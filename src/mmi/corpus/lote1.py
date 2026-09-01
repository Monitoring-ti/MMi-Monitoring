"""Lote 1 MVP — revisiones vigentes para Fase 0 (sin Rev 4/5 ni duplicados BCK)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lote1Spec:
    name_suffix: str
    document_key: str
    revision: str
    is_current: bool
    tipo: str
    phase0: str  # excel | pdf | pptx | ocr


# Rev 6 = guía vigente. Rev 5 / Rev 4 quedan fuera del lote inicial.
LOTE1_SPECS: tuple[Lote1Spec, ...] = (
    Lote1Spec("NCC-030_REV02.pdf", "NCC-030", "REV02", True, "norma", "pdf"),
    Lote1Spec(
        "SGP-07MYC-GUIGS-00001 GUIA MANTENIBILIDAD Y CONFIABILIDAD EN PROYECTOS Rev 6.pdf",
        "SGP-07MYC-GUIGS-00001",
        "Rev 6",
        True,
        "guia",
        "pdf",
    ),
    Lote1Spec(
        "SGPD-07MYC-PROGS-0001 Procedimiento de Mantenibilidad y Confiabilidad en Estudios y Proyectos.pdf",
        "SGPD-07MYC-PROGS-0001",
        "vigente",
        True,
        "sop",
        "pdf",
    ),
    Lote1Spec(
        "Anexo C Check List SGP-07MYC-GUIGS-00001.xlsx",
        "SGP-07MYC-GUIGS-00001-Anexo-C",
        "checklist",
        True,
        "tabla",
        "excel",
    ),
    Lote1Spec(
        "SGPD-07MYC-FRMGS-0035 FMECA.xlsx",
        "SGPD-07MYC-FRMGS-0035",
        "FMECA",
        True,
        "tabla",
        "excel",
    ),
    Lote1Spec(
        "SGPD-07MYC-FRMGS-0036 RCM.xlsx",
        "SGPD-07MYC-FRMGS-0036",
        "RCM",
        True,
        "tabla",
        "excel",
    ),
    Lote1Spec(
        "FMECA MONITORING 092021 rev 1.pptx",
        "FMECA-CAPACITACION",
        "rev 1",
        True,
        "presentacion",
        "pptx",
    ),
    Lote1Spec(
        "RCM MONITORING 072021 rev 4_TE (1) (1).pptx",
        "RCM-CAPACITACION",
        "rev 4",
        True,
        "presentacion",
        "pptx",
    ),
    Lote1Spec(
        "IFC 078_REV15 28122020 (1).pdf",
        "IFC-078",
        "REV15",
        True,
        "sop",
        "pdf",
    ),
)


def _file_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


def resolve_lote1(corpus_root: Path) -> tuple[list[dict], list[str]]:
    """Resuelve archivos del lote 1 bajo corpus_root (p. ej. 00 DOCUMENTOS NCC30)."""
    if not corpus_root.exists():
        return [], [f"No existe carpeta corpus: {corpus_root}"]

    by_name: dict[str, Path] = {}
    for path in corpus_root.rglob("*"):
        if path.is_file():
            by_name[path.name] = path

    files: list[dict] = []
    missing: list[str] = []
    for spec in LOTE1_SPECS:
        path = by_name.get(spec.name_suffix)
        if path is None:
            missing.append(spec.name_suffix)
            continue
        rel = f"{corpus_root.name}/{path.relative_to(corpus_root).as_posix()}"
        ext = path.suffix.lower()
        phase0 = spec.phase0
        suggested_tipo = spec.tipo
        plan_detection: dict | None = None
        if ext == ".pdf":
            from mmi.ingest.plan_detect import detect_plan

            det = detect_plan(path)
            plan_detection = det.to_dict()
            suggested_tipo = det.suggested_tipo
            if spec.phase0 == "ocr" and det.block_ocr:
                phase0 = det.suggested_phase0
            elif spec.phase0 == "ocr" and det.is_plano:
                phase0 = "ocr"
            elif spec.phase0 == "pdf" and det.is_plano and det.ocr_page_ratio >= 0.5:
                phase0 = "ocr"
        files.append(
            {
                "id": _file_id(str(path.resolve())),
                "name": path.name,
                "relative_path": rel,
                "absolute_path": str(path.resolve()),
                "source": "local",
                "extension": ext,
                "ready": True,
                "document_key": spec.document_key,
                "revision": spec.revision,
                "is_current": spec.is_current,
                "suggested_tipo": suggested_tipo,
                "phase0": phase0,
                "plan_detection": plan_detection,
                "is_plano": plan_detection.get("is_plano") if plan_detection else None,
            }
        )
    return files, missing
