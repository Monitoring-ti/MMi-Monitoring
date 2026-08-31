#!/usr/bin/env python3
"""
MMI — Carga masiva · Ingesta del corpus completo.

Procesa todos los archivos del manifiesto con versionado SHA-256, manejo de
errores por archivo y un log de resultados. Los documentos ya indexados con el
mismo hash se detectan como duplicados y se omiten.
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from ingest import ingest

CORPUS = "/home/ubuntu/mmi_corpus/completo"
TENANT = "monitoring"
MANIFEST = os.path.join(os.path.dirname(__file__), "manifest_corpus.json")
LOG = os.path.join(os.path.dirname(__file__), "ingest_corpus_log.json")


def main():
    with open(MANIFEST) as f:
        manifiesto = json.load(f)

    resultados = []
    t0 = time.time()
    for i, m in enumerate(manifiesto, 1):
        fname = m["archivo"]
        path = os.path.join(CORPUS, fname)
        if not os.path.exists(path):
            res = {"archivo": fname, "estado": "no_encontrado"}
        else:
            try:
                res = ingest(path, TENANT, m["tipo"], m.get("version"), m.get("dominio"))
            except Exception as e:
                res = {"archivo": fname, "estado": "error", "detalle": str(e)[:300]}
        resultados.append(res)
        estado = res.get("estado")
        nch = res.get("chunks", 0)
        print(f"[{i:2}/{len(manifiesto)}] {estado:14} {nch:4} chunks  {fname[:50]}")
        # Guardar log incremental
        with open(LOG, "w") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

    dt = time.time() - t0
    ok = [r for r in resultados if r.get("estado") == "indexado"]
    dup = [r for r in resultados if r.get("estado") == "duplicado"]
    vac = [r for r in resultados if r.get("estado") == "sin_contenido"]
    err = [r for r in resultados if r.get("estado") == "error"]
    nf = [r for r in resultados if r.get("estado") == "no_encontrado"]

    print("\n=== RESUMEN CARGA MASIVA ===")
    print(f"Tiempo total : {dt:.0f} s")
    print(f"Indexados    : {len(ok)} ({sum(r.get('chunks', 0) for r in ok)} chunks, "
          f"{sum(r.get('tokens', 0) for r in ok)} tokens)")
    print(f"Duplicados   : {len(dup)}")
    print(f"Sin contenido: {len(vac)}")
    print(f"Errores      : {len(err)}")
    print(f"No encontrado: {len(nf)}")
    for e in err:
        print("  ERROR:", e.get("archivo"), "->", e.get("detalle"))
    for v in vac:
        print("  VACÍO:", v.get("archivo"))


if __name__ == "__main__":
    main()
