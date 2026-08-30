# Tableros y membresía

**Introducida por:** [TASK-04](../tasks/TASK-04-tableros-y-membresia.md) · **Última actualización:** 2026-08-30

El **tablero** es el espacio de trabajo con sus miembros, y la membresía es la unidad
de autorización de todo el producto: a partir de aquí, "puedo ver esto" significa
"soy miembro de su tablero", sin distinguir si el miembro es una persona o un agente.

## Modelo

| Tabla | Columnas |
|-------|----------|
| `boards` | `id` (UUID), `name`, `created_at` |
| `board_members` | `id`, `board_id` (FK→`boards.id`, `ON DELETE CASCADE`), `actor_id` (FK→**`actors.id`**, `ON DELETE CASCADE`), `role` (`"owner"` \| `"member"`, `CHECK` en base de datos), `created_at` |

`board_members.actor_id` apunta a la tabla base de la jerarquía de actor
(`actors`), nunca a `people`: es literalmente la invariante de `CLAUDE.md` §0 hecha
esquema. Ninguna consulta de esta feature filtra por `Actor.kind` — un agente
(TASK-09) será miembro exactamente igual que una persona el día que exista la tabla
`agents`, sin tocar `board_members` en absoluto.

`Board` no tiene columna `owner_id`: quién es owner vive enteramente en
`board_members` (una fila con `role="owner"`), para no duplicar esa fuente de
verdad.

## El filtro de pertenencia, reutilizable

`repositories/membership.py::board_ids_for_actor(actor_id)` es una subconsulta —
"ids de tablero donde este actor es miembro" — pensada para que cualquier
repositorio de una tabla que cuelgue de un tablero la reutilice sin rederivar el
join:

```python
.where(Column.board_id.in_(board_ids_for_actor(actor_id)))   # TASK-05
```

TASK-05 (columnas), TASK-06 (tarjetas, vía su columna), y TASK-11/TASK-12
(comentarios y eventos, vía su tarjeta) filtran su propia tabla con este mismo
patrón. `repositories/boards.py` reutiliza la subconsulta para el conteo de la
paginación; para el listado y la lectura de un tablero concreto usa un join directo
a `board_members` porque además necesita el `role` de esa fila, que la subconsulta
no lleva.

## Roles y permisos

| Acción | Requiere |
|--------|----------|
| Crear un tablero | Cualquier actor autenticado (queda como `owner`) |
| Leer un tablero / listar sus miembros | Ser miembro (`owner` o `member`) |
| Renombrar o borrar un tablero | Ser `owner` |
| Añadir un miembro | Ser `owner` |
| Quitar a otro miembro | Ser `owner` |
| Quitarse a uno mismo | Cualquier miembro, sin importar su rol |

**No ser miembro de un tablero devuelve 404** en cualquier ruta bajo
`/boards/{board_id}...`, nunca 403 — no se confirma que el tablero exista. **Ser
miembro pero no tener el rol necesario devuelve 403** (`AuthorizationError`, nueva
en esta tarea): a diferencia del caso anterior, el actor ya sabe que el recurso
existe porque es miembro de él.

**Quitar al único `owner` de un tablero está bloqueado** con `409 Conflict`: la
regla cuenta cuántos `owner` quedan, no quién en concreto se va — si hay más de uno,
cualquiera de ellos puede quitarse sin problema.

## Endpoints

| Método | Ruta | Requiere | Respuesta |
|--------|------|----------|-----------|
| `POST` | `/api/v1/boards` | sesión | `201 BoardRead` |
| `GET` | `/api/v1/boards` | sesión | `200 Page[BoardRead]` (solo los propios) |
| `GET` | `/api/v1/boards/{board_id}` | miembro | `200 BoardRead` / `404` |
| `PATCH` | `/api/v1/boards/{board_id}` | owner | `200 BoardRead` / `404` / `403` |
| `DELETE` | `/api/v1/boards/{board_id}` | owner | `204` / `404` / `403` |
| `GET` | `/api/v1/boards/{board_id}/members` | miembro | `200 Page[BoardMemberRead]` / `404` |
| `POST` | `/api/v1/boards/{board_id}/members` | owner | `201 BoardMemberRead` / `404` / `403` / `409` |
| `DELETE` | `/api/v1/boards/{board_id}/members/{member_id}` | owner o el propio miembro | `204` / `404` / `403` / `409` |

`BoardRead` incluye `role`: el rol del actor que pregunta en ese tablero concreto —
no es una columna de `Board`, la ensambla el router a partir del `(Board, role)` que
devuelve el servicio. `BoardMemberRead.actor` reutiliza `ActorRead` de TASK-03 tal
cual, sin ningún campo añadido para agentes.

## Paginación

Primer uso en el proyecto de la forma genérica `{items, total, page, size}`:
`schemas/pagination.py::Page[T]` (`class Page[ItemT](BaseModel)`, sintaxis PEP 695)
y `api/deps.py::PaginationParams`/`PaginationDep`, con query params `page` (≥1) y
`size` (1–100). Pedir `size` por encima de 100 devuelve `422`, no un recorte
silencioso. Cualquier listado futuro reutiliza ambas piezas sin más código.

## No entra en esta feature

Columnas y tarjetas (TASK-05, TASK-06), invitaciones por email o alta de personas
nuevas, permisos por columna o por tarjeta, y el alta de agentes como actores
(TASK-09) — `POST /boards/{id}/members` recibe un `actor_id` ya existente porque no
hay, todavía, ningún endpoint que cree o busque actores.

## Contrato

`backend/openapi.json` incluye ahora los ocho endpoints de `/api/v1/boards`. El
frontend no los consume todavía (la primera vez es TASK-08); no se ha regenerado
`frontend/src/api/schema.d.ts` porque no hay ningún código en `frontend/` que lo use
aún (mismo criterio que aplicó TASK-03 a `/auth`).
