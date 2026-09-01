"""Worker B2: ingesta por etapas reanudables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from mmi.corpus.paths import DEFAULT_EXTRACT_FULL
from mmi.index.manifest_index import indexable_from_manifest
from mmi.index.stages import (
    StageContext,
    list_failed_for_resume,
    resume_failed_document,
    run_full_ingest,
    run_through_chunk,
)


def _ctx_from_item(item: dict) -> StageContext:
    return StageContext(
        path=Path(item["path"]),
        tipo=item["tipo"],
        document_key=item.get("document_key"),
        version_label=item.get("version_label") or None,
        relative_path=item.get("relative_path") or "",
        origen=item.get("origen") or "ods1",
        asset_tag=item.get("asset_tag") or "",
        modulo=item.get("modulo") or "",
    )


def _preview_item(item: dict) -> dict:
    ctx = _ctx_from_item(item)
    stages = run_through_chunk(ctx)
    return {
        "archivo": item["name"],
        "logical_key": ctx.logical_key,
        "content_hash": (ctx.content_hash or "")[:12],
        "identity_decision": ctx.identity_decision,
        "chunks": ctx.metrics.get("chunks", 0),
        "stages": [
            {"stage": s.stage, "ok": s.ok, "skip": s.skip, "reason": s.reason}
            for s in stages
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker de ingesta por etapas (B2)")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("out/ingest-worker-preview.json"))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar pipeline completo (embed/index/activate)",
    )
    parser.add_argument(
        "--from-stage",
        choices=[
            "validate",
            "extract",
            "chunk",
            "identity",
            "register",
            "embed",
            "index",
            "validate_index",
            "activate",
        ],
        help="Reanudar desde etapa (requiere --execute)",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Indexar sin activar versión (estado indexed)",
    )
    parser.add_argument(
        "--resume-failed",
        action="store_true",
        help="Reanudar documentos con status=failed en PG (B2.7)",
    )
    parser.add_argument(
        "--document-id",
        help="Reanudar un document_id específico (requiere --resume-failed --execute)",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    items: list[dict] = []
    errors = 0

    if args.resume_failed:
        if not args.execute:
            print("--resume-failed requiere --execute")
            return 2
        failed = list_failed_for_resume(limit=args.limit)
        if args.document_id:
            failed = [d for d in failed if d.get("id") == args.document_id]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": []}
        by_path = {
            (e.get("absolute_path") or ""): e
            for e in manifest.get("files") or []
        }
        for doc in failed:
            entry = by_path.get(doc.get("source_file_id") or "")
            try:
                result = resume_failed_document(
                    doc,
                    tipo=(entry or {}).get("tipo") or doc.get("tipo") or "otro",
                    relative_path=(entry or {}).get("relative_path") or "",
                    asset_tag=(entry or {}).get("asset_tag") or "",
                    modulo=(entry or {}).get("modulo") or "",
                    activate=not args.no_activate,
                    from_stage=args.from_stage if args.from_stage else None,  # type: ignore[arg-type]
                )
                items.append(result)
                if result.get("estado") == "failed":
                    errors += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                items.append(
                    {
                        "archivo": doc.get("titulo"),
                        "document_id": doc.get("id"),
                        "estado": "failed",
                        "error": str(exc)[:300],
                    }
                )
    else:
        files = indexable_from_manifest(manifest_path, extract_root)[: args.limit]

        for item in files:
            if args.execute:
                ctx = _ctx_from_item(item)
                ctx.activate = not args.no_activate
                try:
                    result = run_full_ingest(
                        ctx,
                        from_stage=args.from_stage if args.from_stage else None,  # type: ignore[arg-type]
                    )
                    items.append(result)
                    if result.get("estado") == "failed":
                        errors += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    items.append(
                        {
                            "archivo": item["name"],
                            "estado": "failed",
                            "error": str(exc)[:300],
                        }
                    )
            else:
                items.append(_preview_item(item))

    payload = {
        "mode": "resume_failed" if args.resume_failed else ("execute" if args.execute else "preview"),
        "count": len(items),
        "errors": errors,
        "items": items,
    }
    out = args.out if args.out.is_absolute() else repo / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    label = "Ejecutados" if args.execute else "Preview"
    print(f"{label} {len(items)} docs → {out}" + (f" · {errors} error(es)" if errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
