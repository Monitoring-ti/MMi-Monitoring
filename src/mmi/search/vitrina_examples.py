"""Componentes de ejemplo reutilizables en paginas vitrina interactivas."""

from __future__ import annotations

from html import escape
from typing import Any


def vitrina_example_card(cat: dict[str, Any]) -> str:
    chips: list[str] = []
    for ex in cat.get("examples") or ():
        search_only = ex.get("action") == "search"
        chip_cls = (
            "bg-green-50 text-green-900 border-green-200 hover:bg-green-100"
            if search_only
            else "bg-primary-fixed/30 text-primary border-primary-fixed hover:bg-primary-fixed/50"
        )
        action_attr = ' data-action="search"' if search_only else ""
        chips.append(
            f'<button type="button"{action_attr} data-q="{escape(ex["query"], quote=True)}" '
            f'title="{escape(ex["query"])}" '
            f'class="inline-flex items-center px-stack-sm py-1 rounded-lg border text-label-sm font-semibold {chip_cls} transition-colors">'
            f"{escape(ex['label'])}</button>"
        )
    return f"""
<article class="bg-surface-container-lowest p-stack-lg rounded-xl border border-outline/20 shadow-sm">
  <div class="flex items-start gap-stack-md mb-stack-md">
    <div class="w-10 h-10 rounded-xl bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-bold text-label-sm shrink-0">{escape(str(cat.get("icon", "?")))}</div>
    <div>
      <h3 class="text-body-lg font-bold text-primary">{escape(cat.get("title", ""))}</h3>
      <p class="text-label-sm text-on-surface-variant">{escape(cat.get("tag", ""))}</p>
    </div>
  </div>
  <p class="text-body-md text-on-surface-variant mb-stack-md">{escape(cat.get("note") or "")}</p>
  <div class="flex flex-wrap gap-stack-sm">{"".join(chips)}</div>
</article>"""
