# Plan · TASK-06 · Tarjetas: CRUD y movimiento

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-06](../tasks/TASK-06-tarjetas.md)

## Objetivo

La unidad de trabajo del tablero. Una tarjeta vive en una columna, tiene una posición
dentro de ella y recuerda qué actor la creó. El CRUD es rutina; lo que de verdad
decide esta tarea es **el movimiento**: cambiar de columna y de posición en una sola
operación que aguante que varias personas y agentes muevan tarjetas a la vez sin
duplicar posiciones, sin perder tarjetas y sin colarse por encima del límite WIP.

## Enfoque

Copiar al pie el patrón de TASK-05 (`board_columns`), que se diseñó explícitamente
para que esta tarea lo heredara: capas `router → service → repository → model`,
filtrado de pertenencia dentro de la consulta
(`repositories/membership.py::board_ids_for_actor`), 404 para recurso ajeno, listados
paginados con `Page[T]`, y el **mismo esquema de posiciones**: `position` como `float`
con `UniqueConstraint(column_id, position)` `DEFERRABLE INITIALLY DEFERRED`, `GAP`
importado de `repositories/columns.py` (no redefinido), punto medio entre vecinas al
mover.

**La decisión central de esta tarea es dónde se serializa el movimiento.** Tres
alternativas consideradas:

1. **Leer en Python y escribir después** (leer vecinas, calcular el punto medio,
   `UPDATE`). Descartada de entrada: es exactamente el anti-patrón que la tarea
   prohíbe. Dos movimientos simultáneos hacia la misma columna leen el mismo estado,
   calculan el mismo punto medio y chocan contra el `UNIQUE` aplazado en el `COMMIT`
   — el segundo se lleva un `IntegrityError` sin traducir (500 opaco), que es
   justo lo que la code review de TASK-05 encontró en el alta de columnas.
2. **Bloquear la fila del tablero** (`repositories/boards.py::lock_board_for_update`,
   lo que ya hace TASK-05 al crear/reordenar columnas). Correcto, pero serializa
   *todo* el tablero: dos movimientos en columnas distintas del mismo tablero se
   esperan mutuamente sin ninguna razón. En un tablero con varios agentes trabajando
   a la vez —el caso de uso del producto— es demasiado grueso.
3. **Bloquear la fila de la columna de destino** (`SELECT ... FROM board_columns
   WHERE id = :id FOR UPDATE`). **Elegida.** Los dos invariantes que el movimiento
   pone en riesgo son *por columna*: la unicidad de `position` es
   `(column_id, position)`, y el límite WIP es de la columna. Bloquear la fila de la
   columna de destino serializa exactamente a los actores que compiten por esos dos
   invariantes y deja pasar en paralelo los movimientos hacia columnas distintas.
   PostgreSQL en `READ COMMITTED` vuelve a leer tras desbloquear, así que la
   transacción que espera calcula su posición y cuenta las tarjetas sobre el estado
   **ya comprometido** por la anterior: ni posiciones duplicadas ni dos tarjetas
   coladas en el último hueco del WIP.

El movimiento sigue siendo **un solo `UPDATE` de una sola fila** (la tarjeta que se
mueve): esa es la propiedad por la que TASK-05 eligió posiciones `float` en lugar de
reindexado entero.

## Alcance

Backend (`backend/src/kanbai/`):
- `models/card.py` — modelo `Card` (tabla `cards`): tablero, columna, título,
  descripción, posición, actor creador, `created_at`/`updated_at`.
- `models/__init__.py` — reexporta `Card` para que Alembic lo vea.
- Migración Alembic autogenerada y **revisada a mano** (el `UNIQUE` aplazable es el
  punto que Alembic puede omitir).
- `schemas/card.py` — `CardCreate` / `CardUpdate` / `CardMove` / `CardRead`.
- `repositories/cards.py` — únicas consultas SQL sobre `cards`.
- `repositories/columns.py` — añade `lock_column_for_update` (el bloqueo del punto 3).
- `services/cards.py` — reglas: pertenencia, creación con actor creador, movimiento
  atómico, límite WIP.
- `services/columns.py` — cierra el pendiente que TASK-05 dejó marcado con un
  comentario: borrar una columna con tarjetas devuelve `409`.
- `api/routers/cards.py` — endpoints bajo `/api/v1/boards/{board_id}/cards`.
- `api/router.py` — registra el router.
- `tests/test_cards.py` — CRUD, permisos (404), límite WIP, y **dos tests de
  concurrencia real** con conexiones y sesiones independientes que hacen `COMMIT` de
  verdad (la técnica que estrenó `tests/test_columns.py`, porque la suite normal vive
  en un `SAVEPOINT` que siempre se revierte).
- `tests/test_columns.py` — añade `test_borrar_columna_con_tarjetas_devuelve_409`.

Frontend (`frontend/src/`): **no se toca**. Mismo criterio que TASK-04 y TASK-05:
ningún código de `frontend/` consume todavía `/boards`, y el primero que lo hará es
TASK-08.

Contrato: cambia el OpenAPI (seis endpoints nuevos). `uv run poe openapi` regenera
`backend/openapi.json` (`tests/test_openapi.py` falla si no se hace).
`frontend/src/api/schema.d.ts` no se regenera, por el mismo motivo que arriba.

## Decisiones abiertas que cierra la spec

1. **Cómo se expresa la posición de destino en el movimiento**: índice entero dentro
   de la columna de destino frente a "detrás de esta tarjeta" (`after_card_id`), y
   qué pasa si el índice que manda el cliente se quedó desfasado.
2. **El verbo y la forma del endpoint de movimiento** (`POST .../move` frente a
   `PUT`), y por qué no se hace con el `PUT` de edición.
3. **Si el límite WIP se aplica también al crear** una tarjeta, no solo al moverla.
4. **`ON DELETE` de las tres claves ajenas** (`board_id`, `column_id`,
   `created_by_actor_id`) y cómo convive el `CASCADE` de borrar un tablero con el
   `409` de borrar una columna con tarjetas.
5. **Qué hacer cuando la precisión del `float` se agota** entre dos vecinas muy
   juntas (recompactación de la columna dentro de la misma transacción bloqueada).

## Criterios de aceptación

- [x] Se crea, edita y borra una tarjeta, y el creador registrado es el actor
      autenticado, sea persona o agente.
- [x] Mover una tarjeta a otra columna y a otra posición persiste correctamente y el
      orden se conserva al releer.
- [x] Dos movimientos concurrentes sobre la misma columna **no** dejan posiciones
      duplicadas ni pierden una tarjeta (test explícito de concurrencia).
- [x] Mover a una columna que ya alcanzó su límite WIP devuelve un error claro en
      español.
- [x] Una tarjeta de un tablero ajeno devuelve **404**.
- [x] `uv run poe check` en verde.

## Plan de verificación

- Backend, desde `backend/`: `uv run poe check` (ruff + mypy + pytest), **dos veces**
  — los tests de concurrencia real son la fuente más probable de intermitencias y hay
  que descartarlas.
- Migración: `--autogenerate`, revisión a mano del archivo, `alembic upgrade head`, y
  un `--autogenerate` posterior que salga vacío (esa revisión de comprobación se
  borra).
- Contrato: `uv run poe openapi`.
- Frontend, desde `frontend/`: `npm run check` (no se toca nada, pero es la puerta).
- Los tests que hacen `COMMIT` real limpian sus datos: la base `kanbai_test` queda sin
  residuos.

## Riesgos / decisiones abiertas

- **Que el test de concurrencia no demuestre nada.** Un test que dispare dos
  movimientos con `asyncio.gather` pero sobre la misma sesión los ejecuta en serie y
  pasa siempre, tenga o no bloqueo el código. Mitigación: sesiones y conexiones
  independientes con `COMMIT` real, y **comprobar que el test falla si se quita el
  bloqueo** antes de darlo por bueno.
- **Interbloqueos.** Si una operación llegara a tomar dos bloqueos en orden distinto
  al de otra, PostgreSQL abortaría una de las dos. Mitigación: un único orden global
  de adquisición en todo el código (columna → tarjeta) y nunca más de una columna por
  transacción.
- **El `CASCADE` de la columna borra tarjetas en silencio** si la comprobación del
  `409` corre sin bloqueo y una tarjeta entra a la vez. Mitigación: el borrado de
  columna toma el mismo bloqueo de columna antes de contar.
- **Erosión de la precisión del `float`** tras muchas inserciones entre las mismas dos
  vecinas. Mitigación en la spec (decisión abierta 5).
