"""Servidor local MMI: búsqueda + estáticos en out/."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

from mmi.search.answer import ask
from mmi.search.api_payloads import ask_details_payload, ask_payload
from mmi.search.engine import HybridSearchEngine
from mmi.search.session import AskSession, AskSessionStore
from mmi.tools.search_cli import _result_dict, render_search_html


def make_handler(engine: HybridSearchEngine, out_dir: Path, search_html: str):
    from mmi.corpus.remote_source import load_remote_source, save_remote_source

    remote_path = out_dir / "remote-source.json"
    sessions = AskSessionStore()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"[mmi] {args[0]}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self.send_response(302)
                self.send_header("Location", "/search.html")
                self.end_headers()
                return
            if path == "/api/remote-source":
                data = load_remote_source(remote_path) or {}
                self._send_json(data)
                return
            rel = path.lstrip("/") or "search.html"
            target = out_dir / rel
            if target.is_file():
                self._send_file(target)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            import time

            path = urlparse(self.path).path
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

            if path not in {"/api/search", "/api/ask", "/api/ask-details"}:
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                t0 = time.perf_counter()

                if path == "/api/ask-details":
                    session_id = (data.get("ask_id") or "").strip()
                    section = (data.get("section") or "").strip()
                    session = sessions.get(session_id)
                    if session is None:
                        self._send_json({"error": "Sesión expirada o inválida"}, status=404)
                        return
                    payload = ask_details_payload(session, section, _result_dict)
                    payload["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
                    self._send_json(payload)
                    return

                query = (data.get("query") or "").strip()
                limit = int(data.get("limit") or 6)

                if path == "/api/search":
                    hits = engine.search(query, limit=limit)
                    payload = {
                        "query": query,
                        "count": len(hits),
                        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                        "results": [_result_dict(r) for r in hits],
                    }
                else:
                    result = ask(query, engine, limit=limit)
                    session_id = sessions.put(
                        AskSession(
                            query=result.query,
                            hits=result.hits,
                            cited_indices=result.cited_indices,
                            references=result.references,
                        )
                    )
                    payload = ask_payload(
                        result,
                        session_id,
                        int((time.perf_counter() - t0) * 1000),
                    )

                self._send_json(payload)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=500)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            ctype, _ = mimetypes.guess_type(str(path))
            ctype = ctype or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor local MMI (búsqueda + out/)")
    parser.add_argument("--port", type=int, default=8773)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--tenant", default="monitoring")
    args = parser.parse_args(argv)

    load_dotenv()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    search_html = render_search_html()
    (out_dir / "search.html").write_text(search_html, encoding="utf-8")

    engine = HybridSearchEngine(tenant_slug=args.tenant)
    handler = make_handler(engine, out_dir, search_html)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"MMI local → http://127.0.0.1:{args.port}/")
    print(f"  Búsqueda     http://127.0.0.1:{args.port}/")
    print(f"  Estado       http://127.0.0.1:{args.port}/analysis-status.html")
    print(f"  Enlace nube  http://127.0.0.1:{args.port}/source-review.html")
    print(f"  Corpus       http://127.0.0.1:{args.port}/corpus-picker.html")
    print("  Generación   OpenRouter (/api/ask)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
