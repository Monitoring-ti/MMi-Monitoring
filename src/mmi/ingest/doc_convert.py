"""Conversión DOC legacy → DOCX (LibreOffice opcional)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def convert_doc_to_docx(path: Path) -> Path:
    """Convierte .doc a .docx temporal. Requiere LibreOffice (soffice) en PATH."""
    path = Path(path)
    if path.suffix.lower() != ".doc":
        raise ValueError(f"No es .doc: {path}")

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(
            "Archivo .doc requiere LibreOffice (soffice) para convertir a DOCX. "
            "Instala LibreOffice o entrega el archivo en formato .docx."
        )

    out_dir = Path(tempfile.mkdtemp(prefix="mmi-doc-convert-"))
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        str(out_dir),
        str(path.resolve()),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"LibreOffice falló: {proc.stderr[:300]}")

    candidates = list(out_dir.glob("*.docx"))
    if not candidates:
        raise RuntimeError(f"Conversión sin salida docx: {path.name}")
    return candidates[0]
