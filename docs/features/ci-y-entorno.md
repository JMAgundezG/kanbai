# Integración continua y entorno reproducible · TASK-17

El proyecto se puede arrancar completo con `docker compose up -d --build --wait` o en
modo host con PostgreSQL en Compose. Los puertos publicados se limitan a loopback y
pueden cambiarse con `KANBAI_DB_PORT`, `KANBAI_BACKEND_PORT` y
`KANBAI_FRONTEND_PORT`.

El workflow de GitHub Actions tiene tres jobs independientes: calidad y migraciones de
backend sobre PostgreSQL 18, calidad y build de frontend, y humo de Compose. Las
instalaciones usan `uv sync --locked --dev` y `npm ci`; el workflow comprueba además
que recalcular el lockfile npm no deja cambios, y que OpenAPI y tipos generados están
versionados.

`alembic check` se ejecuta con Alembic 1.19.2, que detecta modelos sin migración. La
validación incluyó de forma aislada una columna sin migración, un test roto y un
manifiesto npm desalineado; cada escenario hizo fallar su puerta correspondiente.

La primera ejecución remota terminó en verde: [CI 34340591517](https://github.com/JMAgundezG/kanbai/actions/runs/34340591517).
