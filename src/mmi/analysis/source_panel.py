"""Panel HTML: pegar enlace de carpeta remota para revisar archivos."""

from __future__ import annotations

from html import escape
from typing import Any


def render_source_link_panel(remote: dict[str, Any] | None = None) -> str:
    url = escape((remote or {}).get("url") or "")
    label = escape((remote or {}).get("label") or "")
    provider = (remote or {}).get("provider") or ""
    updated = escape((remote or {}).get("updated_at") or "")
    has_url = bool((remote or {}).get("url"))

    provider_label = {
        "sharepoint": "SharePoint",
        "onedrive": "OneDrive",
        "other": "Enlace web",
    }.get(provider, "")

    open_btn = (
        f'<a class="btn btn-open" id="open-remote" href="{url}" target="_blank" '
        f'rel="noopener">Abrir carpeta para revisar</a>'
        if has_url
        else '<span class="muted">Guarda un enlace para abrir la carpeta</span>'
    )

    meta = ""
    if has_url and updated:
        meta = f'<p class="source-meta">Guardado: {updated}'
        if provider_label:
            meta += f" · {escape(provider_label)}"
        meta += "</p>"

    return f"""
<section class="source-panel" id="source-panel">
  <div class="source-head">
    <h2>Revisar archivos en la nube</h2>
    <p class="source-hint">Pega el enlace de la carpeta <b>SharePoint</b> o <b>OneDrive</b> donde están los documentos.
       No hace falta sincronizar: abre la carpeta en el navegador para revisar el original.</p>
  </div>
  <div class="source-form">
    <label class="sr-only" for="remote-url">Enlace de la carpeta</label>
    <input id="remote-url" type="url" placeholder="https://…sharepoint.com/… o onedrive.live.com/…"
           value="{url}" autocomplete="off" spellcheck="false"/>
    <input id="remote-label" type="text" placeholder="Nombre (opcional, ej. 00 DOCUMENTOS NCC30)"
           value="{label}"/>
    <button type="button" class="btn-save" id="save-remote">Guardar enlace</button>
    {open_btn}
  </div>
  {meta}
  <p class="source-status" id="source-status"></p>
</section>
<style>
  .source-panel {{
    background: #202020; border: 1px solid #333; border-radius: 10px;
    padding: 16px 18px; margin-bottom: 20px;
  }}
  .source-head h2 {{ font-size: 1.05rem; margin: 0 0 6px; }}
  .source-hint {{ color: #9a9a9a; font-size: 0.85rem; margin: 0 0 12px; line-height: 1.45; }}
  .source-form {{
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  }}
  .source-form input[type=url] {{ flex: 2 1 320px; min-width: 200px; }}
  .source-form input[type=text] {{ flex: 1 1 180px; min-width: 140px; }}
  .source-form input {{
    padding: 9px 11px; border-radius: 6px; border: 1px solid #444;
    background: #111; color: #eee; font-size: 0.88rem;
  }}
  .btn-save {{
    padding: 9px 14px; border-radius: 6px; border: 1px solid #444;
    background: #2a2a2a; color: #eee; cursor: pointer; font-weight: 600;
  }}
  .btn-save:hover {{ filter: brightness(1.1); }}
  a.btn-open {{
    display: inline-block; color: #fff; background: #2b5cff; padding: 9px 14px;
    border-radius: 6px; text-decoration: none; font-size: 0.88rem; font-weight: 600;
  }}
  a.btn-open:hover {{ filter: brightness(1.1); }}
  .source-meta {{ color: #7a7a7a; font-size: 0.78rem; margin: 10px 0 0; }}
  .source-status {{ font-size: 0.82rem; margin: 8px 0 0; min-height: 1.2em; }}
  .source-status.ok {{ color: #8fddb0; }}
  .source-status.err {{ color: #e68a8a; }}
  .sr-only {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }}
</style>
<script>
(function() {{
  const urlInput = document.getElementById('remote-url');
  const labelInput = document.getElementById('remote-label');
  const statusEl = document.getElementById('source-status');
  const saveBtn = document.getElementById('save-remote');

  async function loadSaved() {{
    try {{
      let data = null;
      try {{
        const res = await fetch('/api/remote-source');
        if (res.ok) data = await res.json();
      }} catch (_) {{
        const res = await fetch('remote-source.json');
        if (res.ok) data = await res.json();
      }}
      if (!data || !data.url) return;
      urlInput.value = data.url;
      if (data.label) labelInput.value = data.label;
      updateOpenLink(data.url);
    }} catch (_) {{}}
  }}

  function updateOpenLink(url) {{
    let open = document.getElementById('open-remote');
    if (!open && url) {{
      const form = document.querySelector('.source-form');
      const a = document.createElement('a');
      a.id = 'open-remote';
      a.className = 'btn btn-open';
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = 'Abrir carpeta para revisar';
      form.appendChild(a);
      open = a;
    }}
    if (open) {{
      if (url) {{
        open.href = url;
        open.style.display = '';
      }} else {{
        open.style.display = 'none';
      }}
    }}
  }}

  saveBtn.addEventListener('click', async () => {{
    const url = urlInput.value.trim();
    if (!url) {{
      statusEl.className = 'source-status err';
      statusEl.textContent = 'Pega un enlace HTTPS de la carpeta.';
      return;
    }}
    statusEl.className = 'source-status';
    statusEl.textContent = 'Guardando…';
    const body = {{ url, label: labelInput.value.trim() }};
    try {{
      const res = await fetch('/api/remote-source', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
      }});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      updateOpenLink(data.url);
      statusEl.className = 'source-status ok';
      statusEl.textContent = 'Enlace guardado. Usa «Abrir carpeta» para revisar los archivos originales.';
    }} catch (_) {{
      try {{
        localStorage.setItem('mmi_remote_source', JSON.stringify(body));
        updateOpenLink(url);
        statusEl.className = 'source-status ok';
        statusEl.textContent = 'Guardado en este navegador (modo local). Abre la carpeta con el botón azul.';
      }} catch (err) {{
        statusEl.className = 'source-status err';
        statusEl.textContent = 'No se pudo guardar. Usa el servidor: python -m mmi.tools.serve_local';
      }}
    }}
  }});

  urlInput.addEventListener('keydown', e => {{
    if (e.key === 'Enter') saveBtn.click();
  }});

  loadSaved();
  try {{
    const local = localStorage.getItem('mmi_remote_source');
    if (local && !urlInput.value) {{
      const data = JSON.parse(local);
      if (data.url) {{
        urlInput.value = data.url;
        if (data.label) labelInput.value = data.label;
        updateOpenLink(data.url);
      }}
    }}
  }} catch (_) {{}}
}})();
</script>
"""
