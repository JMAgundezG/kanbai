# TASK-03 · Actores y autenticación de personas

**Prioridad:** Alta · **Depende de:** TASK-01

## Objetivo

Introducir la pieza central del dominio: el **actor**, el participante que firma toda
acción del tablero y que puede ser persona o agente. Esta tarea modela el actor y deja
a las **personas** capaces de identificarse; los agentes llegan en TASK-09 sobre este
mismo modelo, sin tocarlo.

## Alcance

**Entra:**
- Modelo `Actor` con discriminador de tipo (`person` | `agent`) y los datos propios de
  una persona (email único, hash de contraseña, nombre visible).
- Autenticación de personas: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`,
  `GET /api/v1/auth/me`.
- Dependencia `CurrentActor` en `api/deps.py`, preparada para admitir más adelante un
  segundo esquema de credenciales sin cambiar su firma.
- Hash de contraseña con una librería contrastada (justificada en la spec).
- Migración inicial del dominio, revisada.
- Tests: login correcto, credenciales inválidas, acceso sin sesión, `/auth/me`.

**No entra:**
- Agentes y API keys (TASK-09).
- Registro público, invitaciones, recuperación de contraseña, verificación de email.
- Roles o permisos finos (la membresía de tablero llega en TASK-04).

## Criterios de aceptación

- [ ] `POST /auth/login` con credenciales válidas devuelve sesión y `200`.
- [ ] Credenciales inválidas devuelven `401` con un mensaje en español que **no**
      revela si el email existe.
- [ ] `GET /auth/me` devuelve el actor autenticado con su tipo; sin sesión, `401`.
- [ ] La contraseña no aparece nunca en respuestas, logs ni trazas de error.
- [ ] `alembic upgrade head` aplica limpio y un `--autogenerate` posterior sale vacío.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- La estrategia de herencia (tabla única con discriminador frente a *joined table*) se
  decide en la spec; la restricción es que **un endpoint no debe ramificar por el tipo
  de actor** (ver `CLAUDE.md` § 0).
- La sesión (cookie firmada frente a JWT) se decide en la spec valorando que TASK-09
  añadirá autenticación por `Authorization: Bearer` en paralelo.
