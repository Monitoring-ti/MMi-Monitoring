# Vitrina CSS (Tailwind precompilado)

Fuente: `web/vitrina/` → salida: `public/vitrina.css`.

```bash
npm run build:vitrina-css
# o desde web/vitrina:
npx tailwindcss@3.4.17 -c ./tailwind.config.js -i ./input.css -o ../../public/vitrina.css --minify
```

Commit `public/vitrina.css` tras cambiar clases en `src/mmi/web/*.py` o `src/mmi/search/*.py`.
