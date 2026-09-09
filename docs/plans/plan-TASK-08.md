# Plan · TASK-08 · Frontend: vista del tablero con arrastrar y soltar

**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** 2026-09-09
**Tarea:** [TASK-08](../tasks/TASK-08-frontend-tablero.md)

## Objetivo

Dar a kanbai su pantalla principal: el tablero con sus columnas y tarjetas, con
arrastrar y soltar accesible (también operable con teclado) para mover una tarjeta
entre columnas, con mutación optimista y reversión si la API falla.

## Enfoque

El backend (TASK-04/05/06) ya expone tableros, columnas y tarjetas con un movimiento
atómico (`POST /boards/{id}/cards/{id}/move`, recibe columna destino + índice). El
frontend (TASK-07) ya trae sesión, rutas protegidas y armazón. Este trabajo es
puramente de frontend: una nueva feature `board` que consume ese contrato.

**Librería de arrastrar y soltar**: `react-aria-components` (`useDragAndDrop` +
`GridList`/`GridListItem`), ya instalada como *peer dependency* de `@heroui/react`
(`react-aria-components@1.20.0` en `node_modules`, sin añadirla a `package.json` como
dependencia directa porque HeroUI ya la trae — se justifica en la spec si hace falta
declararla explícita). Es la que React Aria (en la que se apoya HeroUI) recomienda
para listas de arrastrar y soltar con teclado de serie: al enfocar una tarjeta y
pulsar Intro/Espacio entra en "modo arrastre por teclado", Tab/flechas mueven el
objetivo de soltado, Intro/Espacio confirma, Escape cancela — sin código propio de
teclado que mantener. Alternativas consideradas y descartadas: `@dnd-kit` (buena
librería, pero añade una dependencia nueva y duplica la accesibilidad por teclado
que React Aria ya da gratis conviviendo con HeroUI) y arrastrar y soltar nativo del
navegador (HTML5 DnD no es operable por teclado sin una reimplementación completa).

**Patrón de columnas independientes**: cada columna es su propio `GridList` con su
propia llamada a `useDragAndDrop` (no una única instancia compartida), cerrando sobre
el id de esa columna — así `onReorder` (mismo `GridList`) y `onInsert`/`onRootDrop`
(desde otra columna) saben siempre a qué columna de destino pertenecen sin más
estado. Detalle técnico completo en la spec.

**Alcance de navegación**: la tarea es la vista del tablero, no la gestión de
tableros. No existe todavía ninguna pantalla para listar o crear tableros
(ningún TASK anterior la cubre). Para que la vista sea alcanzable desde la UI,
`HomePage` pasa a listar los tableros del actor (`GET /api/v1/boards`, ya
consumido por primera vez) como enlaces a `/boards/:boardId`; crear un tablero
desde la interfaz queda fuera (no lo pide la tarea y el criterio de aceptación no
lo exige — se crean tableros de prueba directamente contra la API para verificar).

## Alcance

- Backend (`backend/src/kanbai/`): sin cambios. Los endpoints de boards/columns/cards
  ya existen (TASK-04/05/06).
- Contrato: `GET /api/v1/boards`, `GET .../columns`, `GET .../cards`,
  `POST .../cards/{id}/move` se consumen **por primera vez** desde el frontend →
  `npm run gen:api` regenera `frontend/src/api/schema.d.ts` con estos tipos.
- Frontend (`frontend/src/`):
  - `features/board/api.ts` — tipos derivados del schema, `boardKeys`, fetchers,
    `moveCard`.
  - `features/board/hooks.ts` — `useBoards`, `useBoard`, `useBoardColumns`,
    `useBoardCards`, `useMoveCard` (mutación optimista + reversión).
  - `features/board/components/` — `BoardColumnList` (GridList + drag and drop),
    `BoardCard` (tonta, sin llamadas a la API), estados de carga/vacío/error.
  - `routes/BoardPage.tsx` — nueva ruta `/boards/:boardId`.
  - `routes/HomePage.tsx` — editada: lista de tableros del actor.
  - `App.tsx` — añade la ruta `/boards/:boardId` bajo `ProtectedRoute`/`AppLayout`.

## Criterios de aceptación

- [x] Arrastrar una tarjeta a otra columna persiste el cambio y sobrevive a recargar.
- [x] La misma operación se puede completar solo con teclado.
- [x] Si la API falla, la tarjeta vuelve visualmente a su sitio y se avisa al usuario.
- [x] Un tablero sin tarjetas muestra un estado vacío con sentido.
- [x] Una fila `.row` / `.col-*` maqueta las columnas sin romper los estilos de HeroUI.
- [x] `npm run check` en verde.

## Plan de verificación

- Frontend: `npm run check` desde `frontend/` (eslint + tsc + vitest).
- Frontend: `npm run build` sin errores.
- End-to-end: API real levantada (`uv run poe dev`), datos de prueba reales creados
  contra la API (persona, tablero, columnas ya sembradas, tarjetas), navegador Chrome
  headless dirigido por el protocolo DevTools desde un script de Node (sin extensión
  disponible), comprobando los cinco puntos de la sección "Verificación" del encargo.

## Riesgos / decisiones abiertas

- El patrón exacto de `useDragAndDrop` para mover tarjetas entre columnas
  independientes (una instancia por columna, cerrando sobre su id) se detalla en la
  spec; es la parte de más riesgo técnico de la tarea.
- Verificación en navegador sin la extensión de Chrome disponible: se conduce con un
  script propio sobre el protocolo DevTools (mismo enfoque que documentó TASK-07).

## Revisión y cierre · 2026-09-08

Se corrigió la concurrencia de movimientos: el arrastre se deshabilita hasta que
terminan la escritura y la reconciliación. Una guarda síncrona evita dos disparos
antes del siguiente render. Regresión con respuesta aplazada y rechazo 409;
también se comprueba la presentación genérica de un 404.

Verificación final ejecutada: `uv run poe check` (111 passed; Ruff, formato y
Mypy correctos), `npm run check` (32 passed en 8 archivos; ESLint y TypeScript
correctos) y `npm run build` (correcto, aviso de chunk superior a 500 kB).
En navegador con API/PostgreSQL reales: movimiento con ratón y recarga; movimiento
por teclado y recarga; rechazo WIP con reversión y aviso; tablero vacío; rejilla y
HeroUI inspeccionados visualmente. Sin cambios de modelos ni contrato: no aplica
migración ni regeneración de tipos por esta revisión.

TASK-14 y TASK-15 siguen pendientes de sus otras dependencias; no queda ninguna
tarea adicional lista para empezar por este cierre.
