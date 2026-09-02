"""Verifica hrefs internos de paginas vitrina contra serve_local."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8773"
PAGES = ["/", "/index.html", "/pruebas.html", "/ejemplos.html", "/search.html", "/rag.html"]


def main() -> int:
    all_hrefs: set[str] = set()
    for page in PAGES:
        html = urllib.request.urlopen(BASE + page, timeout=15).read().decode("utf-8", "replace")
        nav = "vitrina" if "Consulta RAG" in html and "tailwindcss" in html else "dev"
        print(f"{page} nav={nav}")
        for match in re.finditer(r'href="([^"]+)"', html):
            href = match.group(1)
            if href.startswith(("#", "javascript:")):
                continue
            all_hrefs.add(href)

    failed: list[tuple[str, str]] = []
    for href in sorted(all_hrefs):
        if href.startswith("http"):
            continue
        url = href if href.startswith("/") else f"/{href}"
        try:
            with urllib.request.urlopen(BASE + url.split("?", 1)[0], timeout=15) as resp:
                if resp.status >= 400:
                    failed.append((href, str(resp.status)))
        except urllib.error.HTTPError as exc:
            failed.append((href, str(exc.code)))
        except Exception as exc:  # noqa: BLE001
            failed.append((href, str(exc)))

    print(f"links checked: {len(all_hrefs)}")
    if failed:
        print("FAILED:")
        for item in failed:
            print(" ", item)
        return 1
    print("All internal links OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
