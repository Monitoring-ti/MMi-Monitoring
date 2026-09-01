"""Preprocesamiento selectivo de imágenes para OCR (C4.2)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from mmi.config import get_ocr_settings

logger = logging.getLogger(__name__)


def preprocess_image(
    source: Path,
    dest: Path,
    *,
    dpi: int | None = None,
    grayscale: bool = True,
    autocontrast: bool = True,
) -> Path:
    """Preprocesa imagen para OCR. Si Pillow no está, copia el original."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    settings = get_ocr_settings()
    target_dpi = dpi or settings.dpi

    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError:
        logger.warning("Pillow no instalado; copiando imagen sin preprocesar")
        shutil.copy2(source, dest)
        return dest

    with Image.open(source) as img:
        if grayscale and img.mode not in {"L", "1"}:
            img = ImageOps.grayscale(img)
        if autocontrast:
            img = ImageOps.autocontrast(img)
        if target_dpi and hasattr(img, "info"):
            img.info["dpi"] = (target_dpi, target_dpi)
        img.save(dest)
    return dest


def preprocess_page_raster(
    source: Path,
    page_dir: Path,
    *,
    dpi: int | None = None,
) -> tuple[Path, Path]:
    """Devuelve (original_uri, preprocessed_uri) relativos a page_dir.parent.parent."""
    page_dir.mkdir(parents=True, exist_ok=True)
    original = page_dir / "original.png"
    preprocessed = page_dir / "preprocessed.png"
    if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        shutil.copy2(source, original)
    else:
        # PDF u otro: el caller debe rasterizar; copiamos como placeholder
        shutil.copy2(source, original)
    preprocess_image(original, preprocessed, dpi=dpi)
    staging_root = page_dir.parent.parent
    return (
        str(original.relative_to(staging_root)),
        str(preprocessed.relative_to(staging_root)),
    )
