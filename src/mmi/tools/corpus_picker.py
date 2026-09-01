"""Listado seleccionable del corpus: local + inventario SharePoint conocido.

Uso:
  .venv\\Scripts\\python -m mmi.tools.corpus_picker --serve
  Abrir http://127.0.0.1:8770/

Guarda la selección en out/process-manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Extensiones reconocidas por el pipeline (ver src/mmi/ingest/file_types.py)
from mmi.analysis.extract_index import load_extract_index, lookup_extract
from mmi.ingest.file_types import FILE_TYPES, phase0_for_extension

PROCESSABLE = {
    ext
    for ext, spec in FILE_TYPES.items()
    if spec.status in {"ready", "partial", "planned"}
}
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".cursor", "out"}


@dataclass
class CorpusItem:
    id: str
    name: str
    relative_path: str
    absolute_path: str | None
    source: str  # local | sharepoint
    extension: str
    size_bytes: int | None
    processable: bool
    notes: str = ""
    selected_default: bool = False
    processed: bool = False
    process_quality: str = ""
    extract_dir: str | None = None


def _file_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


def scan_local_roots(roots: list[Path], max_files: int = 5000) -> list[CorpusItem]:
    items: list[CorpusItem] = []
    for root in roots:
        if not root.exists():
            continue
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            # Evitar bucles / carpetas pesadas de sync
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and not d.startswith(".")
            ]
            for name in filenames:
                if len(items) >= max_files:
                    return items
                path = Path(dirpath) / name
                ext = path.suffix.lower()
                spec = FILE_TYPES.get(ext)
                proc = ext in PROCESSABLE
                notes = ""
                if spec and spec.status == "planned":
                    notes = f"Extractor pendiente ({spec.phase0}) — {spec.spec_doc or 'ver file-types-compatibility.md'}"
                elif spec and spec.status == "partial":
                    notes = spec.notes
                if ".vscode" in path.parts:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    size = None
                try:
                    rel = str(path.relative_to(root)).replace("\\", "/")
                except ValueError:
                    rel = path.name
                items.append(
                    CorpusItem(
                        id=_file_id(str(path)),
                        name=name,
                        relative_path=f"{root.name}/{rel}",
                        absolute_path=str(path),
                        source="local",
                        extension=ext or "(sin ext)",
                        size_bytes=size,
                        processable=proc,
                        notes=notes,
                        selected_default=proc and spec and spec.status == "ready" and ext not in {".md", ".txt"},
                    )
                )
    return items


def sharepoint_catalog() -> list[CorpusItem]:
    """Inventario visto en el share guest (docs/sharepoint-ncc30-inventory.md)."""
    base = "SharePoint/MMi/primer-up3008/00 DOCUMENTOS NCC30"
    rows = [
        ("1. NORMA/20180430 Documento SOMA (1).pdf", ".pdf", 7_870_000, "PDF SOMA"),
        ("1. NORMA/Anexos SGP-07MYC-GUIGS-00001 rev 4.docx", ".docx", 1_970_000, ""),
        ("1. NORMA/LIBRO SOMA DIGITAL FINAL.pdf", ".pdf", 18_700_000, "candidato OCR"),
        ("1. NORMA/NCC-030_REV02.pdf", ".pdf", 1_170_000, "norma"),
        (
            "1. NORMA/SGP-07MYC-GUIGS-00001 GUIA MANTENIBILIDAD Y CONFIABILIDAD EN PROYECTOS Rev 6.pdf",
            ".pdf",
            8_870_000,
            "guía vigente",
        ),
        ("1. NORMA/SGP-07MYC-GUIGS-00001 Rev 5.pdf", ".pdf", 8_480_000, "versión anterior"),
        (
            "1. NORMA/1. VARIOS/Anexo C Check List SGP-07MYC-GUIGS-00001.xlsx",
            ".xlsx",
            43_200,
            "Excel checklist — prioridad",
        ),
        ("1. NORMA/1. VARIOS/SGP-07MYC-CRTTC-00002 REV1.pdf", ".pdf", 483_000, ""),
        ("1. NORMA/1. VARIOS/SGP-07MYC-GUIGS-00001_REV4.pdf", ".pdf", 3_060_000, ""),
        ("1. NORMA/1. VARIOS/SGP-07MYC-PROGS-00009 TALLER M@C.pdf", ".pdf", 409_000, ""),
        (
            "1. NORMA/1. VARIOS/SGPD-07MYC-PROGS-0001 Procedimiento de Mantenibilidad y Confiabilidad en Estudios y Proyectos.pdf",
            ".pdf",
            1_590_000,
            "SOP",
        ),
        (
            "1. NORMA/1. VARIOS/SGPD-07MYC-PROGS-0001 Procedimiento de Mantenibilidad y Confiabilidad en Estudios y Proyectos BCK.pdf",
            ".pdf",
            1_590_000,
            "backup SOP",
        ),
    ]
    items: list[CorpusItem] = []
    for rel, ext, size, notes in rows:
        full = f"{base}/{rel}"
        items.append(
            CorpusItem(
                id=_file_id(full),
                name=Path(rel).name,
                relative_path=full,
                absolute_path=None,
                source="sharepoint",
                extension=ext,
                size_bytes=size,
                processable=True,
                notes=notes or "solo online (guest); descarga o sync para procesar",
                selected_default=ext == ".xlsx" or "Rev 6" in rel or "PROGS-0001 Procedimiento" in rel and "BCK" not in rel,
            )
        )
    return items


def build_inventory(local_roots: list[Path]) -> list[CorpusItem]:
    items = scan_local_roots(local_roots) + sharepoint_catalog()
    seen: set[str] = set()
    unique: list[CorpusItem] = []
    for it in items:
        key = (it.absolute_path or it.relative_path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    unique.sort(key=lambda x: (x.source != "local", x.relative_path.lower()))
    return unique


def attach_processing_status(
    items: list[CorpusItem],
    *,
    extract_roots: list[Path] | None = None,
    previous_selected_ids: set[str] | None = None,
) -> list[CorpusItem]:
    """Marca archivos ya extraídos y restaura la selección previa del análisis."""
    index = load_extract_index(extract_roots)
    prev = previous_selected_ids
    for it in items:
        hit = lookup_extract(it.absolute_path, index)
        if hit:
            it.processed = True
            it.process_quality = str(hit.get("quality") or "")
            it.extract_dir = hit.get("extract_dir")
            extra = f"Procesado ({it.process_quality or 'ok'})"
            it.notes = f"{it.notes} · {extra}".strip(" ·") if it.notes else extra
        if prev is not None:
            it.selected_default = it.id in prev and it.processable
    return items


def load_previous_selected_ids(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids: set[str] = set()
    for row in data.get("files") or []:
        include = row.get("include_in_analysis")
        if include is False:
            continue
        fid = row.get("id")
        if fid:
            ids.add(fid)
    return ids


def _fmt_size(n: int | None) -> str:
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"


@dataclass
class FolderNode:
    name: str
    full_path: str
    files: list[CorpusItem]
    subfolders: dict[str, FolderNode]

    def file_count(self) -> int:
        return len(self.files) + sum(s.file_count() for s in self.subfolders.values())

    def processed_count(self) -> int:
        n = sum(1 for f in self.files if f.processed)
        return n + sum(s.processed_count() for s in self.subfolders.values())


def build_folder_tree(items: list[CorpusItem]) -> list[FolderNode]:
    roots: dict[str, FolderNode] = {}

    def ensure_child(parent: dict[str, FolderNode], name: str, full_path: str) -> FolderNode:
        if name not in parent:
            parent[name] = FolderNode(name=name, full_path=full_path, files=[], subfolders={})
        return parent[name]

    for it in items:
        parts = it.relative_path.replace("\\", "/").split("/")
        parent_map = roots
        accumulated = ""
        leaf: FolderNode | None = None
        for part in parts[:-1]:
            accumulated = f"{accumulated}/{part}" if accumulated else part
            leaf = ensure_child(parent_map, part, accumulated)
            parent_map = leaf.subfolders
        if leaf is not None:
            leaf.files.append(it)

    def sort_tree(node: FolderNode) -> None:
        node.files.sort(key=lambda x: x.name.lower())
        for child in node.subfolders.values():
            sort_tree(child)

    top = sorted(roots.values(), key=lambda n: (n.name.lower()))
    for node in top:
        sort_tree(node)
    return top


def _unique_extensions(items: list[CorpusItem]) -> list[str]:
    exts = sorted({it.extension for it in items if it.extension and it.extension != "(sin ext)"})
    return exts


def _unique_locations(items: list[CorpusItem]) -> list[str]:
    locs: set[str] = set()
    for it in items:
        parts = it.relative_path.replace("\\", "/").split("/")
        if parts:
            locs.add(parts[0])
    return sorted(locs, key=str.lower)


def _filter_options(options: list[str], *, all_label: str) -> str:
    rows = [f'<option value="">{all_label}</option>']
    rows.extend(f'<option value="{_esc(o)}">{_esc(o)}</option>' for o in options)
    return "\n      ".join(rows)


def _render_file_row(it: CorpusItem) -> str:
    checked = "checked" if it.selected_default and it.processable else ""
    disabled = "" if it.processable else "disabled"
    badge = "local" if it.source == "local" else "sharepoint"
    proc = "sí" if it.processable else "no"
    abs_attr = it.absolute_path or ""
    processed = "yes" if it.processed else "no"
    parts = it.relative_path.replace("\\", "/").split("/")
    root = parts[0] if parts else ""
    size_bytes = it.size_bytes if it.size_bytes is not None else -1
    if it.processed:
        q = it.process_quality or "ok"
        qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(q, "ok")
        estado = f'<span class="badge {qclass}">Procesado · {_esc(q)}</span>'
    else:
        estado = '<span class="badge pending">Pendiente</span>'
    return f"""<div class="file-row" data-ext="{it.extension}" data-source="{it.source}" data-proc="{proc}"
     data-processed="{processed}" data-quality="{_esc(it.process_quality)}"
     data-root="{_esc(root)}" data-name="{_esc(it.name.lower())}" data-size="{size_bytes}"
     data-folder="{_esc('/'.join(parts[:-1]))}">
  <input type="checkbox" name="sel" value="{it.id}" data-abs="{_esc(abs_attr)}"
       data-rel="{_esc(it.relative_path)}" data-name="{_esc(it.name)}"
       data-source="{it.source}" data-ext="{it.extension}" {checked} {disabled}/>
  <span class="badge {badge}">{it.source}</span>
  <span class="name">{_esc(it.name)}</span>
  <span class="estado">{estado}</span>
  <span class="path">{_esc(it.relative_path)}</span>
  <span class="ext">{it.extension}</span>
  <span class="size">{_fmt_size(it.size_bytes)}</span>
  <span class="notes">{_esc(it.notes)}</span>
</div>"""


def _render_folder_node(node: FolderNode, depth: int = 0, open_depth: int = 2) -> str:
    open_attr = " open" if depth < open_depth else ""
    count = node.file_count()
    processed = node.processed_count()
    subfolders = "".join(
        _render_folder_node(child, depth + 1, open_depth)
        for child in sorted(node.subfolders.values(), key=lambda n: n.name.lower())
    )
    files = "".join(_render_file_row(it) for it in node.files)
    return f"""<details class="folder" data-path="{_esc(node.full_path)}" data-depth="{depth}"{open_attr}>
  <summary>
    <span class="folder-name">{_esc(node.name)}</span>
    <span class="folder-count">{count} archivo{"s" if count != 1 else ""} · {processed} procesado{"s" if processed != 1 else ""}</span>
  </summary>
  <div class="folder-body">
    {subfolders}
    {files}
  </div>
</details>"""


def render_html(items: list[CorpusItem]) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css

    tree_html = "".join(_render_folder_node(node, depth=0, open_depth=3) for node in build_folder_tree(items))

    local_n = sum(1 for i in items if i.source == "local")
    sp_n = sum(1 for i in items if i.source == "sharepoint")
    proc_n = sum(1 for i in items if i.processable)
    done_n = sum(1 for i in items if i.processed)
    selected_n = sum(1 for i in items if i.selected_default and i.processable)
    ext_options = _filter_options(_unique_extensions(items), all_label="Todos los tipos")
    loc_options = _filter_options(_unique_locations(items), all_label="Todas las ubicaciones")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>MMI — Selección de corpus</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 20px 24px 48px; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 6px; }}
  .meta {{ color: #9a9a9a; margin-bottom: 14px; }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }}
  input[type=search], select {{ padding: 8px 10px; border-radius: 6px; border: 1px solid #444;
    background: #111; color: #eee; }}
  button {{ padding: 8px 14px; border-radius: 6px; border: 1px solid #444; background: #2a2a2a;
    color: #eee; cursor: pointer; }}
  button.primary {{ background: #2b5cff; border-color: #2b5cff; font-weight: 600; }}
  button:hover {{ filter: brightness(1.1); }}
  .tree-header {{ display: grid; grid-template-columns: 28px 72px 1.1fr 140px 1.6fr 56px 72px 1fr;
    gap: 8px; padding: 8px 10px; font-size: 0.75rem; color: #9a9a9a; border-bottom: 1px solid #333;
    position: sticky; top: 0; background: #202020; z-index: 1; }}
  .tree {{ font-size: 0.85rem; }}
  details.folder {{ margin: 2px 0; border-left: 2px solid #333; margin-left: 4px; }}
  details.folder > summary {{
    cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px;
    padding: 6px 8px; border-radius: 4px; user-select: none;
  }}
  details.folder > summary::-webkit-details-marker {{ display: none; }}
  details.folder > summary::before {{ content: "▸"; color: #8ab4ff; width: 1em; flex-shrink: 0; }}
  details.folder[open] > summary::before {{ content: "▾"; }}
  details.folder > summary:hover {{ background: #252525; }}
  .folder-name {{ font-weight: 600; color: #d4e4ff; }}
  .folder-count {{ color: #7a7a7a; font-size: 0.78rem; }}
  .folder-body {{ padding-left: 12px; }}
  .file-row {{
    display: grid; grid-template-columns: 28px 72px 1.1fr 140px 1.6fr 56px 72px 1fr;
    gap: 8px; align-items: start; padding: 6px 8px; border-bottom: 1px solid #2a2a2a;
  }}
  .file-row:hover {{ background: #222; }}
  .file-row[data-processed="yes"] {{ background: #162016; }}
  .badge {{ font-size: 0.72rem; padding: 2px 7px; border-radius: 999px; display: inline-block; }}
  .badge.local {{ background: #1f3d2a; color: #8fddb0; }}
  .badge.sharepoint {{ background: #1a2f4d; color: #8ab4ff; }}
  .badge.ok {{ background: #1a3d1a; color: #8ae68a; }}
  .badge.warn {{ background: #3d351a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .badge.pending {{ background: #2a2a2a; color: #9a9a9a; }}
  .name {{ font-weight: 600; }}
  .path {{ color: #9a9a9a; word-break: break-all; font-size: 0.78rem; }}
  .ext, .size {{ color: #aaa; }}
  .notes {{ color: #888; font-size: 0.78rem; }}
  #status {{ margin-top: 12px; padding: 10px 12px; border-radius: 6px; background: #202020;
    border: 1px solid #333; white-space: pre-wrap; }}
  #status.ok {{ border-color: #2d6a45; }}
  #status.err {{ border-color: #8a3a3a; }}
  .hidden {{ display: none !important; }}
  details.folder.filter-hide {{ display: none; }}
  .toolbar label {{ font-size: 0.78rem; color: #9a9a9a; display: flex; align-items: center; gap: 4px; }}
  .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }}
  #visible-count {{ font-size: 0.82rem; color: #8ab4ff; margin-left: auto; }}
{review_nav_css()}
</style>
</head>
<body>
  {render_review_nav("corpus")}
  <h1>Selección de corpus a procesar</h1>
  <p class="meta">Local: {local_n} · SharePoint: {sp_n} · Procesables: {proc_n} ·
     Ya extraídos en este directorio: <b>{done_n}</b> · Marcados para análisis: {selected_n}.
     Marca <b>sí</b> (checkbox) los que entran al análisis; los no marcados quedan fuera.</p>
  <p class="legend">Verde oscuro = ya procesado (Fase 0). El checkbox decide si entra otra vez al análisis.</p>
  <div class="filter-row">
    <label>Buscar<input id="q" type="search" placeholder="Nombre o ruta…" style="min-width:220px"/></label>
    <label>Tipo<select id="ext">{ext_options}</select></label>
    <label>Ubicación<select id="ubicacion">{loc_options}</select></label>
    <label>Fuente<select id="src">
      <option value="">Todas</option>
      <option value="local">local</option>
      <option value="sharepoint">sharepoint</option>
    </select></label>
    <label>Estado<select id="estado">
      <option value="">Todos</option>
      <option value="yes">Procesados</option>
      <option value="no">Pendientes</option>
    </select></label>
    <label>Orden<select id="sort">
      <option value="tree">Carpeta (default)</option>
      <option value="name-asc">Nombre A → Z</option>
      <option value="name-desc">Nombre Z → A</option>
      <option value="size-asc">Tamaño ↑</option>
      <option value="size-desc">Tamaño ↓</option>
    </select></label>
    <span id="visible-count"></span>
  </div>
  <div class="toolbar">
    <button type="button" id="expand-all">Expandir todo</button>
    <button type="button" id="collapse-all">Colapsar todo</button>
    <button type="button" id="all-proc">Seleccionar procesables visibles</button>
    <button type="button" id="pending-only">Solo pendientes visibles</button>
    <button type="button" id="none">Limpiar</button>
    <button type="button" class="primary" id="save">Guardar selección (sí/no análisis)</button>
  </div>
  <div class="tree-header">
    <span></span><span>Fuente</span><span>Nombre</span><span>Estado</span><span>Ruta</span><span>Ext</span><span>Tamaño</span><span>Notas</span>
  </div>
  <div class="tree" id="tree">
    {tree_html}
  </div>
  <div id="status">Marca los archivos que <b>sí</b> van al análisis y pulsa Guardar.
     Se escribe <code>out/process-manifest.json</code> con incluidos y excluidos.</div>
<script>
const q = document.getElementById('q');
const ext = document.getElementById('ext');
const ubicacion = document.getElementById('ubicacion');
const src = document.getElementById('src');
const estado = document.getElementById('estado');
const sort = document.getElementById('sort');
const status = document.getElementById('status');
const visibleCount = document.getElementById('visible-count');

function visibleFiles() {{
  return [...document.querySelectorAll('.file-row')].filter(el => !el.classList.contains('hidden'));
}}

function applySort() {{
  const mode = sort.value;
  document.querySelectorAll('details.folder').forEach(folder => {{
    const body = folder.querySelector(':scope > .folder-body');
    if (!body) return;
    const rows = [...body.querySelectorAll(':scope > .file-row')];
    if (mode === 'tree' || rows.length < 2) return;
    rows.sort((a, b) => {{
      if (mode === 'name-asc') return a.dataset.name.localeCompare(b.dataset.name);
      if (mode === 'name-desc') return b.dataset.name.localeCompare(a.dataset.name);
      const sa = parseInt(a.dataset.size || '-1', 10);
      const sb = parseInt(b.dataset.size || '-1', 10);
      if (mode === 'size-asc') return sa - sb;
      if (mode === 'size-desc') return sb - sa;
      return 0;
    }});
    rows.forEach(r => body.appendChild(r));
  }});
}}

function updateVisibleCount() {{
  const n = visibleFiles().length;
  const total = document.querySelectorAll('.file-row').length;
  visibleCount.textContent = n === total ? `${{total}} archivos` : `${{n}} / ${{total}} visibles`;
}}

function applyFilter() {{
  const qq = q.value.toLowerCase().trim();
  const e = ext.value;
  const loc = ubicacion.value;
  const s = src.value;
  const st = estado.value;
  const hasFilter = Boolean(qq || e || loc || s || st);

  document.querySelectorAll('.file-row').forEach(row => {{
    const text = row.innerText.toLowerCase();
    const okQ = !qq || text.includes(qq);
    const okE = !e || row.dataset.ext === e;
    const okLoc = !loc || row.dataset.root === loc;
    const okS = !s || row.dataset.source === s;
    const okSt = !st || row.dataset.processed === st;
    row.classList.toggle('hidden', !(okQ && okE && okLoc && okS && okSt));
  }});

  document.querySelectorAll('details.folder').forEach(folder => {{
    const summaryText = folder.querySelector('summary')?.innerText.toLowerCase() || '';
    const folderMatch = qq && summaryText.includes(qq);
    const visibleFilesInside = [...folder.querySelectorAll('.file-row')].some(r => !r.classList.contains('hidden'));
    const visibleSubfolders = [...folder.querySelectorAll(':scope > .folder-body > details.folder')]
      .some(f => !f.classList.contains('filter-hide'));
    const show = !hasFilter || folderMatch || visibleFilesInside || visibleSubfolders;
    folder.classList.toggle('filter-hide', !show);
    if (hasFilter && show && (folderMatch || visibleFilesInside)) folder.open = true;
  }});

  applySort();
  updateVisibleCount();
}}
q.addEventListener('input', applyFilter);
ext.addEventListener('change', applyFilter);
ubicacion.addEventListener('change', applyFilter);
src.addEventListener('change', applyFilter);
estado.addEventListener('change', applyFilter);
sort.addEventListener('change', applyFilter);
applyFilter();

document.getElementById('expand-all').onclick = () => {{
  document.querySelectorAll('details.folder').forEach(d => {{ d.open = true; }});
}};
document.getElementById('collapse-all').onclick = () => {{
  document.querySelectorAll('details.folder').forEach(d => {{ d.open = false; }});
}};

document.getElementById('all-proc').onclick = () => {{
  visibleFiles().forEach(row => {{
    const cb = row.querySelector('input[type=checkbox]');
    if (cb && !cb.disabled) cb.checked = true;
  }});
}};
document.getElementById('pending-only').onclick = () => {{
  visibleFiles().forEach(row => {{
    const cb = row.querySelector('input[type=checkbox]');
    if (cb && !cb.disabled) cb.checked = row.dataset.processed === 'no';
  }});
}};
document.getElementById('none').onclick = () => {{
  document.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = false);
}};

function allPayload() {{
  return [...document.querySelectorAll('input[name=sel]')].map(cb => ({{
    id: cb.value,
    name: cb.dataset.name,
    relative_path: cb.dataset.rel,
    absolute_path: cb.dataset.abs || null,
    source: cb.dataset.source,
    extension: cb.dataset.ext,
    ready: Boolean(cb.dataset.abs),
    include_in_analysis: cb.checked && !cb.disabled,
    processed: cb.closest('.file-row')?.dataset.processed === 'yes',
    process_quality: cb.closest('.file-row')?.dataset.quality || '',
  }}));
}}

function downloadFallback(files) {{
  const included = files.filter(f => f.include_in_analysis);
  const payload = {{
    created_at: new Date().toISOString(),
    source: 'corpus-picker',
    count: included.length,
    excluded_count: files.length - included.length,
    processed_count: files.filter(f => f.processed).length,
    local_ready: included.filter(f => f.absolute_path).length,
    online_only: included.filter(f => !f.absolute_path).length,
    files: files,
  }};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {{type: 'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'process-manifest.json';
  a.click();
  status.className = 'ok';
  status.textContent = 'Descargado process-manifest.json.\\n' +
    included.length + ' sí al análisis · ' + (files.length - included.length) + ' no.';
}}

document.getElementById('save').onclick = async () => {{
  const files = allPayload();
  status.className = '';
  status.textContent = 'Guardando…';
  try {{
    const res = await fetch('/api/manifest', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ files }}),
    }});
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    status.className = 'ok';
    status.textContent = `Guardado: ${{data.path}}\\n` +
      `${{data.count}} sí al análisis · ${{data.excluded_count}} no · ` +
      `${{data.processed_count}} ya procesados en el directorio.`;
  }} catch (err) {{
    downloadFallback(files);
  }}
}};
</script>
</body>
</html>
"""
def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_manifest(rows: list[dict], out_path: Path, inventory: list[CorpusItem]) -> dict:
    by_id = {i.id: i for i in inventory}
    files = []
    included = 0
    excluded = 0
    processed_count = 0
    local_ready = 0
    online_only = 0
    for row in rows:
        item = by_id.get(row.get("id", ""))
        abs_path = row.get("absolute_path") or (item.absolute_path if item else None)
        include = row.get("include_in_analysis")
        if include is None:
            include = True
        include = bool(include)
        processed = bool(row.get("processed"))
        if item and item.processed:
            processed = True
        quality = row.get("process_quality") or (item.process_quality if item else "")
        ext = row.get("extension") or (item.extension if item else "")
        if include:
            included += 1
            if abs_path:
                local_ready += 1
            else:
                online_only += 1
        else:
            excluded += 1
        if processed:
            processed_count += 1
        files.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "relative_path": row.get("relative_path"),
                "absolute_path": abs_path,
                "source": row.get("source"),
                "extension": ext,
                "ready": bool(abs_path),
                "include_in_analysis": include,
                "processed": processed,
                "process_quality": quality or None,
                "phase0": phase0_for_extension(ext) if ext else None,
                "suggested_tipo": _suggest_tipo(row.get("name", ""), ext),
            }
        )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "corpus-picker",
        "count": included,
        "excluded_count": excluded,
        "processed_count": processed_count,
        "local_ready": local_ready,
        "online_only": online_only,
        "files": files,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(out_path),
        "count": included,
        "excluded_count": excluded,
        "processed_count": processed_count,
        "local_ready": local_ready,
        "online_only": online_only,
    }


def _suggest_tipo(name: str, ext: str) -> str:
    n = name.lower()
    if ext in {".xlsx", ".xls", ".csv"}:
        return "tabla"
    if ext == ".pptx":
        return "presentacion"
    if "sop" in n or "procedimiento" in n or "progs" in n:
        return "sop"
    if "guigs" in n or "guia" in n:
        return "guia"
    if "ncc" in n or "norma" in n:
        return "norma"
    if "fmeca" in n or "rcm" in n:
        return "otro"
    return "otro"


def make_handler(inventory: list[CorpusItem], manifest_path: Path):
    html = render_html(inventory)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"[picker] {args[0]}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/inventory":
                payload = json.dumps([asdict(i) for i in inventory], ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/manifest":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                result = write_manifest(
                    data.get("files") or data.get("selected") or [],
                    manifest_path,
                    inventory,
                )
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:  # noqa: BLE001
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    return Handler


def default_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        repo / "ODS1 TORR ENF DCH",
        repo / "fixtures",
        repo / "corpus",
        home / "OneDrive - Monitoring SPA" / "Pruebas MMI",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Listado y selección de corpus MMI")
    parser.add_argument("--serve", action="store_true", help="Abrir UI en http://127.0.0.1:PORT")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="Carpeta local extra a escanear (repetible)",
    )
    parser.add_argument(
        "--write-html",
        type=Path,
        help="Escribe un HTML estático (sin servidor) para revisar/seleccionar",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("out/process-manifest.json"),
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Solo imprimir inventario JSON por stdout",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[3]
    roots = default_roots(repo)
    if args.root:
        roots = list(args.root) + [repo / "fixtures"]

    inventory = build_inventory(roots)
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    inventory = attach_processing_status(
        inventory,
        previous_selected_ids=load_previous_selected_ids(manifest_path) or None,
    )
    done = sum(1 for i in inventory if i.processed)
    print(f"Inventario: {len(inventory)} items · {done} ya procesados")
    for it in inventory[:40]:
        mark = "+" if it.processable else "-"
        proc = " procesado" if it.processed else ""
        print(f"  {mark} [{it.source}]{proc} {it.relative_path}")
    if len(inventory) > 40:
        print(f"  … y {len(inventory) - 40} más")

    if args.write_html:
        args.write_html.parent.mkdir(parents=True, exist_ok=True)
        args.write_html.write_text(render_html(inventory), encoding="utf-8")
        print(f"HTML -> {args.write_html.resolve()}")
        return 0

    if args.dump:
        print(json.dumps([asdict(i) for i in inventory], ensure_ascii=False, indent=2))
        return 0

    if args.serve:
        handler = make_handler(inventory, manifest_path.resolve())
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"Abre http://127.0.0.1:{args.port}/")
        print(f"Manifest -> {args.manifest.resolve()}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDetenido.")
        return 0

    # Por defecto: generar HTML en out/ para abrir ya
    out_html = repo / "out" / "corpus-picker.html"
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(render_html(inventory), encoding="utf-8")
    print(f"HTML -> {out_html}")
    print("Opcional: --serve para guardar manifest via API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
