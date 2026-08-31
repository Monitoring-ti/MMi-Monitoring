#!/usr/bin/env python3
"""
MMI — Fase 2 · Análisis de calidad del chunking actual.

Mide la distribución de tamaños, detecta chunks degenerados (muy cortos o
cortados a media frase) y evalúa si los cortes respetan la estructura del
documento, por tipo de documento.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from extractors import extract
from chunking import chunk_blocks, count_tokens

LOTE = "/home/ubuntu/mmi_corpus/lote1"

DOCS = [
    ("NCC-030_REV02.pdf", "norma"),
    ("SGP-07MYC-GUIGS-00001 GUIA MANTENIBILIDAD Y CONFIABILIDAD EN PROYECTOS Rev 6.pdf", "guia"),
    ("SGPD-07MYC-PROGS-0001 Procedimiento de Mantenibilidad y Confiabilidad en Estudios y Proyectos.pdf", "sop"),
    ("Anexo C Check List SGP-07MYC-GUIGS-00001.xlsx", "tabla"),
    ("FMECA MONITORING 092021 rev 1.pptx", "presentacion"),
]


def stats(tokens):
    if not tokens:
        return {}
    s = sorted(tokens)
    n = len(s)
    return {
        "n": n,
        "min": s[0],
        "p25": s[n // 4],
        "mediana": s[n // 2],
        "p75": s[3 * n // 4],
        "max": s[-1],
        "media": sum(s) / n,
    }


def main():
    print(f"{'Documento':42} {'tipo':12} {'n':>4} {'min':>5} {'med':>5} {'p75':>5} {'max':>5} {'cortos':>6} {'largos':>6}")
    print("-" * 100)
    for fname, tipo in DOCS:
        path = os.path.join(LOTE, fname)
        fmt = os.path.splitext(path)[1].lower()
        blocks = extract(path)
        chunks = chunk_blocks(blocks, fmt, tipo)
        tokens = [c.token_count for c in chunks]
        st = stats(tokens)
        if not st:
            print(f"{fname[:42]:42} {tipo:12}  (sin chunks)")
            continue
        # Chunks degenerados
        cortos = sum(1 for t in tokens if t < 80)     # casi sin contenido
        largos = sum(1 for t in tokens if t > 1400)   # exceden el objetivo
        print(f"{fname[:42]:42} {tipo:12} {st['n']:>4} {st['min']:>5} "
              f"{st['mediana']:>5} {st['p75']:>5} {st['max']:>5} {cortos:>6} {largos:>6}")

    print()
    print("Leyenda: cortos = <80 tokens (ruido), largos = >1400 tokens (exceden objetivo)")

    # Detalle: chunks cortos del SOP (posible ruido)
    print("\n=== Chunks cortos (<80 tok) del SOP ===")
    blocks = extract(os.path.join(LOTE, DOCS[2][0]))
    chunks = chunk_blocks(blocks, ".pdf", "sop")
    for c in chunks:
        if c.token_count < 80:
            print(f"  [{c.token_count:>3} tok] {c.content[:90]!r}")


if __name__ == "__main__":
    main()
