# Plan · TASK-03 · Actores y autenticación de personas

**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-03](../tasks/TASK-03-actores-y-sesion.md)

## Objetivo

Modelar el **actor** — la pieza central del dominio, persona o agente, que firma toda
acción del tablero — y dejar a las personas capaces de identificarse con email y
contraseña. Los agentes (TASK-09) se añadirán sobre este mismo modelo sin tocarlo.

## Enfoque

- **Herencia del actor:** *joined-table inheritance* de SQLAlchemy. Una tabla base
  `actors` (id, `kind` discriminador, `display_name`, `created_at`) con los campos
  comunes a cualquier actor, y una tabla `people` (`actor_id` FK+PK, `email` único,
  `password_hash`) para lo propio de una persona. TASK-09 añadirá `agents` de la misma
  forma, sin migrar ni tocar `actors` ni `people`. Alternativa descartada: tabla única
  con columnas nullable para email/password/api_key — mezclaría en una fila campos que
  no tienen sentido según el tipo, justo lo que el dominio quiere evitar.
- **Sesión de personas:** cookie de sesión opaca respaldada en base de datos (tabla
  `sessions`: token hasheado, actor, expiración), no JWT. Permite un logout real
  (se borra la fila) en vez de depender de una lista de revocación. El mismo patrón
  (token aleatorio + hash almacenado) es el que usará TASK-09 para las API keys de los
  agentes, así que `CurrentActor` queda ya preparado para admitir un segundo esquema
  de credenciales (`Authorization: Bearer`) sin cambiar su firma: internamente
  probará la cookie y, cuando TASK-09 lo añada, la cabecera — la rama vive en la
  dependencia de infraestructura, no en servicios ni routers.
- **Hash de contraseña:** `argon2-cffi` (Argon2id), recomendación actual de OWASP;
  no depende de `passlib`, que está sin mantenimiento activo.
- No entran endpoints de alta de personas: la tarea explícitamente deja fuera el
  registro público. La creación de una persona vive como función de servicio interna,
  usada por los tests y por futuras herramientas de arranque (semilla, admin), no
  expuesta por HTTP.

## Alcance

- Backend (`backend/src/kanbai/`):
  - `models/actor.py` (`Actor`, `Person`), `models/session.py` (`AuthSession`).
  - `core/security.py`: hash/verificación de contraseña, generación y hash de tokens
    de sesión.
  - `core/config.py`: `session_cookie_name`, `session_ttl_days`.
  - `core/exceptions.py`: `AuthenticationError` (401).
  - `schemas/actor.py` (`ActorRead`), `schemas/auth.py` (`LoginRequest`).
  - `repositories/actors.py`, `repositories/sessions.py`.
  - `services/auth.py`: login, logout, resolución de sesión, creación interna de
    personas.
  - `api/deps.py`: `CurrentActor`.
  - `api/routers/auth.py`: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`.
  - Migración Alembic para `actors`, `people`, `sessions`.
  - `tests/`: fixtures de persona + tests de login, logout, `/me`, permisos y
    unicidad de email.
- Frontend: no toca en esta tarea (llega en TASK-07). Si el contrato de
  `/openapi.json` cambia, se regenera igualmente para no dejarlo desincronizado.
- Contrato: sí cambia (nuevos endpoints `/api/v1/auth/*`). Se exporta con
  `uv run poe openapi`; `npm run gen:api` se pospone a TASK-07, que es quien consume
  estos endpoints, pero se deja anotado en la spec.

## Criterios de aceptación

- [x] `POST /auth/login` con credenciales válidas devuelve sesión y `200`.
- [x] Credenciales inválidas devuelven `401` con un mensaje en español que no revela
      si el email existe.
- [x] `GET /auth/me` devuelve el actor autenticado con su tipo; sin sesión, `401`.
- [x] La contraseña no aparece nunca en respuestas, logs ni trazas de error.
- [x] `alembic upgrade head` aplica limpio y un `--autogenerate` posterior sale vacío.
- [x] `uv run poe check` en verde.

## Plan de verificación

- Backend: `uv run poe check` desde `backend/` (ruff + mypy + pytest).
- Migraciones: generar, revisar a mano, aplicar, y confirmar `--autogenerate`
  posterior vacío (borrando la revisión de comprobación).
- Contrato: `uv run poe openapi` y diff de `backend/openapi.json`.

## Riesgos / decisiones abiertas

- Ninguna decisión de fondo pendiente del usuario; las tres bloqueadas por la tarea
  (herencia, sesión, hash) se fijan y justifican arriba, se detallan en la spec.
