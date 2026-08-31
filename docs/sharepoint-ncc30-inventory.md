# Inventario SharePoint — corpus MMI (revisión 2026-08-30)

**Enlace revisado:** carpeta compartida OneDrive de Pedro Hidalgo  
**Ruta:** `Mat Monitoring / web y otros / MMi / primer-up3008 / 00 DOCUMENTOS NCC30`  
**Acceso del agente:** colaborador invitado (guest).  
**Sync local:** este árbol **no** está en `OneDrive - Monitoring SPA` (solo aparece `Pruebas MMI\Listas clasificacion concentradora.xlsx`).

## Qué se ve con el enlace actual

Con el share abierto, la raíz `00 DOCUMENTOS NCC30` muestra **solo** la carpeta `1. NORMA` (8 ítems).  
No aparecen en este acceso: `2. CAPACITACION`, `3. REFERENCIA ANEXOS`, plantillas FRMGS, etc. (sí estaban en el inventario Manus previo). Posibles causas: el enlace comparte un subconjunto, o esas carpetas ya no están en `primer-up3008`.

### `1. NORMA` (raíz de la carpeta compartida efectiva)

| Ítem | Tipo | Tamaño |
| --- | --- | --- |
| 1. VARIOS | carpeta | 7 ítems |
| 11. DIAGRAMAS NATIVOS NCC30 | carpeta | 7 ítems |
| 20180430 Documento SOMA (1).pdf | PDF | 7.87 MB |
| Anexos SGP-07MYC-GUIGS-00001 rev 4.docx | DOCX | 1.97 MB |
| LIBRO SOMA DIGITAL FINAL.pdf | PDF | 18.7 MB (candidato OCR) |
| NCC-030_REV02.pdf | PDF | 1.17 MB |
| SGP-07MYC-GUIGS-00001 … Rev 6.pdf | PDF | 8.87 MB (vigente) |
| SGP-07MYC-GUIGS-00001 Rev 5.pdf | PDF | 8.48 MB (versión anterior) |

### `1. NORMA / 1. VARIOS`

| Ítem | Tipo | Tamaño | Uso MMI |
| --- | --- | --- | --- |
| 11. DIAGRAMAS NATIVOS NCC30 | carpeta | 7 ítems | diagramas / posible OCR |
| **Anexo C Check List SGP-07MYC-GUIGS-00001.xlsx** | **XLSX** | **43.2 KB** | **Excel prioritario para extractor** |
| SGP-07MYC-CRTTC-00002 REV1.pdf | PDF | 483 KB | criticidad |
| SGP-07MYC-GUIGS-00001_REV4.pdf | PDF | 3.06 MB | otra rev de la guía |
| SGP-07MYC-PROGS-00009 TALLER M@C.pdf | PDF | 409 KB | taller |
| SGPD-07MYC-PROGS-0001 … BCK.pdf | PDF | 1.59 MB | duplicado/backup SOP |
| SGPD-07MYC-PROGS-0001 … Proyectos.pdf | PDF | 1.59 MB | SOP principal |

## Hallazgos para el pipeline

1. **Versionado real:** Rev 4 / 5 / 6 de la misma guía → hace falta `document_key` + `is_current`.
2. **Par SOP + BCK:** prueba de SHA-256 / no reindexar idénticos o marcar backup.
3. **Un solo XLSX visible en este share:** el check list Anexo C (no el historial de concentradora). El Excel operativo grande sigue en `Pruebas MMI` local.
4. **Guest limitado:** subir a `primer-up3008` falla (“item isn't available”). Para ingesta fiable hace falta Graph API autenticada o sync local de esta carpeta.
5. **LIBRO SOMA 18.7 MB** sigue siendo el mejor candidato OCR del lote visible.

## Próximo paso recomendado

- Sincronizar `…/MMi/primer-up3008` a OneDrive local **o** descargar el check list + PDFs del lote 1 a `fixtures/corpus-ncc30/`.
- Correr `mmi.tools.preview_excel` sobre `Anexo C Check List….xlsx`.
- Confirmar si CAPACITACION / ANEXOS FRMGS deben volver a estar en el share.
