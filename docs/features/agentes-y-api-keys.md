# Agentes y API keys

**Introducida por:** [TASK-09](../tasks/TASK-09-agentes-y-api-keys.md) · **Última actualización:** 2026-08-30

La tarea que hace distinto a kanbai: un **agente** es un actor igual que una
persona ([TASK-03](../tasks/TASK-03-actores-y-sesion.md)), solo que se identifica
con una **API key** en vez de una sesión de cookie, y lo da de alta una persona.
Con una key válida, un agente usa **exactamente los mismos endpoints** de
tableros, columnas y tarjetas (TASK-04, TASK-05, TASK-06) que una persona, con las
mismas restricciones de membresía — ninguna ruta de dominio nueva.

## Modelo

*Joined-table inheritance*, igual que `Person`: `agents` no toca `actors` ni
`people`.

| Tabla | Columnas |
|-------|----------|
| `agents` | `actor_id` (FK+PK → `actors.id`, `ON DELETE CASCADE`), `description` (opcional), `owner_person_id` (FK → `people.actor_id`, `ON DELETE CASCADE`) |
| `agent_api_keys` | `id`, `agent_id` (FK → `agents.actor_id`, `ON DELETE CASCADE`), `prefix` (único, en claro), `secret_hash` (SHA-256), `created_at`, `revoked_at` (nullable) |

`display_name` y `created_at` del agente son los heredados de `Actor` — el mismo
campo que usa una persona para su nombre visible.

## El esquema de la API key

La key que ve el agente tiene la forma `kanbai_agent_<prefix>.<secret>`:

- `prefix` (`secrets.token_urlsafe(9)`, ~12 caracteres) se guarda **en claro**, en
  una columna única e indexada — localizar la key presentada es un
  `WHERE prefix = :prefix`, nunca un `SELECT` de todas las keys para comparar una
  a una.
- `secret` (`secrets.token_urlsafe(32)`, ~43 caracteres) solo existe fuera de la
  base de datos: se guarda `secret_hash = sha256(secret)`. El secreto ya nace con
  alta entropía aleatoria (a diferencia de una contraseña elegida por una
  persona), así que un hash rápido con comparación a tiempo constante
  (`secrets.compare_digest`) es la herramienta correcta — no hace falta Argon2
  aquí.
- Revocar una key no borra la fila: pone `revoked_at`. "Inexistente" y "revocada"
  son estados distintos en base de datos, pero **el mismo `401` genérico** en la
  respuesta — igual que TASK-03 nunca distingue "email no existe" de "contraseña
  incorrecta".
- La key en claro **solo aparece una vez**: en el cuerpo de la respuesta de
  `POST /api/v1/agents/{agent_id}/keys`. Ningún otro endpoint, log ni traza la
  vuelve a mostrar — `ApiKeyRead` (la forma que usan el listado y la revocación)
  ni siquiera tiene ese campo.

## `CurrentActor`: la segunda credencial

`api/deps.py::get_current_actor` prueba primero la cookie de sesión de persona
(TASK-03); si no hay, prueba `Authorization: Bearer <api key>`. Presencia, no
validez, decide la rama. La resolución de la key
(`services/agents.py::resolve_actor_by_api_key`) es siempre el mismo `401`
genérico ante cualquier fallo — key malformada, prefijo inexistente, key
revocada, o secreto incorrecto — para no delatar cuál de los cuatro fue.

Devuelve un `Actor` igual que la sesión de persona: ningún router ni servicio de
dominio (`boards`, `columns`, `cards`) sabe ni le importa cuál de las dos
credenciales resolvió a quién le atiende.

## Un agente nunca supera a su persona propietaria

Invariante de `CLAUDE.md` §0, aplicada sin que el dominio lea `actor.kind` en
ningún momento: `Actor` define
`permission_ceiling_actor_id() -> uuid.UUID | None`, que una persona responde
siempre con `None` y que `Agent` sobrescribe devolviendo su
`owner_person_id`. `services/boards.py` llama a este método — nunca a `kind` — en
dos puntos:

- **`add_member`**: si el actor a añadir tiene techo, ese techo debe ya ser
  miembro del tablero con un rol igual o superior al que se le va a conceder; si
  no, `409 Conflict`.
- **`create_board`**: si quien crea el tablero tiene techo, ese techo se añade
  también como `owner`, en la misma transacción.

Ver [`tableros-y-membresia.md`](tableros-y-membresia.md#el-techo-de-permisos-de-un-agente-task-09)
para el detalle, el lock que protege la comprobación (`add_member` y
`remove_member` toman `lock_board_for_update`) y la limitación aceptada (no se
revoca en cascada si la persona pierde después su membresía).

Dos correcciones de la code review, aplicadas antes de cerrar la tarea: la
comprobación del techo necesitaba ese lock (era un read-then-insert sin
protección, demostrado con una prueba de concurrencia real), y `Actor` necesitaba
`with_polymorphic="*"` en su mapper — sin él, leer `Agent.owner_person_id` sobre
un actor cargado por la clase base (`select(Actor)`, lo que hace `CurrentActor`
en cada petición) reventaba con `MissingGreenlet` en una sesión nueva, es decir,
en cualquier petición real.

**Solo una persona puede dar de alta o administrar un agente** —
`services/agents.py::_require_person` usa `isinstance(actor, Person)`, la única
comprobación de tipo de actor en todo el backend fuera de este módulo. Es la
frontera de la propia feature (un agente no puede crear agentes), no una
ramificación del dominio compartido: `/api/v1/agents` no es un endpoint de
tableros, columnas o tarjetas.

## Endpoints

Todos bajo `/api/v1/agents`, todos exigen que `CurrentActor` sea una persona
(`403` si no) y, salvo la creación, que el agente sea suyo (`404` si no).

| Método | Ruta | Respuesta |
|--------|------|-----------|
| `POST` | `/api/v1/agents` | `201 AgentRead` |
| `GET` | `/api/v1/agents` | `200 Page[AgentRead]` (solo los propios) |
| `GET` | `/api/v1/agents/{agent_id}` | `200 AgentRead` / `404` |
| `POST` | `/api/v1/agents/{agent_id}/keys` | `201 ApiKeyCreated` (con `api_key` en claro) / `404` |
| `GET` | `/api/v1/agents/{agent_id}/keys` | `200 Page[ApiKeyRead]` (sin secreto) / `404` |
| `POST` | `/api/v1/agents/{agent_id}/keys/{key_id}/revoke` | `200 ApiKeyRead` (idempotente) / `404` |

No hay endpoint para borrar un agente (fuera de alcance de TASK-09).

## No entra en esta feature

Cola de trabajo y endpoints de consumo automático (TASK-13), reclamación de
tarjetas (TASK-10), interfaz de gestión de agentes (TASK-16), límite de peticiones
por key, borrado de agentes, y revocación en cascada de la membresía de un agente
cuando su persona propietaria deja un tablero.

## Contrato

`backend/openapi.json` incluye ahora `/api/v1/agents` y sus subrecursos. El
frontend no los consume todavía (TASK-16); no se ha regenerado
`frontend/src/api/schema.d.ts` — mismo criterio que TASK-03 aplicó a `/auth`.
