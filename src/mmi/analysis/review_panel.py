"""Panel de revisión asistida (OpenRouter) embebido en review.html."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from mmi.analysis.llm_review import REVIEW_MODELS


def load_saved_review(extract_dir: Path | None) -> dict[str, Any] | None:
    if not extract_dir:
        return None
    path = extract_dir / "ai-review.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _format_saved(saved: dict[str, Any]) -> str:
    parts: list[str] = []
    if saved.get("summary"):
        parts.append(str(saved["summary"]))
    issues = saved.get("issues") or []
    if issues:
        parts.append("\nProblemas:\n- " + "\n- ".join(str(i) for i in issues))
    recs = saved.get("recommendations") or []
    if recs:
        parts.append("\nRecomendaciones:\n- " + "\n- ".join(str(r) for r in recs))
    alts = saved.get("alternatives") or []
    if alts:
        parts.append("\nAlternativas: " + ", ".join(str(a) for a in alts))
    if not parts and saved.get("raw"):
        parts.append(str(saved["raw"])[:4000])
    return "\n".join(parts) or json.dumps(saved, ensure_ascii=False, indent=2)


def render_review_ai_panel(
    document_name: str,
    quality: str,
    saved: dict[str, Any] | None = None,
) -> str:
    name = escape(document_name)
    qclass = {"pass": "ok", "review": "warn", "reject": "bad", "error": "bad"}.get(quality, "warn")
    model_opts = "".join(
        f'<option value="{escape(m["id"])}">{escape(m["label"])}</option>' for m in REVIEW_MODELS
    )
    saved_text = escape(_format_saved(saved)) if saved else ""
    saved_meta = ""
    if saved:
        saved_meta = escape(
            f"Modelo: {saved.get('model', '?')} · Veredicto: {saved.get('verdict', '?')} · "
            f"Sugerido: {saved.get('suggested_quality', '?')}"
        )
    suggested_raw = str((saved or {}).get("suggested_quality") or (saved or {}).get("verdict") or "")

    return f"""
<section class="ai-review card" id="ai-review" data-document="{name}" data-quality="{escape(quality)}">
  <h2>Revisión asistida (OpenRouter)</h2>
  <p class="meta">Calidad Fase 0: <span class="badge {qclass}">{escape(quality)}</span>
     · Evalúa si conviene indexar, re-extraer o excluir.</p>
  <div class="ai-toolbar">
    <label for="ai-model">Modelo</label>
    <select id="ai-model">{model_opts}</select>
    <button type="button" class="btn-ai primary" id="ai-run">Analizar con IA</button>
    <button type="button" class="btn-ai" id="ai-reextract">Re-extraer</button>
    <button type="button" class="btn-ai" id="ai-apply">Aplicar calidad sugerida</button>
    <button type="button" class="btn-ai bad" id="ai-not-relevant">No relevante</button>
    <button type="button" class="btn-ai warn" id="ai-verify">Verificar (foto/manuscrito)</button>
    <button type="button" class="btn-ai warn" id="ai-exclude">Excluir del análisis</button>
  </div>
  <p class="ai-status" id="ai-status">{saved_meta}</p>
  <pre class="ai-output" id="ai-output">{saved_text}</pre>
</section>
<style>
  .ai-review.card {{
    border-color: #3a4a6a; background: #1a2233;
  }}
  .ai-review h2 {{ font-size: 1.05rem; margin: 0 0 8px; }}
  .ai-toolbar {{
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 10px 0;
  }}
  .ai-toolbar label {{ color: #9a9a9a; font-size: 0.82rem; }}
  .ai-toolbar select {{
    padding: 6px 8px; border-radius: 6px; border: 1px solid #444;
    background: #111; color: #eee; max-width: 280px;
  }}
  .btn-ai {{
    padding: 6px 12px; border-radius: 6px; border: 1px solid #444;
    background: #2a2a2a; color: #eee; cursor: pointer; font-size: 0.8rem;
  }}
  .btn-ai.primary {{ background: #2b5cff; border-color: #2b5cff; }}
  .btn-ai.warn {{ border-color: #6a3a3a; color: #e6a8a8; }}
  .btn-ai.bad {{ border-color: #5a2a2a; color: #e68a8a; }}
  .btn-ai:hover {{ filter: brightness(1.08); }}
  .ai-status {{ color: #9a9a9a; font-size: 0.82rem; min-height: 1.2em; }}
  .ai-output {{
    white-space: pre-wrap; word-break: break-word; font-size: 0.82rem;
    background: #141414; border: 1px solid #333; border-radius: 6px;
    padding: 12px; max-height: 320px; overflow: auto; margin: 0;
  }}
</style>
<script>
(function reviewAiPanel() {{
  const root = document.getElementById('ai-review');
  if (!root) return;
  const docName = root.dataset.document;
  const statusEl = document.getElementById('ai-status');
  const outEl = document.getElementById('ai-output');
  const modelSel = document.getElementById('ai-model');
  let suggested = {json.dumps(suggested_raw)};

  function showReview(row) {{
    suggested = row.suggested_quality || row.verdict || suggested;
    statusEl.textContent = (row.model ? 'Modelo: ' + row.model + ' · ' : '')
      + (row.verdict ? 'Veredicto: ' + row.verdict + ' · ' : '')
      + (row.suggested_quality ? 'Sugerido: ' + row.suggested_quality : '');
    const parts = [];
    if (row.summary) parts.push(row.summary);
    if (row.issues && row.issues.length) parts.push('\\nProblemas:\\n- ' + row.issues.join('\\n- '));
    if (row.recommendations && row.recommendations.length)
      parts.push('\\nRecomendaciones:\\n- ' + row.recommendations.join('\\n- '));
    if (row.alternatives && row.alternatives.length)
      parts.push('\\nAlternativas: ' + row.alternatives.join(', '));
    outEl.textContent = parts.join('\\n') || row.raw || JSON.stringify(row, null, 2);
  }}

  async function callApi(action, extra) {{
    if (window.location.protocol === 'file:') {{
      throw new Error('Abre la app con serve_local (http://127.0.0.1:8773), no como archivo local.');
    }}
    statusEl.textContent = 'Ejecutando…';
    const body = Object.assign({{
      action, names: [docName], force: true, delete_failed: true,
      model: modelSel.value,
    }}, extra || {{}});
    const r = await fetch('/api/ingestion-action', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(body),
    }});
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.statusText);
    return data;
  }}

  document.getElementById('ai-run').addEventListener('click', async () => {{
    try {{
      const data = await callApi('ai_review');
      const row = (data.results && data.results[0]) || data;
      if (row.ok === false) throw new Error(row.error || 'Error IA');
      showReview(row);
      statusEl.textContent += ' · guardado en ai-review.json';
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});

  document.getElementById('ai-reextract').addEventListener('click', async () => {{
    try {{
      await callApi('reextract');
      statusEl.textContent = 'Re-extracción OK · recargando…';
      setTimeout(() => location.reload(), 700);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});

  document.getElementById('ai-apply').addEventListener('click', async () => {{
    const q = ['pass','review','reject'].includes(suggested) ? suggested : 'review';
    try {{
      await callApi('apply_quality', {{ quality: q }});
      statusEl.textContent = 'Calidad → ' + q + ' · volviendo al dashboard…';
      setTimeout(() => {{ window.location.href = '../../review.html'; }}, 700);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});

  document.getElementById('ai-exclude').addEventListener('click', async () => {{
    if (!confirm('¿Excluir este documento del análisis?')) return;
    try {{
      await callApi('exclude');
      statusEl.textContent = 'Excluido · volviendo al dashboard…';
      setTimeout(() => {{ window.location.href = '../../review.html'; }}, 700);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});

  document.getElementById('ai-not-relevant').addEventListener('click', async () => {{
    if (!confirm('¿Marcar como no relevante y excluir del análisis?')) return;
    try {{
      await callApi('mark_not_relevant', {{
        note: 'No relevante: plantilla vacía / solo encabezados Excel',
      }});
      statusEl.textContent = 'No relevante · volviendo al dashboard…';
      setTimeout(() => {{ window.location.href = '../../review.html?status=reject'; }}, 700);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});

  document.getElementById('ai-verify').addEventListener('click', async () => {{
    try {{
      await callApi('mark_verify', {{
        note: 'Verificar: posible foto escaneada o texto manuscrito (OCR)',
      }});
      statusEl.textContent = 'Marcado verificar · recargando…';
      setTimeout(() => location.reload(), 700);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }});
}})();
</script>
"""


def review_back_link(depth: int = 2) -> str:
    from mmi.analysis.review_shell import render_review_nav

    return render_review_nav("document", depth=depth)
