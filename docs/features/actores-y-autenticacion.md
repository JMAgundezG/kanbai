# Actores y autenticación de personas

**Introducida por:** [TASK-03](../tasks/TASK-03-actores-y-sesion.md) · **Última actualización:** 2026-08-30

El **actor** es el participante que firma toda acción del tablero: persona o agente,
mismo tipo de dominio. Esta feature modela el actor y deja a las **personas**
capaces de identificarse con email y contraseña; los agentes llegan en TASK-09
sobre este mismo modelo, sin tocarlo.

## Modelo

*Joined-table inheritance* de SQLAlchemy: una tabla `actors` con lo común a
cualquier actor, y una tabla `people` con lo propio de una persona.

| Tabla | Columnas |
|-------|----------|
| `actors` | `id` (UUID), `kind` (`"person"` hoy, `"agent"` en TASK-09), `display_name`, `created_at` |
| `people` | `actor_id` (FK+PK → `actors.id`, `ON DELETE CASCADE`), `email` (único), `password_hash` |
| `sessions` | `id`, `actor_id` (FK → `actors.id`), `token_hash` (único, SHA-256 del token de sesión), `created_at`, `expires_at` |

Ninguna consulta fuera de la capa de autenticación filtra por `kind`: cargar un
actor por `id` (`repositories/actors.py::get_actor_by_id`) ya devuelve la subclase
concreta gracias a la herencia.

## Autenticación de personas

Sesión por **cookie httpOnly** (`kanbai_session` por defecto,
`KANBAI_SESSION_COOKIE_NAME`), no JWT: el valor de la cookie es un token aleatorio
opaco; en base de datos solo se guarda su hash SHA-256 (tabla `sessions`). El
`logout` real borra la fila — no depende de una lista de revocación. Vive
`session_ttl_days` (por defecto 14, `KANBAI_SESSION_TTL_DAYS`).

Contraseñas con **Argon2id** (`argon2-cffi`).

| Endpoint | Qué hace |
|----------|----------|
| `POST /api/v1/auth/login` | Verifica email + contraseña. `200 ActorRead` + `Set-Cookie` de sesión, o `401` genérico. |
| `POST /api/v1/auth/logout` | Borra la sesión del token en la cookie (si hay). Siempre `204`, sea cual sea el estado de la sesión: cerrar sesión es idempotente. |
| `GET /api/v1/auth/me` | `200 ActorRead` del actor de la sesión activa, o `401` sin sesión. |

`ActorRead` (`id`, `kind`, `display_name`, `created_at`) es deliberadamente el mismo
schema para cualquier tipo de actor, sin `email`: el actor se identifica por tipo e
identidad visible, no por su credencial — así TASK-09 no necesita tocarlo al añadir
agentes.

**Login inválido nunca revela si el email existe:** email inexistente y contraseña
incorrecta devuelven exactamente el mismo `401` con el mismo cuerpo
(`"El email o la contraseña no son correctos."`). Cuando el email no existe, se
verifica igualmente contra un hash señuelo (`verify_dummy_password`) para que el
tiempo de respuesta no lo delate.

## `CurrentActor`

`api/deps.py::get_current_actor` (expuesto como `CurrentActor`) es la única
dependencia que resuelve quién hace la petición. Hoy solo mira la cookie de sesión;
TASK-09 añadirá la rama `Authorization: Bearer` **dentro de esta misma función**,
sin cambiar su firma ni tocar ningún router o servicio que ya dependa de ella — la
ramificación es sobre qué credencial llegó, nunca sobre `actor.kind` (invariante de
`CLAUDE.md` § 0).

## No entra en esta feature

Registro público, invitaciones, recuperación de contraseña, verificación de email,
roles o permisos finos (la membresía de tablero llega en TASK-04), agentes y API
keys (TASK-09). La creación de una persona existe solo como función de servicio
interna (`services/auth.py::create_person`), usada por los tests y por futuras
herramientas de arranque — no hay endpoint HTTP que la exponga todavía.

## Dependencias nuevas

- `argon2-cffi` — hash de contraseña (Argon2id, recomendación OWASP actual).
- `email-validator` — requerida en tiempo de ejecución por `pydantic.EmailStr`.

## Contrato

`backend/openapi.json` incluye ahora `POST /api/v1/auth/login`,
`POST /api/v1/auth/logout` y `GET /api/v1/auth/me`. El frontend no los consume
todavía (llega en TASK-07); no se ha regenerado `frontend/src/api/schema.d.ts`
porque no hay ningún código en `frontend/` que lo use aún.
