"""Página de verificación / acceso demo (pública)."""

from __future__ import annotations

import json
from html import escape

from mmi.web.access_control import basic_auth_credentials
from mmi.web.vitrina import DEMO_AUTH_PASSWORD, DEMO_AUTH_USER, PROJECT_SHORT
from mmi.web.vitrina_shell import LOGO_HEADER, TAILWIND_CONFIG


def demo_credentials_for_display() -> tuple[str, str]:
    creds = basic_auth_credentials()
    if creds:
        return creds
    return DEMO_AUTH_USER, DEMO_AUTH_PASSWORD


def render_acceso_html(*, next_path: str = "/ejemplos.html") -> str:
    user, password = demo_credentials_for_display()
    allowed = {
        "/ejemplos.html",
        "/pruebas.html",
        "/search.html",
        "/rag.html",
        "/index.html",
        "/",
    }
    next_safe = next_path if next_path in allowed else "/ejemplos.html"
    next_json = json.dumps(next_safe)

    return f"""<!DOCTYPE html>
<html lang="es" class="light">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow, noarchive"/>
<title>Verificación de acceso · MMI</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=block" rel="stylesheet"/>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script id="tailwind-config">try{{{TAILWIND_CONFIG}}}catch(_e){{}}</script>
<style>
  body {{ font-family: Montserrat, system-ui, sans-serif; }}
  .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
  dialog.auth-dialog::backdrop {{ background: rgba(11, 37, 69, 0.55); backdrop-filter: blur(3px); }}
  dialog.auth-dialog[open] {{ display: flex; flex-direction: column; margin: auto; }}
</style>
</head>
<body class="min-h-screen bg-background text-on-surface flex flex-col">
<header class="h-16 bg-surface flex items-center px-margin-mobile md:px-margin-desktop border-b border-outline/10 shadow-sm">
  <div class="bg-white rounded-lg p-1 shadow-sm">
    <img src="{LOGO_HEADER}" alt="Monitoring" class="h-8 w-auto object-contain"/>
  </div>
  <div class="ml-stack-md min-w-0">
    <h1 class="text-headline-md font-semibold text-primary truncate">Verificación de acceso</h1>
    <p class="text-body-md text-on-surface-variant">{escape(PROJECT_SHORT)}</p>
  </div>
</header>

<main class="flex-1 flex items-center justify-center p-margin-mobile md:p-margin-desktop">
  <div class="w-full max-w-lg bg-surface-container-lowest rounded-xl border border-outline/20 shadow-sm p-stack-lg text-center space-y-stack-md">
    <div class="mx-auto w-14 h-14 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center">
      <span class="material-symbols-outlined" style="font-size:28px">verified_user</span>
    </div>
    <h2 class="text-headline-md font-semibold text-primary">Se requiere autenticación</h2>
    <p class="text-body-md text-on-surface-variant">
      Para abrir ejemplos, búsqueda o consulta RAG debe identificarse.
      Pulse el botón para ver el <strong class="text-on-surface">usuario y contraseña de apoyo</strong>.
    </p>
    <button type="button" id="open-auth-modal"
      class="inline-flex items-center justify-center gap-stack-sm w-full sm:w-auto bg-primary text-on-primary px-stack-lg py-stack-md rounded-lg text-label-sm font-bold uppercase tracking-wider hover:opacity-95 transition-opacity">
      <span class="material-symbols-outlined" style="font-size:18px">key</span>
      Ver credenciales e ingresar
    </button>
    <p class="text-label-sm text-on-surface-variant">
      <a href="/" class="text-primary font-semibold hover:underline">Volver al inicio</a>
    </p>
  </div>
</main>

<dialog id="auth-dialog" class="auth-dialog w-[min(94vw,28rem)] rounded-xl border border-outline/20 bg-surface-container-lowest p-0 shadow-xl open:flex open:flex-col">
  <div class="flex items-start justify-between gap-stack-md p-stack-lg border-b border-outline/15 bg-surface">
    <div>
      <p class="text-label-sm uppercase tracking-wider text-on-surface-variant mb-base">Apoyo · demo</p>
      <h2 class="text-headline-md font-semibold text-primary">Credenciales de acceso</h2>
    </div>
    <button type="button" id="close-auth-modal" class="shrink-0 w-10 h-10 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-primary flex items-center justify-center" aria-label="Cerrar">
      <span class="material-symbols-outlined">close</span>
    </button>
  </div>
  <div class="p-stack-lg space-y-stack-md">
    <p class="text-body-md text-on-surface-variant">Use estos valores en los campos de abajo.</p>
    <div class="rounded-xl border border-primary/20 bg-primary-fixed/20 p-stack-md space-y-stack-sm">
      <div>
        <p class="text-label-sm uppercase tracking-wider text-on-surface-variant">Usuario (apoyo)</p>
        <p class="text-body-lg font-semibold text-primary break-all select-all">{escape(user)}</p>
      </div>
      <div>
        <p class="text-label-sm uppercase tracking-wider text-on-surface-variant">Contraseña (apoyo)</p>
        <p class="text-body-lg font-semibold text-primary font-data-tabular select-all">{escape(password)}</p>
      </div>
    </div>
    <form id="auth-form" class="space-y-stack-md">
      <label class="block text-left">
        <span class="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wider">Usuario</span>
        <input id="auth-user" name="user" type="text" autocomplete="username" required
          value="{escape(user)}"
          class="mt-base w-full rounded-lg border border-outline/30 bg-surface-container-low px-stack-md py-stack-sm text-body-md text-on-surface focus:border-primary focus:ring-1 focus:ring-primary"/>
      </label>
      <label class="block text-left">
        <span class="text-label-sm font-semibold text-on-surface-variant uppercase tracking-wider">Contraseña</span>
        <input id="auth-pass" name="password" type="password" autocomplete="current-password" required
          value="{escape(password)}"
          class="mt-base w-full rounded-lg border border-outline/30 bg-surface-container-low px-stack-md py-stack-sm text-body-md text-on-surface focus:border-primary focus:ring-1 focus:ring-primary"/>
      </label>
      <p id="auth-error" class="hidden text-body-md text-error font-semibold"></p>
      <button type="submit" id="auth-submit"
        class="w-full inline-flex items-center justify-center gap-stack-sm bg-primary text-on-primary px-stack-lg py-stack-md rounded-lg text-label-sm font-bold uppercase tracking-wider hover:opacity-95 transition-opacity disabled:opacity-50">
        Ingresar
      </button>
    </form>
  </div>
</dialog>

<script>
(function () {{
  var dlg = document.getElementById('auth-dialog');
  var nextPath = {next_json};
  var openBtn = document.getElementById('open-auth-modal');
  var closeBtn = document.getElementById('close-auth-modal');
  var form = document.getElementById('auth-form');
  var errEl = document.getElementById('auth-error');
  var submitBtn = document.getElementById('auth-submit');

  function openModal() {{
    if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
    else if (dlg) dlg.setAttribute('open', '');
  }}
  function closeModal() {{
    if (dlg && typeof dlg.close === 'function') dlg.close();
    else if (dlg) dlg.removeAttribute('open');
  }}

  if (openBtn) openBtn.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (dlg) dlg.addEventListener('click', function (e) {{ if (e.target === dlg) closeModal(); }});
  openModal();

  function basicHeader(user, pass) {{
    return 'Basic ' + btoa(unescape(encodeURIComponent(user + ':' + pass)));
  }}

  form.addEventListener('submit', function (e) {{
    e.preventDefault();
    errEl.classList.add('hidden');
    var user = document.getElementById('auth-user').value.trim();
    var pass = document.getElementById('auth-pass').value;
    if (!user || !pass) return;
    submitBtn.disabled = true;
    fetch('/api/auth/check', {{
      method: 'GET',
      headers: {{ 'Authorization': basicHeader(user, pass) }},
      credentials: 'same-origin'
    }}).then(function (res) {{
      if (!res.ok) throw new Error('Usuario o contraseña incorrectos');
      return new Promise(function (resolve, reject) {{
        var xhr = new XMLHttpRequest();
        xhr.open('GET', nextPath, true, user, pass);
        xhr.onload = function () {{
          if (xhr.status >= 200 && xhr.status < 400) resolve();
          else reject(new Error('No se pudo abrir la página protegida'));
        }};
        xhr.onerror = function () {{ reject(new Error('Error de red')); }};
        xhr.send();
      }});
    }}).then(function () {{
      location.href = nextPath;
    }}).catch(function (err) {{
      errEl.textContent = err.message || 'No autorizado';
      errEl.classList.remove('hidden');
      submitBtn.disabled = false;
    }});
  }});
}})();
</script>
</body></html>"""
