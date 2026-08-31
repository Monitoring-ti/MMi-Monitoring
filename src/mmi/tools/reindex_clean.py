"""Limpieza y re-indexación del lote 1 (solo versiones vigentes)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from mmi.corpus.lote1 import resolve_lote1
from mmi.index.chunking import file_sha256
from mmi.index.store import (
    pg_delete_chunks,
    pg_delete_document,
    pg_get_tenant_id,
    pg_list_documents,
    qdrant_delete_document_points,
)
from mmi.tools.index_lote1 import _indexable_from_manifest, main as index_main


def _allowed_hashes(corpus_root: Path) -> set[str]:
    files, _ = resolve_lote1(corpus_root)
    allowed: set[str] = set()
    for entry in files:
        path = entry.get("absolute_path")
        if path and Path(path).exists():
            allowed.add(file_sha256(path))
    return allowed


def _allowed_keys(corpus_root: Path) -> set[str]:
    files, _ = resolve_lote1(corpus_root)
    return {f["document_key"] for f in files}


def clean_tenant(
    tenant_slug: str,
    *,
    corpus_root: Path,
    dry_run: bool = True,
) -> list[dict]:
    tenant_id = pg_get_tenant_id(tenant_slug)
    allowed_hashes = _allowed_hashes(corpus_root)
    allowed_keys = _allowed_keys(corpus_root)
    actions: list[dict] = []

    for doc in pg_list_documents(tenant_id):
        fh = doc.get("file_hash")
        dk = doc.get("document_key")
        remove = False
        reason = ""
        if fh and fh not in allowed_hashes:
            remove = True
            reason = "hash fuera de lote1 vigente"
        elif dk and dk not in allowed_keys and fh not in allowed_hashes:
            remove = True
            reason = "document_key fuera de lote1"

        if not remove:
            continue

        action = {
            "document_id": doc["id"],
            "titulo": doc.get("titulo"),
            "document_key": dk,
            "reason": reason,
            "dry_run": dry_run,
        }
        if not dry_run:
            qdrant_delete_document_points(tenant_id, doc["id"])
            pg_delete_chunks(doc["id"])
            pg_delete_document(doc["id"])
            action["deleted"] = True
        actions.append(action)

    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limpieza índice lote 1 + re-index opcional")
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--corpus", type=Path, default=Path("00 DOCUMENTOS NCC30"))
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=Path("out/lote1-extract"))
    parser.add_argument("--dry-run", action="store_true", help="Solo listar documentos a eliminar")
    parser.add_argument("--reindex", action="store_true", help="Re-indexar tras limpiar")
    parser.add_argument("--out", type=Path, default=Path("out/reindex-clean-report.json"))
    args = parser.parse_args(argv)

    load_dotenv()
    corpus = args.corpus if args.corpus.is_absolute() else Path.cwd() / args.corpus

    print("Documentos a retirar del índice:")
    actions = clean_tenant(args.tenant, corpus_root=corpus, dry_run=args.dry_run)
    for a in actions:
        mark = "DRY" if a.get("dry_run") else "DEL"
        print(f"  [{mark}] {a.get('titulo')} — {a.get('reason')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReporte → {args.out.resolve()} ({len(actions)} documentos)")

    if args.dry_run:
        print("\nEjecuta sin --dry-run para eliminar.")
        return 0

    if args.reindex:
        print("\nRe-indexando lote 1…")
        return index_main(
            [
                "--manifest",
                str(args.manifest),
                "--extract-dir",
                str(args.extract_dir),
                "--tenant",
                args.tenant,
            ]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
