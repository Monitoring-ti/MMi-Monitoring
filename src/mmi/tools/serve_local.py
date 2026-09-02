"""Servidor local MMI: búsqueda + estáticos en out/."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

from mmi.graph.page import render_mapa_html
from mmi.motor.page import render_motor_html
from mmi.search.rag_page import render_rag_html
from mmi.tools.api_routes import ApiContext, handle_get_api, handle_post_api, normalize_api_path
from mmi.tools.console import configure_stdout_utf8
from mmi.tools.search_cli import render_search_html
from mmi.web.deploy_mode import is_vitrina
from mmi.web.landing import write_landing_page
from mmi.web.sync import sync_web_assets
from mmi.web.vitrina import write_vitrina_pages
from mmi.analysis.ingestion_results import write_ingestion_results


def make_handler(engine, out_dir: Path, search_html: str, *, tenant_slug: str = "monitoring"):
    from mmi.corpus.remote_source import load_remote_source, save_remote_source

    remote_path = out_dir / "remote-source.json"
    api_ctx = ApiContext(tenant_slug=tenant_slug, out_dir=out_dir, _engine=engine)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"[mmi] {args[0]}")

        def _cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                target = out_dir / "index.html"
                if target.is_file():
                    self._send_file(target)
                    return
                self.send_response(302)
                self.send_header("Location", "/app.html")
                self.end_headers()
                return
            if path == "/api/remote-source":
                data = load_remote_source(remote_path) or {}
                self._send_json(data)
                return
            if path == "/api/ingestion-live":
                from mmi.analysis.live_status import collect_live_snapshot

                self._send_json(collect_live_snapshot(out_dir))
                return
            if path == "/api/review-models":
                from mmi.analysis.llm_review import REVIEW_MODELS

                self._send_json({"models": REVIEW_MODELS})
                return
            if handle_get_api(path, self, api_ctx):
                return
            rel = unquote(path.lstrip("/") or "search.html")
            rel = rel.replace("\\", "/")
            target = (out_dir / rel).resolve()
            try:
                target.relative_to(out_dir.resolve())
            except ValueError:
                self.send_error(404)
                return
            if target.is_file():
                self._send_file(target)
                return
            self.send_error(404, f"No encontrado: {path}")

        def do_POST(self) -> None:
            path = normalize_api_path(urlparse(self.path).path)
            if path == "/api/remote-source":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                    saved = save_remote_source(
                        data.get("url") or "",
                        label=data.get("label") or "",
                        path=remote_path,
                    )
                    self._send_json(saved)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": str(exc)}, status=500)
                return

            if path == "/api/ingestion-action":
                if is_vitrina():
                    self._send_json(
                        {"error": "Acción no disponible en modo vitrina (ingesta solo local)."},
                        status=403,
                    )
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                    action = (data.get("action") or "").strip()
                    names = data.get("names") or []
                    if isinstance(names, str):
                        names = [names]
                    if not action or not names:
                        self._send_json({"error": "Se requiere action y names"}, status=400)
                        return
                    from mmi.analysis.reprocess import run_ingestion_action

                    result = run_ingestion_action(
                        action,
                        names,
                        out_dir=out_dir,
                        tenant_slug=tenant_slug,
                        force=bool(data.get("force", True)),
                        quality=data.get("quality"),
                        model=data.get("model"),
                        delete_failed=bool(data.get("delete_failed", True)),
                        note=data.get("note") or "",
                    )
                    self._send_json(result)
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": str(exc)}, status=500)
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                if handle_post_api(path, data, self, api_ctx):
                    return
                self._send_json({"error": f"POST no soportado: {path}"}, status=404)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=500)

        def _send_json(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            ctype, _ = mimetypes.guess_type(str(path))
            ctype = ctype or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if ctype.startswith("text/html") or path.suffix == ".json":
                self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _pids_listening_on_port(port: int) -> set[int]:
    import subprocess

    pids: set[int] = set()
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            timeout=20,
        )
        for line in out.splitlines():
            if f":{port}" not in line or "LISTENING" not in line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                continue
    except (subprocess.SubprocessError, OSError):
        pass
    return pids


def free_listening_port(port: int) -> list[int]:
    """Libera el puerto deteniendo procesos que escuchan en localhost (dev local)."""
    import subprocess
    import time

    freed: list[int] = []
    for _ in range(3):
        pids = _pids_listening_on_port(port)
        if not pids:
            break
        for pid in sorted(pids):
            if pid in freed:
                continue
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=15,
            )
            freed.append(pid)
        time.sleep(1.0)
    return freed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor local MMI (búsqueda + out/)")
    parser.add_argument("--port", type=int, default=8773)
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz de escucha (0.0.0.0 en Docker)")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument(
        "--replace",
        action="store_true",
        default=True,
        help="Detener proceso previo en el puerto (default: sí)",
    )
    parser.add_argument(
        "--no-replace",
        action="store_false",
        dest="replace",
        help="No detener proceso previo en el puerto",
    )
    args = parser.parse_args(argv)

    configure_stdout_utf8()
    load_dotenv()
    if args.replace:
        freed = free_listening_port(args.port)
        if freed:
            print(f"Puerto {args.port}: liberado (PID {', '.join(str(p) for p in freed)})")
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sync_web_assets(out_dir)
    if is_vitrina():
        write_vitrina_pages(out_dir)
    else:
        write_ingestion_results(out_dir)
        write_landing_page(out_dir)
    search_html = render_search_html(out_dir)
    rag_html = render_rag_html(out_dir)
    motor_html = render_motor_html(out_dir)
    mapa_html = render_mapa_html(out_dir)
    (out_dir / "search.html").write_text(search_html, encoding="utf-8")
    (out_dir / "rag.html").write_text(rag_html, encoding="utf-8")
    (out_dir / "motor.html").write_text(motor_html, encoding="utf-8")
    (out_dir / "mapa.html").write_text(mapa_html, encoding="utf-8")

    from mmi.search.engine import HybridSearchEngine

    engine = HybridSearchEngine(tenant_slug=args.tenant)
    handler = make_handler(engine, out_dir, search_html, tenant_slug=args.tenant)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    mode = "vitrina" if is_vitrina() else "development"
    host = args.host if args.host != "0.0.0.0" else "127.0.0.1"
    print(f"MMI local -> http://{host}:{args.port}/  (modo {mode})")
    if is_vitrina():
        print(f"  Vitrina      http://{host}:{args.port}/")
        print(f"  Pruebas      http://{host}:{args.port}/pruebas.html")
        print(f"  Ejemplos     http://{host}:{args.port}/ejemplos.html")
    else:
        print(f"  Portal       http://{host}:{args.port}/index.html")
        print(f"  App MMI      http://{host}:{args.port}/app.html")
        print(f"  Ingesta      http://{host}:{args.port}/ingestion-results.html")
    print(f"  Búsqueda     http://{host}:{args.port}/search.html")
    print(f"  Consulta RAG http://{host}:{args.port}/rag.html")
    print(f"  Health       http://{host}:{args.port}/api/motor/health")
    if not is_vitrina():
        print(f"  Mapa         http://{host}:{args.port}/mapa.html")
        print(f"  Motor MMI    http://{host}:{args.port}/motor.html")
        print(f"  Revisión     http://{host}:{args.port}/review.html")
    print("  Generación   OpenRouter (/api/ask, /api/motor/analyze)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
