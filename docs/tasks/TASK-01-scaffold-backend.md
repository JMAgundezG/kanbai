# TASK-01 · Scaffold del backend (uv + Python 3.14 + FastAPI)

**Prioridad:** Alta · **Depende de:** —

## Objetivo

Dejar `backend/` funcionando como un proyecto FastAPI ejecutable, con el layout por
capas, la configuración, la base de datos con Alembic y la batería de calidad
(`ruff`, `mypy`, `pytest`) descritos en `CLAUDE.md`. Es la base sobre la que se
implementa cualquier feature posterior.

## Alcance

**Entra:**
- `backend/pyproject.toml` gestionado con uv (`requires-python = ">=3.14"`),
  `.python-version` con `3.14`, `uv.lock` commiteado.
- Layout `src/kanbai/` con `main.py`, `core/` (config, seguridad), `db/` (engine,
  sesión, base declarativa), `models/`, `schemas/`, `repositories/`, `services/`,
  `api/` (router `v1`, dependencias).
- `GET /health` y OpenAPI servido en `/docs`.
- Alembic configurado y con la migración inicial vacía aplicable.
- `pytest` con `httpx.AsyncClient` + `ASGITransport` y un test de `/health` en verde.
- Tareas `poe` (`dev`, `lint`, `format`, `typecheck`, `test`, `check`) y `.env.example`.

**No entra:**
- Modelos de dominio del kanban (tableros, columnas, tarjetas).
- Autenticación real de usuarios.

## Criterios de aceptación

- [x] `uv sync` funciona partiendo del repo limpio y `uv run python -V` dice 3.14.x.
- [x] `uv run poe dev` levanta la API y `GET /health` responde `{"status": "ok"}`.
- [x] `/docs` muestra el OpenAPI.
- [x] `uv run poe check` (ruff + mypy estricto + pytest) pasa en verde.
- [x] `alembic upgrade head` aplica sin errores sobre una base de datos vacía.
- [x] No hay secretos en el repo; `.env.example` documenta todas las variables.

## Notas técnicas

- Settings con `pydantic-settings`, cacheadas con `@lru_cache`, inyectadas por `Depends`.
- Sesión de base de datos async con `async_sessionmaker`, expuesta como `SessionDep`.
- Un solo `APIRouter` raíz con prefijo `/api/v1`.
