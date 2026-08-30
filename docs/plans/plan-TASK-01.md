# Plan · TASK-01 · Scaffold del backend (uv + Python 3.14 + FastAPI)

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-01](../tasks/TASK-01-scaffold-backend.md)

## Objetivo

Dejar `backend/` como un proyecto FastAPI ejecutable y verificable: uv gestionando el
entorno con Python 3.14, el layout por capas de `CLAUDE.md` § 3, configuración con
pydantic-settings, base de datos async con Alembic ya conectado, y la puerta de calidad
`uv run poe check` en verde. No implementa dominio ni autenticación: implementa el
**esqueleto sobre el que se apoyará toda feature posterior**.

El listón: alguien clona el repo, ejecuta `uv sync`, levanta la base de datos, corre
`uv run poe check` y todo pasa sin un solo paso manual no documentado.

## Enfoque

Un esqueleto **vertical y mínimo pero completo**: en lugar de crear carpetas vacías,
`/health` recorre de verdad la pila (router → dependencia de sesión → base de datos) y
un test cubre ese recorrido. Así el andamiaje queda demostrado, no supuesto, y las
features siguientes copian un patrón que ya funciona.

Decisiones de partida y por qué:

- **`create_app()` (app factory) en `main.py`**, no una `app` global. Permite construir
  la app con settings distintos en los tests y es lo que espera `ASGITransport`.
- **Driver `psycopg` 3 en modo async** en vez de `asyncpg`: un único driver sirve para
  la app *y* para Alembic, y SQLAlchemy 2.0 lo soporta de primera. Menos piezas.
- **PostgreSQL en Docker Compose** para desarrollo y tests (Docker 29.7 y Compose v5.1
  están disponibles en la máquina; también hay un PostgreSQL 18 por Homebrew como
  alternativa). Los tests corren contra PostgreSQL real, según `CLAUDE.md` § 2.
- **Aislamiento de tests por transacción**: cada test abre una conexión, empieza una
  transacción externa y hace *rollback* al terminar; el esquema se crea una vez por
  sesión aplicando las migraciones. Sin estado compartido, sin dependencia del orden.
- **`poethepoet` como runner** declarado en `pyproject.toml`, para que `check` sea el
  mismo comando en local y en CI.
- **Alembic con plantilla async** (`alembic init -t async`), con `env.py` leyendo la URL
  desde `Settings` en lugar de duplicarla en `alembic.ini`.
- La migración inicial es **vacía a propósito**: solo demuestra que la cadena
  `alembic upgrade head` funciona. Las tablas llegan con las tareas de dominio.
- `deps.py` expondrá `SessionDep` ya funcional y dejará **anotado** dónde entrará
  `CurrentUser`, sin implementar autenticación (no entra en esta tarea).

Alternativas descartadas: SQLite para tests (rompe la promesa de "probamos lo que
desplegamos"), `Makefile` en lugar de poe (deja la definición fuera de `pyproject.toml`),
y un scaffold generado con plantillas de terceros (arrastra convenciones que chocan con
`CLAUDE.md`).

## Alcance

- **Backend (`backend/`)** — todo el trabajo está aquí:
  - Manifiestos: `pyproject.toml` (deps + `[tool.poe.tasks]` + ruff/mypy/pytest),
    `uv.lock`, `.python-version`, `.env.example`, `.gitignore`.
  - `src/kanbai/main.py` — `create_app()`, montaje del router `/api/v1`, lifespan,
    manejadores de excepciones, CORS para `:5173`.
  - `src/kanbai/core/` — `config.py` (Settings + `@lru_cache`), `exceptions.py`
    (excepciones de dominio base), `logging.py`.
  - `src/kanbai/db/` — engine async, `async_sessionmaker`, `Base` declarativa.
  - `src/kanbai/api/` — `deps.py` (`SessionDep`), `routers/health.py`, router raíz.
  - `src/kanbai/{models,schemas,repositories,services}/` — creados con sus `__init__.py`
    (solo reexports) para fijar el layout por capas.
  - `migrations/` + `alembic.ini` — Alembic async y revisión inicial.
  - `tests/` — `conftest.py` (fixtures de app, cliente y sesión con rollback) y
    `test_health.py`.
  - `compose.yaml` en la raíz del repo — PostgreSQL de desarrollo y de test.
- **Frontend:** no se toca (llega en TASK-02).
- **Contrato:** esta tarea **crea** el OpenAPI (`/openapi.json`) del que TASK-02
  generará los tipos. Además expondrá `poe openapi`, que vuelca el esquema a un archivo
  para que `npm run gen:api` no dependa de tener el servidor levantado.

## Criterios de aceptación

- [x] `uv sync` funciona partiendo del repo limpio y `uv run python -V` dice 3.14.x.
- [x] `uv run poe dev` levanta la API y `GET /health` responde `{"status": "ok"}`.
- [x] `/docs` muestra el OpenAPI.
- [x] `uv run poe check` (ruff + mypy estricto + pytest) pasa en verde.
- [x] `alembic upgrade head` aplica sin errores sobre una base de datos vacía.
- [x] No hay secretos en el repo; `.env.example` documenta todas las variables.

## Plan de verificación

- `uv sync` y `uv run python -V` desde `backend/` (comprueba que uv resuelve 3.14).
- `docker compose up -d db` y `uv run alembic upgrade head` sobre la base vacía; después
  `uv run alembic revision --autogenerate` debe salir **sin cambios detectados**.
- `uv run poe check` desde `backend/`: ruff, mypy estricto y pytest, con la salida real
  pegada en el reporte de `implement-task`.
- End-to-end manual: `uv run poe dev` + `curl localhost:8000/health` y `/docs` abierto.

## Riesgos / decisiones abiertas

1. **PostgreSQL vía Docker Compose** es mi propuesta (hay Docker operativo en la
   máquina). Si prefieres el PostgreSQL 18 de Homebrew que ya tienes instalado, dilo en
   la fase de spec y cambio `compose.yaml` por instrucciones de `.env`.
2. **`mypy` en modo estricto sobre Python 3.14 con SQLAlchemy 2.0**: el soporte es
   bueno, pero si algún stub se queda corto se resolverá con `# type: ignore` comentado
   y acotado, nunca relajando la configuración global.
3. **Nombre del paquete**: `kanbai` (según `CLAUDE.md` § 3). Si el proyecto va a
   publicarse con otro nombre de distribución, ahora es el momento barato de cambiarlo.
4. **`poe openapi` volcando el esquema a un archivo** es un añadido sobre lo escrito en
   `CLAUDE.md`; simplifica TASK-02 y CI. Si no lo quieres, `gen:api` exigirá backend
   levantado.
5. **CORS** se abrirá solo para el origen de Vite en desarrollo; la política de
   producción se decidirá cuando haya despliegue.
6. **Doc interactiva**: `/docs` y `/openapi.json` se publican salvo con
   `KANBAI_ENVIRONMENT=production`. Decidido durante la code review.
