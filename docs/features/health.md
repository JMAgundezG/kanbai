# Salud del servicio

**Introducida por:** [TASK-01](../tasks/TASK-01-scaffold-backend.md) · **Última actualización:** 2026-08-30

Dos comprobaciones, con propósitos distintos. Confundirlas es el error clásico: si la
sonda de vida consulta la base de datos, una caída de PostgreSQL hace que el
orquestador reinicie procesos que están perfectamente sanos.

| Endpoint | Qué responde | Toca la base de datos |
|----------|--------------|------------------------|
| `GET /health` | `200 {"status": "ok"}` | No |
| `GET /api/v1/health/ready` | `200 {"status": "ok", "database": "ok"}` | Sí (`SELECT 1`) |
| | `503 {"status": "error", "database": "error"}` cuando no responde | |

- **Liveness** (`/health`) vive **fuera** de `/api/v1`: es infraestructura, no parte del
  contrato que consume el frontend. Por eso no lleva versión.
- **Readiness** (`/api/v1/health/ready`) recorre la pila entera: router →
  `services/health.py` → `repositories/health.py` → PostgreSQL. Es la rodaja vertical
  que sirve de plantilla para cualquier feature nueva.
- Un fallo de base de datos **nunca** llega al cliente: el detalle de psycopg va al log
  (`Database readiness probe failed`) y la respuesta solo dice `error`.

## Documentación interactiva

`/docs`, `/redoc` y `/openapi.json` se publican en todos los entornos **salvo** con
`KANBAI_ENVIRONMENT=production`, donde devuelven 404.

## Contrato

El esquema commiteado está en `backend/openapi.json`, generado con `uv run poe openapi`
y verificado por `tests/test_openapi.py`, que falla si el archivo y el código divergen.
El exportador ignora el entorno a propósito (`SchemaSettings`), así que el contrato es
idéntico en cualquier máquina.
