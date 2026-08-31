#!/usr/bin/env python3
"""
MMI — Fase 1 · Ingesta masiva del lote 1.

Procesa los 8 archivos del lote con sus metadatos (tipo, versión, dominio).
El par Rev 5 / Rev 6 de la guía se ingesta como dos versiones del mismo
documento lógico para probar el versionado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from ingest import ingest

LOTE = "/home/ubuntu/mmi_corpus/lote1"
TENANT = "monitoring"

# (archivo, tipo, version_label, dominio)
ARCHIVOS = [
    ("NCC-030_REV02.pdf", "norma", "REV02", "criticidad"),
    ("SGP-07MYC-GUIGS-00001 GUIA MANTENIBILIDAD Y CONFIABILIDAD EN PROYECTOS Rev 6.pdf",
     "guia", "Rev 6", "mantenibilidad"),
    ("SGP-07MYC-GUIGS-00001 Rev 5.pdf", "guia", "Rev 5", "mantenibilidad"),
    ("SGPD-07MYC-PROGS-0001 Procedimiento de Mantenibilidad y Confiabilidad en Estudios y Proyectos.pdf",
     "sop", None, "mantenibilidad"),
    ("Anexo C Check List SGP-07MYC-GUIGS-00001.xlsx", "tabla", None, "mantenibilidad"),
    ("SGPD-07MYC-FRMGS-0035 FMECA.xlsx", "tabla", None, "confiabilidad"),
    ("FMECA MONITORING 092021 rev 1.pptx", "presentacion", "rev 1", "confiabilidad"),
    ("RCM MONITORING 072021 rev 4_TE (1) (1).pptx", "presentacion", "rev 4", "confiabilidad"),
]


def main():
    resultados = []
    for fname, tipo, version, dominio in ARCHIVOS:
        path = os.path.join(LOTE, fname)
        if not os.path.exists(path):
            print(f"NO ENCONTRADO: {fname}")
            continue
        try:
            res = ingest(path, TENANT, tipo, version, dominio)
        except Exception as e:
            res = {"archivo": fname, "estado": "error", "detalle": str(e)[:200]}
        resultados.append(res)
        print(res)

    print("\n=== RESUMEN LOTE 1 ===")
    ok = [r for r in resultados if r.get("estado") == "indexado"]
    dup = [r for r in resultados if r.get("estado") == "duplicado"]
    err = [r for r in resultados if r.get("estado") == "error"]
    print(f"Indexados : {len(ok)} ({sum(r.get('chunks', 0) for r in ok)} chunks, "
          f"{sum(r.get('tokens', 0) for r in ok)} tokens)")
    print(f"Duplicados: {len(dup)}")
    print(f"Errores   : {len(err)}")
    for e in err:
        print("  ERROR:", e.get("archivo"), "->", e.get("detalle"))


if __name__ == "__main__":
    main()
