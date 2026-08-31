#!/usr/bin/env python3
"""
MMI — Carga masiva · Clasificación del corpus y construcción del manifiesto.

Clasifica cada archivo por tipo (norma/guia/sop/tabla/presentacion/otro) y
dominio (criticidad/mantenibilidad/confiabilidad/otro) a partir de su nombre,
y detecta la etiqueta de versión (Rev X). Omite imágenes (jpg/png) que no son
documentos de texto.
"""
import os
import re
import json

CORPUS = "/home/ubuntu/mmi_corpus/completo"

# Palabras clave para clasificar por tipo
TIPO_KW = [
    ("norma", ["ncc-030", "ncc030", "norma", "gcm-m"]),
    ("guia", ["guigs", "guia", "guía"]),
    ("sop", ["progs", "procedimiento", "taller m@c", "taller m&c"]),
    ("tabla", ["frmgs", "check list", "checklist", "fmeca", "rcm", "analisis tarea"]),
    ("presentacion", ["presentacion", "taller", "capacitación", "capacitacion", "etapa de ejecucion"]),
]

# Palabras clave para el dominio
DOMINIO_KW = [
    ("criticidad", ["ncc-030", "ncc030", "criticidad", "adenda ncc"]),
    ("mantenibilidad", ["mantenibilidad", "guigs", "check list", "checklist"]),
    ("confiabilidad", ["confiabilidad", "fmeca", "rcm", "analisis tarea", "frmgs"]),
]

# Extensiones que son documentos de texto procesables
EXT_PROCESABLES = {".pdf", ".docx", ".xlsx", ".pptx"}
# Imágenes: no son documentos de texto (se omiten de la ingesta RAG)
EXT_IMAGENES = {".jpg", ".jpeg", ".png"}


def clasificar(nombre: str, kws: list[tuple[str, list[str]]], default: str) -> str:
    n = nombre.lower()
    for etiqueta, palabras in kws:
        if any(p in n for p in palabras):
            return etiqueta
    return default


def detectar_version(nombre: str) -> str | None:
    m = re.search(r"\brev(?:ision)?[\s._-]*(\d+(?:\.\d+)?)\b", nombre, re.IGNORECASE)
    if m:
        return f"Rev {m.group(1)}"
    m = re.search(r"\bREV(\d+)\b", nombre)
    if m:
        return f"Rev {m.group(1)}"
    return None


def main():
    archivos = sorted(os.listdir(CORPUS))
    manifiesto = []
    omitidos = []
    for fname in archivos:
        ext = os.path.splitext(fname)[1].lower()
        if ext in EXT_IMAGENES:
            omitidos.append((fname, "imagen"))
            continue
        if ext not in EXT_PROCESABLES:
            omitidos.append((fname, f"ext {ext} no soportada"))
            continue
        tipo = clasificar(fname, TIPO_KW, "otro")
        dominio = clasificar(fname, DOMINIO_KW, "otro")
        version = detectar_version(fname)
        manifiesto.append({
            "archivo": fname, "tipo": tipo, "dominio": dominio,
            "version": version, "ext": ext,
        })

    out = "/home/ubuntu/mmi/scripts/manifest_corpus.json"
    with open(out, "w") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=2)

    from collections import Counter
    print(f"Procesables: {len(manifiesto)} | Omitidos: {len(omitidos)}")
    print("Por tipo:", dict(Counter(m["tipo"] for m in manifiesto)))
    print("Por dominio:", dict(Counter(m["dominio"] for m in manifiesto)))
    print("Por extensión:", dict(Counter(m["ext"] for m in manifiesto)))
    print(f"\nManifiesto guardado en {out}")
    if omitidos:
        print("\nOmitidos:")
        for f, r in omitidos:
            print(f"  {f} ({r})")


if __name__ == "__main__":
    main()
