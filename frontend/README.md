# kanbai — frontend

SPA React 19 con HeroUI v3 sobre Tailwind v4. Las convenciones están en el
[`AGENTS.md`](../AGENTS.md) de la raíz.

## Puesta en marcha

```bash
# Terminal 1, desde la raíz:
docker compose up -d db --wait
cd backend
uv run poe dev                   # la API en :8000

# Terminal 2, desde la raíz:
cd frontend
npm ci
npm run dev                      # http://localhost:5173
```

## Comandos

| Comando | Qué hace |
|---------|----------|
| `npm run dev` | Vite en `:5173`, con proxy de `/api` al backend |
| `npm run gen:api` | Regenera `src/api/schema.d.ts` desde `../backend/openapi.json` |
| `npm run lint` / `typecheck` / `test` | Pasos sueltos de calidad |
| `npm run check` | lint + typecheck + test |
| `npm run build` | Bundle de producción |

## Estilos

El orden de capas de `src/styles/global.css` no es decorativo: `bootstrap` va
**después** de `base` porque el preflight de Tailwind (`*{margin:0;padding:0}`) borraría
los gutters de la rejilla, y **antes** de `components`/`utilities` para que HeroUI y
Tailwind ganen cualquier conflicto. De Bootstrap se usan solo `.row` y `.col-*`: el
contenedor de página es de Tailwind, porque `.container` es un nombre que Tailwind v4
también define.
