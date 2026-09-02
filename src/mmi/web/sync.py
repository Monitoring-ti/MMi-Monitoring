"""Sincroniza assets web estaticos hacia out/ para serve_local."""

from __future__ import annotations

import shutil
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def sync_web_assets(out_dir: Path, *, repo_root: Path | None = None) -> None:
    """Copia web/, public/ y genera app.css desde app/globals.css."""
    root = repo_root or _repo_root()
    out_dir.mkdir(parents=True, exist_ok=True)

    for folder in ("web", "public"):
        src_root = root / folder
        if not src_root.is_dir():
            continue
        for path in src_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src_root)
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    css_src = root / "app" / "globals.css"
    if css_src.is_file():
        css = css_src.read_text(encoding="utf-8")
        css = css.replace('@import "tailwindcss";\n\n', "").replace('@import "tailwindcss";\r\n\r\n', "")
        css += """
.spin-ring{position:absolute;width:108px;height:108px;border:2px solid transparent;border-top-color:var(--blue);border-radius:50%;animation:spin 1.2s linear infinite}
.asset-card>button.asset-open{width:100%;border:0;background:transparent;color:var(--blue);display:flex;align-items:center;justify-content:space-between;padding:14px 0 0;font-size:11px;font-weight:700;text-transform:uppercase}
.sidebar nav .nav-btn{width:100%;text-align:left}
"""
        (out_dir / "app.css").write_text(css, encoding="utf-8")
