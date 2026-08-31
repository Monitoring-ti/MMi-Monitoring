#!/usr/bin/env python3
"""
MMI — Fase 3 · Validación del motor de búsqueda híbrida afinado.

Ejecuta un conjunto de consultas representativas del dominio (definiciones,
procedimientos, seguridad, tablas) y evalúa:
  - Si el boost de seguridad eleva chunks 'seguridad' en consultas de seguridad.
  - Si el reranking deduplica por documento/sección.
  - Si los resultados son relevantes para la consulta.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from search import HybridSearchEngine

# (consulta, ¿es de seguridad?, descripción)
CONSULTAS = [
    ("¿Qué es la mantenibilidad y cómo se evalúa?", False, "definición"),
    ("modos de falla y criticidad FMECA", False, "metodología"),
    ("advertencia seguridad bloqueo antes de operar equipo", True, "seguridad"),
    ("¿Cuáles son los criterios de criticidad según NCC-30?", False, "norma"),
    ("check list de mantenibilidad accesibilidad", False, "tabla"),
    ("¿Qué es el RCM y en qué se diferencia del FMECA?", False, "metodología"),
]


def main():
    engine = HybridSearchEngine()
    print("=" * 70)
    print("VALIDACIÓN DEL MOTOR HÍBRIDO — Fase 3")
    print("=" * 70)

    for q, es_seg, desc in CONSULTAS:
        results = engine.search(q, limit=4)
        print(f"\n[{desc:12}] {q}")
        print(f"         (consulta de seguridad: {es_seg})")
        if not results:
            print("         Sin resultados")
            continue
        n_seg = sum(1 for r in results if r.criticality_level == "seguridad")
        for i, r in enumerate(results, 1):
            sec = f" | {r.section_path[:35]}" if r.section_path else ""
            ver = f" | {r.version_label}" if r.version_label else ""
            marca = " *SEG*" if r.criticality_level == "seguridad" else ""
            print(f"  {i}. [{r.tipo:11}] {r.score:.3f}{sec}{ver}{marca}")
            print(f"     {r.content[:75]}…")
        if es_seg:
            print(f"  -> chunks de seguridad en top-4: {n_seg}")


if __name__ == "__main__":
    main()
