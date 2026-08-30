# Plan · TASK-05 · Columnas del tablero

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-05](../tasks/TASK-05-columnas.md)

## Objetivo

Modelar las columnas de un tablero (fases del flujo de trabajo): CRUD, reordenación
atómica en una sola llamada, y un límite de trabajo en curso (WIP) opcional que
TASK-06 aplicará al mover tarjetas. El esquema de posiciones que se decida aquí lo
hereda TASK-06 sin inventar un segundo mecanismo.

## Enfoque

Copiar al pie el patrón de TASK-04 (`boards`/`board_members`): capas
`router → service → repository → model`, filtrado de pertenencia en la consulta
(`repositories/membership.py::board_ids_for_actor`), 404 para tablero ajeno, listados
paginados con `Page[T]`.

**Posición: fraccional (float), no entero con reindexado global.** Un `UPDATE` de una
sola fila (mover una columna, o más adelante una tarjeta, entre dos vecinas) solo
necesita escribir esa fila con un valor entre las dos posiciones vecinas — no hay que
desplazar el resto de filas en la misma transacción. Eso es exactamente lo que TASK-06
exige para el movimiento atómico de tarjetas bajo concurrencia: con reindexado entero,
mover una tarjeta obliga a reescribir todas las posteriores, lo que multiplica el
contenido en conflicto entre movimientos simultáneos. Con float, cada fila es
independiente y una `UniqueConstraint(padre, position)` aplazable
(`DEFERRABLE INITIALLY DEFERRED`) detecta colisiones sin bloquear la tabla entera.

Detalle exacto (fórmulas, DDL, constraint) se cierra en la spec.

## Alcance

Backend (`backend/src/kanbai/`):
- `models/board_column.py` — modelo `BoardColumn` (tabla `board_columns`, evita el
  choque de nombres con `sqlalchemy.Column`).
- Migración Alembic (autogenerada, revisada a mano).
- `schemas/column.py` — `ColumnCreate` / `ColumnUpdate` / `ColumnRead` /
  `ColumnReorder`.
- `repositories/columns.py` — únicas consultas SQL sobre `board_columns`.
- `services/columns.py` — reglas de negocio; `services/boards.py::create_board` pasa
  a sembrar el juego de columnas inicial en la misma transacción.
- `services/boards.py` — pequeño cambio: crear columnas iniciales al crear tablero.
- `api/routers/columns.py` — endpoints bajo `/api/v1/boards/{board_id}/columns`.
- `api/router.py` — registra el nuevo router.
- `tests/test_columns.py` — CRUD, reordenación (N columnas sin huecos ni
  duplicados), 404 en tablero ajeno, y el caso "borrar columna vacía" (con la
  política de "columna con tarjetas" documentada para cuando TASK-06 exista).

Frontend: no se toca (mismo criterio que TASK-04: nada en `frontend/` consume
`/boards` todavía).

Contrato: cambia el OpenAPI (nuevos endpoints). `uv run poe openapi` regenera
`backend/openapi.json`. `schema.d.ts` no se regenera por el mismo motivo que arriba.

## Decisiones abiertas que cierra la spec

1. **Juego de columnas inicial al crear un tablero.** Propuesta: tres columnas fijas
   en español ("Por hacer", "En curso", "Hecho"), sin plantillas configurables (fuera
   de alcance explícito de la tarea).
2. **Borrar una columna con tarjetas.** Las tarjetas no existen todavía (TASK-06), así
   que hoy no hay nada que impedir de verdad. Se decide la política ahora
   (bloquear con `409` si la columna tiene tarjetas) y se documenta como el contrato
   que TASK-06 debe cumplir al añadir el modelo `Card`, sin construir aquí ninguna
   consulta contra una tabla que no existe.

## Criterios de aceptación

- [x] Crear un tablero deja un juego de columnas inicial razonable.
- [x] Reordenar N columnas en una llamada deja un orden estable, sin huecos ni
      posiciones repetidas (demostrado con un test real).
- [x] Borrar una columna con tarjetas está impedido o exige destino (decidido y
      reflejado en `TASK-05-columnas.md` antes de implementar).
- [x] Operar sobre una columna de un tablero ajeno devuelve 404.
- [x] `uv run poe check` en verde.

## Plan de verificación

- Backend: `uv run poe check` desde `backend/` (ruff + mypy + pytest).
- Migración: `alembic revision --autogenerate`, revisión manual del archivo,
  `alembic upgrade head`, y un `--autogenerate` posterior vacío (se borra esa
  revisión de comprobación).
- `uv run poe openapi` para sincronizar `backend/openapi.json`.

## Riesgos / decisiones abiertas

- Rol requerido para gestionar columnas: a diferencia de renombrar/borrar el
  tablero (solo `owner`, TASK-04), se propone que **cualquier miembro** pueda crear,
  renombrar, reordenar y borrar columnas — es trabajo operativo del flujo, no
  administración del tablero. Se confirma en la spec.
- Precisión de `float` a muy largo plazo (inserciones repetidas entre las mismas dos
  columnas): fuera de alcance mitigarlo ahora; la propia reordenación completa ya
  actúa como recompactación si algún día hiciera falta.
