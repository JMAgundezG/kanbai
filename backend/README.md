# kanbai — backend

API FastAPI del proyecto. Las convenciones de arquitectura y calidad están en el
[`AGENTS.md`](../AGENTS.md) de la raíz; aquí solo está lo necesario para arrancar.

## Puesta en marcha

```bash
# Desde la raíz del repositorio:
docker compose up -d db --wait

# Después, desde backend/:
cd backend
cp .env.example .env
uv sync --locked --dev
uv run poe migrate
uv run poe dev               # http://localhost:8000/docs
```

## Comandos

| Comando | Qué hace |
|---------|----------|
| `uv run poe dev` | API con recarga en `:8000` |
| `uv run poe lint` / `format` / `typecheck` / `test` | Pasos sueltos de calidad |
| `uv run poe check` | lint + typecheck + test |
| `uv run poe openapi` | Regenera `openapi.json` (commiteado) |
| `uv run poe migrate` | `alembic upgrade head` |

## Comprobaciones de salud

- `GET /health` — liveness: no toca dependencias, responde `{"status": "ok"}`.
- `GET /api/v1/health/ready` — readiness: consulta la base de datos; `503` si no responde.

## Tests

Corren contra PostgreSQL real (`kanbai_test`, creada por `docker/postgres/init.sql`).
Cada test vive en una transacción que se revierte al terminar. Para apuntar a otra base
de datos: `KANBAI_TEST_DATABASE_URL=postgresql+psycopg://…`.
