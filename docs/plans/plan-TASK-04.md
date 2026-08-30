# Plan · TASK-04 · Tableros y membresía

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-04](../tasks/TASK-04-tableros-y-membresia.md)

## Objetivo

Dar a los actores un espacio de trabajo — el tablero — con sus miembros, y convertir
la membresía en la unidad de autorización de todo lo que viene después (columnas,
tarjetas, comentarios, eventos). A partir de esta tarea, "puedo ver esto" significa
"soy miembro de su tablero", sin importar si soy persona o agente.

## Enfoque

Copiar el patrón de capas de TASK-03 (`router → service → repository → model`,
`CurrentActor`, excepciones de dominio traducidas en `main.py`) y añadir dos piezas
nuevas que TASK-03 no necesitaba:

- **Modelos `Board` y `BoardMember`.** `BoardMember` es la tabla bisagra:
  `board_id` + `actor_id` (FK a `actors.id`, la tabla base de la jerarquía, no a
  `people`) + `role` (`owner` | `member`). Al apuntar a `actors` y no a `people`,
  un agente (TASK-09) será miembro exactamente igual que una persona el día que
  exista esa tabla — hoy se demuestra creando en los tests un `Actor` crudo con
  `kind="agent"` sin fila en `people`, que es exactamente el estado del mundo antes
  de TASK-09.
- **El filtro de pertenencia como pieza reutilizable en el repositorio.** Una
  función `board_ids_for_actor(actor_id)` en un `repositories/membership.py` nuevo,
  que devuelve una subconsulta de "ids de tablero donde este actor es miembro".
  Repositorios futuros (columnas, tarjetas, comentarios, eventos) la importan y
  filtran su propia tabla con `.where(<columna_board_id>.in_(board_ids_for_actor(actor_id)))`
  sin repetir el join. El propio `repositories/boards.py` la reutiliza para el
  conteo de la paginación (no para el listado con rol, que sí necesita el join a
  `board_members` de todos modos).
- **Paginación genérica**, primera vez que se necesita en el proyecto: un
  `schemas/pagination.py::Page[T]` (Pydantic genérico) y unos `PaginationParams`
  en `api/deps.py` con `page`/`size` (máximo `size=100`), reutilizables por
  cualquier listado futuro.

Alternativa descartada: una tabla `agent_memberships` separada de
`board_members` — la invariante del dominio (§0 de `CLAUDE.md`) lo prohíbe
explícitamente y además duplicaría el propio esquema de autorización que TASK-05
en adelante necesita reutilizar sin ramificar.

## Alcance

- Backend (`backend/src/kanbai/`):
  - `models/board.py`, `models/board_member.py` (+ registrar en `models/__init__.py`).
  - `repositories/membership.py` (subconsulta reutilizable), `repositories/boards.py`,
    `repositories/board_members.py`.
  - `services/boards.py`: reglas de creación (owner automático al crear), lectura,
    renombrado y borrado (solo owner), alta/baja de miembros (solo owner, salvo
    quitarse uno mismo), bloqueo de quitar al único owner.
  - `schemas/board.py`, `schemas/board_member.py`, `schemas/pagination.py`.
  - `api/routers/boards.py`, montado en `api/router.py`.
  - `api/deps.py`: `PaginationParams` / `PaginationDep`.
  - `core/exceptions.py`: nueva `AuthorizationError` (403) para "eres miembro pero
    no tienes el rol necesario" — distinta de `NotFoundError` (404), que sigue
    siendo la respuesta para "ni siquiera eres miembro".
  - Migración Alembic para `boards` y `board_members`.
  - `tests/test_boards.py` (feliz, validación, permisos, la invariante
    persona/agente, y paginación).
- Frontend: no se toca (ninguna tarea de frontend depende de tableros todavía;
  TASK-07/08 son las primeras). Se exporta igualmente `backend/openapi.json` con
  `uv run poe openapi` porque el contrato cambia, aunque no haya consumidor aún
  (mismo criterio que aplicó TASK-03 con `/auth`).
- Contrato: cambia el OpenAPI (nuevos endpoints `/api/v1/boards`). No hay
  `frontend/src/api/schema.d.ts` que regenerar todavía (nada lo consume), igual que
  TASK-03 dejó anotado para `/auth`.

## Criterios de aceptación

- [x] Un actor crea un tablero y queda como `owner`.
- [x] `GET /boards` devuelve solo los tableros donde el actor es miembro, con forma
      `{items, total, page, size}` y máximo de `limit` aplicado.
- [x] Leer, modificar o borrar un tablero ajeno devuelve **404**, no 403.
- [x] Un `owner` puede añadir como miembro a un agente exactamente igual que a una
      persona.
- [x] Quitarse a uno mismo siendo el único `owner` está impedido con un error claro.
- [x] `uv run poe check` en verde.

## Plan de verificación

- Backend: `uv run poe check` desde `backend/` (ruff + mypy + pytest).
- Migración: `alembic revision --autogenerate` revisada a mano, `alembic upgrade
  head`, y una segunda `--autogenerate` de comprobación que salga vacía (se borra).
- Contrato: `uv run poe openapi` para dejar `backend/openapi.json` sincronizado
  (lo verifica `tests/test_openapi.py`, que ya existe).
- No aplica frontend en esta tarea (sin consumidor todavía).

## Riesgos / decisiones abiertas

- **Permisos dentro del tablero (owner vs. member).** El criterio de aceptación
  solo exige bloquear quitar al único owner; no especifica si renombrar/borrar el
  tablero o gestionar miembros requiere ser `owner`. Decisión: sí, esas cuatro
  acciones (`PATCH`/`DELETE` del tablero, añadir/quitar miembro) se restringen a
  `owner`, con 403 (`AuthorizationError`, nueva) cuando el actor es miembro pero no
  owner — es un caso distinto del "no eres miembro" (404): aquí el actor ya sabe
  que el recurso existe. Se detalla y justifica en la spec.
- **Cómo se identifica al actor a añadir como miembro.** No hay endpoint de
  búsqueda de actores en esta tarea (ni de alta de agentes, que es TASK-09):
  `POST /boards/{id}/members` recibe `actor_id` directamente. Es la única opción
  razonable con lo que existe hoy; se anota como limitación conocida.
- **`BoardRead` incluye el `role` del actor que pregunta.** No lo exige el
  criterio de aceptación, pero es información barata (ya se consulta para
  filtrar) y que el frontend necesitará para decidir qué mostrar (p. ej. si puede
  borrar el tablero). Se documenta como decisión de diseño, no como alcance
  añadido de negocio.
