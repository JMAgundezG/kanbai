# Vista del tablero · TASK-08

La página inicial lista los tableros del actor y enlaza a `/boards/:boardId`.
La vista muestra las columnas y tarjetas con HeroUI y la rejilla Bootstrap
(`row g-4`, `col-12 col-md`). Contempla carga, error, ausencia de columnas y
«Sin tarjetas» en cada columna vacía.

Cada columna usa un `GridList` de React Aria con arrastre independiente. Con ratón
se arrastra la tarjeta; con teclado se enfoca su asa (flecha derecha desde la fila),
Intro inicia el movimiento, Tab cambia de destino e Intro suelta. Escape cancela.
Las instrucciones accesibles se anuncian en español.

`POST /api/v1/boards/{board_id}/cards/{card_id}/move` recibe la columna y el índice
destino. TanStack Query actualiza la caché inmediatamente, restaura el snapshot
si falla y consulta de nuevo las tarjetas al terminar. La interfaz impide nuevos
arrastres hasta completar esa reconciliación para evitar reversiones concurrentes.
Los errores del backend, incluido el límite WIP, se muestran mediante un aviso. Un
404 al mover se convierte en un mensaje genérico para no revelar detalles del recurso.

La feature `board` consume los tipos generados del OpenAPI; no cambia el contrato
ni añade modelos o migraciones. `BoardCard` solo representa sus props.
`react-aria-components` es una dependencia directa justificada en la spec. El asa
usa su `Button` para integrarse con el contexto del slot `drag` de `GridListItem`.

## Límites actuales

Se carga una página de hasta 100 tableros, columnas o tarjetas por consulta, como
se acordó en la spec. No hay creación/edición desde esta pantalla, detalle de
tarjeta ni actualizaciones en tiempo real.

## Verificación de cierre (2026-09-09)

- Backend: `uv run poe check`, 111 pruebas correctas; Ruff y Mypy correctos.
- Frontend: `npm run check`, 33 pruebas en 8 archivos; ESLint y TypeScript correctos.
- Producción: `npm run build` correcto, con aviso de chunk mayor de 500 kB.
- Navegador con API real: ratón y teclado persisten tras recargar; rechazo WIP
  revierte y avisa; tablero vacío y convivencia visual de rejilla/HeroUI correctos.
- Revisión independiente: un 404 al mover revierte la tarjeta y no expone el detalle
  que devolvió la API.

Plan y decisiones: [plan](../plans/plan-TASK-08.md),
[spec](../plans/spec-TASK-08.md).
