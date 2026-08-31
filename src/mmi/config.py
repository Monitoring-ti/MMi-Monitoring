"""Configuración desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OcrSettings:
    provider: str
    azure_endpoint: str
    azure_key: str
    azure_model: str
    min_page_confidence: float
    min_block_confidence: float

    @property
    def azure_configured(self) -> bool:
        return bool(self.azure_endpoint.strip() and self.azure_key.strip())

    @classmethod
    def from_env(cls) -> OcrSettings:
        return cls(
            provider=(os.getenv("MMI_OCR_PROVIDER") or "azure").strip().lower(),
            azure_endpoint=(os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or "").strip(),
            azure_key=(os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or "").strip(),
            azure_model=(os.getenv("AZURE_DOCUMENT_INTELLIGENCE_MODEL") or "prebuilt-layout").strip(),
            min_page_confidence=float(os.getenv("MMI_OCR_MIN_PAGE_CONFIDENCE", "0.75")),
            min_block_confidence=float(os.getenv("MMI_OCR_MIN_BLOCK_CONFIDENCE", "0.60")),
        )


def get_ocr_settings() -> OcrSettings:
    return OcrSettings.from_env()
