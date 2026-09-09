# TASK-17 · Integración continua y entorno reproducible

**Prioridad:** Media · **Depende de:** TASK-01, TASK-02

## Objetivo

Que la puerta de calidad que describe `AGENTS.md` § 8 se ejecute sola en cada cambio, y
que levantar el proyecto desde cero sea un comando y no una sesión de arqueología.

## Alcance

**Entra:**
- `compose.yaml` con PostgreSQL para desarrollo y para los tests.
- Flujo de integración continua que ejecuta `uv run poe check` y `npm run check`.
- Comprobación automática de que `alembic upgrade head` aplica y de que un
  `alembic revision --autogenerate` posterior **sale vacío**.
- Instrucciones de arranque desde cero en `README.md`.
- Caché de dependencias de `uv` y `npm` para que la integración continua sea usable.

**No entra:**
- Despliegue, imágenes de producción, entornos remotos.
- Publicación de artefactos o versionado.

## Estado de implementación

Completada el 2026-09-09. La implementación y las verificaciones locales están
publicadas, y los tres jobs de GitHub Actions finalizaron correctamente en la
[ejecución 34340591517](https://github.com/JMAgundezG/kanbai/actions/runs/34340591517).

## Criterios de aceptación

- [x] `docker compose up -d db` y las instrucciones del `README.md` dejan el proyecto
      funcionando desde un clon limpio.
- [x] La integración continua pasa en verde sobre el estado actual del repositorio.
- [x] Falla, y se ve por qué, si un test falla o si queda una migración sin generar.
- [x] Los tests corren contra **PostgreSQL real**, no SQLite (`AGENTS.md` § 2).

## Notas técnicas

- Es adelantable: en cuanto TASK-01 y TASK-02 estén cerradas, cuanto antes se haga,
  menos regresiones silenciosas arrastran las tareas siguientes.
