"""Servidor estático out/ + APIs de ingesta (compartido por serve_local y analysis_status)."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse

from mmi.tools.api_routes import ApiContext, handle_get_api, handle_post_api


def make_out_handler(out_dir: Path, *, tenant_slug: str = "monitoring"):
    out_dir = out_dir.resolve()
    api_ctx = ApiContext(tenant_slug=tenant_slug, out_dir=out_dir)

    class OutHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"[mmi] {args[0]}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self.send_response(302)
                self.send_header("Location", "/review.html")
                self.end_headers()
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
            if self._serve_static(path):
                return
            self.send_error(404, f"No encontrado: {path}")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/ingestion-action":
                self._handle_ingestion_action()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json({"error": "JSON inválido"}, status=400)
                return
            try:
                if handle_post_api(path, data, self, api_ctx):
                    return
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_json({"error": f"POST no soportado: {path}"}, status=404)

        def _handle_ingestion_action(self) -> None:
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

        def _serve_static(self, path: str) -> bool:
            rel = unquote(path.lstrip("/") or "review.html")
            rel = rel.replace("\\", "/")
            target = (out_dir / rel).resolve()
            try:
                target.relative_to(out_dir)
            except ValueError:
                return False
            if target.is_file():
                self._send_file(target)
                return True
            return False

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
            if ctype.startswith("text/html") or path.suffix == ".json":
                self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

    return OutHandler
