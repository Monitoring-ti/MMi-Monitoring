"""Entrypoint para Railpack/local: arranca la vitrina MMI."""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Asegura imports desde src/ si no está instalado el paquete.
    root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)

    os.environ.setdefault("MMI_DEPLOY_MODE", "vitrina")
    os.environ.setdefault("MMI_BIND_HOST", "0.0.0.0")

    from mmi.tools.serve_local import main as serve_main

    port = os.environ.get("PORT", "8773")
    return serve_main(["--host", "0.0.0.0", "--port", port, "--no-replace"])


if __name__ == "__main__":
    raise SystemExit(main())
