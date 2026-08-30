# Spec · TASK-01 · Scaffold del backend (uv + Python 3.14 + FastAPI)

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-01](plan-TASK-01.md) · **Tarea:** [TASK-01](../tasks/TASK-01-scaffold-backend.md)

## Decisiones cerradas al aprobar el plan

| Decisión | Resolución |
|----------|------------|
| Base de datos de desarrollo y test | **PostgreSQL 18 en Docker Compose** (`compose.yaml` en la raíz del repo) |
| `poe openapi` | **Sí.** Vuelca `backend/openapi.json`, que **se commitea** y un test mantiene sincronizado |
| Driver | `psycopg` 3 async (`postgresql+psycopg://`), el mismo para la app y para Alembic |
| Nombre del paquete | `kanbai` |
| Autenticación | Fuera de alcance. `deps.py` deja el hueco documentado para `CurrentUser` |

---

## Árbol de archivos a crear

```
kanbai/
├── compose.yaml                          # PostgreSQL 18 (dev + test)
├── docker/postgres/init.sql              # crea las BBDD kanbai y kanbai_test
└── backend/
    ├── .python-version                   # 3.14
    ├── .env.example
    ├── .gitignore
    ├── alembic.ini
    ├── openapi.json                      # GENERADO por `poe openapi`, commiteado
    ├── pyproject.toml
    ├── uv.lock
    ├── src/kanbai/
    │   ├── __init__.py                   # __version__ solo
    │   ├── main.py
    │   ├── openapi.py                    # entrypoint de `poe openapi`
    │   ├── core/{__init__,config,exceptions,logging}.py
    │   ├── db/{__init__,base,session}.py
    │   ├── models/__init__.py            # vacío (reexports), sin modelos aún
    │   ├── schemas/{__init__,health}.py
    │   ├── repositories/__init__.py      # vacío (reexports)
    │   ├── services/__init__.py          # vacío (reexports)
    │   ├── api/
    │   │   ├── __init__.py
    │   │   ├── deps.py
    │   │   ├── router.py                 # APIRouter raíz de /api/v1
    │   │   └── routers/{__init__,health}.py
    │   └── migrations/
    │       ├── env.py                    # plantilla async, URL desde Settings
    │       ├── script.py.mako
    │       └── versions/<rev>_initial.py # vacía a propósito
    └── tests/
        ├── conftest.py
        ├── test_health.py
        └── test_openapi.py
```

---

## Backend (`backend/src/kanbai/`)

### Modelos (`models/`)

**No hay modelos de dominio en esta tarea.** Se crea `models/__init__.py` vacío para
fijar la capa. Lo que sí se define es la **base declarativa** y su convención de
nombres, porque condiciona todas las migraciones futuras:

`db/base.py`:

```python
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })
```

Sin esta convención Alembic genera constraints con nombres autogenerados por PostgreSQL
y los `--autogenerate` posteriores producen diffs falsos. Se fija ahora, cuando no
cuesta nada.

### Sesión y engine (`db/session.py`)

- `engine = create_async_engine(str(settings.database_url), pool_pre_ping=True, echo=settings.db_echo)`.
- `AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)`.
  `expire_on_commit=False` es obligatorio en async: si no, acceder a un atributo después
  del commit dispara IO implícito fuera del `await`.
- Dependencia:

  ```python
  async def get_session() -> AsyncIterator[AsyncSession]:
      async with AsyncSessionLocal() as session:
          try:
              yield session
          except Exception:
              await session.rollback()
              raise
  ```

  **El commit lo hace la capa de servicios**, no la dependencia: un endpoint que agrupa
  dos operaciones debe poder decidir la unidad de trabajo. Se documenta en el docstring.
- El engine se cierra (`await engine.dispose()`) en el `lifespan` de la app.

### Configuración (`core/config.py`)

`Settings(BaseSettings)` con `model_config = SettingsConfigDict(env_prefix="KANBAI_",
env_file=".env", extra="forbid")` y `@lru_cache` en `get_settings()`.

| Campo | Tipo | Por defecto | Notas |
|-------|------|-------------|-------|
| `app_name` | `str` | `"kanbai"` | Título del OpenAPI |
| `environment` | `Literal["local", "test", "production"]` | `"local"` | |
| `debug` | `bool` | `False` | |
| `database_url` | `PostgresDsn` | — | **Obligatoria**, sin valor por defecto |
| `db_echo` | `bool` | `False` | Log de SQL |
| `api_v1_prefix` | `str` | `"/api/v1"` | |
| `cors_origins` | `list[AnyHttpUrl]` | `["http://localhost:5173"]` | Origen de Vite |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR"]` | `"INFO"` | |

`extra="forbid"` hace que una variable `KANBAI_*` mal escrita reviente al arrancar en
lugar de ignorarse en silencio. `database_url` sin default fuerza que arrancar sin
configurar la base de datos falle rápido y con mensaje claro.

### Excepciones (`core/exceptions.py`) y sus manejadores

```python
class KanbaiError(Exception):          # base del dominio
    mensaje_por_defecto: str
class NotFoundError(KanbaiError): ...   # → 404
class ConflictError(KanbaiError): ...   # → 409
class ValidationError(KanbaiError): ... # → 422
```

En `main.py` se registra **un solo** `exception_handler(KanbaiError)` que consulta un
mapa `type → status_code` y responde `{"detail": "<mensaje en español>"}`. Se añade
también un handler de `Exception` que loguea la traza y devuelve `500` con
`{"detail": "Error interno del servidor."}` — nunca la traza (`CLAUDE.md` § 4).

Nota deliberada: **no hay `PermissionDeniedError`**. Según `CLAUDE.md`, un recurso ajeno
devuelve 404, así que el caso de permisos se expresa con `NotFoundError`.

### Logging (`core/logging.py`)

`configure_logging(level: str) -> None` con `logging.config.dictConfig`: formateador de
una línea con timestamp ISO, nivel, logger y mensaje; se aplica también a `uvicorn.access`
para que no haya dos formatos distintos en la misma consola. Sin dependencias extra.

### Dependencias de API (`api/deps.py`)

```python
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
# CurrentUser llegará con la tarea de autenticación; los endpoints que necesiten
# usuario la añadirán aquí como Annotated[User, Depends(get_current_user)].
```

### Router (`api/routers/health.py`, `api/router.py`)

Dos endpoints, no uno. La distinción importa para desplegar y además cumple los dos
objetivos a la vez (criterio de aceptación literal + rodaja vertical del plan):

| Método | Ruta | `status_code` | `response_model` | Toca BD |
|--------|------|---------------|------------------|---------|
| GET | `/health` | 200 | `HealthRead` | No |
| GET | `/api/v1/health/ready` | 200 / 503 | `ReadinessRead` | Sí (`SELECT 1`) |

- `/health` es **liveness**: fuera del prefijo versionado, responde exactamente
  `{"status": "ok"}` sin tocar nada. Es lo que interrogará un orquestador.
- `/api/v1/health/ready` es **readiness**: usa `SessionDep` y ejecuta
  `await session.execute(text("SELECT 1"))`. Devuelve `{"status": "ok", "database": "ok"}`.
  Si la base de datos no responde, captura `SQLAlchemyError`, loguea y responde **503**
  con `{"status": "error", "database": "error"}` — no propaga el error de la BD al
  cliente.
- `api/router.py` expone `api_router = APIRouter(prefix=settings.api_v1_prefix)` e
  incluye `health.router` con `tags=["health"]`. Cada recurso futuro se cuelga aquí.

### Schemas (`schemas/health.py`)

```python
class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"

class ReadinessRead(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]
```

### App factory (`main.py`)

`create_app(settings: Settings | None = None) -> FastAPI`:

1. `settings = settings or get_settings()`; `configure_logging(settings.log_level)`.
2. `lifespan`: al cerrar, `await engine.dispose()`.
3. `FastAPI(title=..., version=__version__, lifespan=..., docs_url="/docs", openapi_url="/openapi.json")`.
4. `CORSMiddleware` con `allow_origins=[str(o) for o in settings.cors_origins]`,
   `allow_credentials=True`, métodos y cabeceras concretos (no `*` junto a credenciales).
5. Registro de los manejadores de excepciones.
6. `app.include_router(health.liveness_router)` (sin prefijo) y `app.include_router(api_router)`.
7. `app = create_app()` a nivel de módulo para `uvicorn kanbai.main:app`.

Aceptar `settings` como parámetro es lo que permite a los tests construir la app contra
la base de datos de test sin tocar variables de entorno globales.

### Exportador de OpenAPI (`openapi.py`)

`python -m kanbai.openapi` construye la app, llama a `app.openapi()` y escribe
`backend/openapi.json` con `indent=2` y `sort_keys=True` (diffs estables) y salto de
línea final. Se commitea: así el contrato aparece en la code review y TASK-02 puede
generar tipos sin levantar el servidor.

---

## Migración (`migrations/`)

- Se genera con `uv run alembic init -t async src/kanbai/migrations` y se mueve la
  configuración a `alembic.ini` con `script_location = src/kanbai/migrations`.
- `env.py` **no** lee la URL de `alembic.ini` (`sqlalchemy.url` se deja vacío): la toma
  de `get_settings().database_url`. Una sola fuente de verdad, y ningún secreto en un
  archivo versionado.
- `target_metadata = Base.metadata`, con `from kanbai import models  # noqa: F401` para
  que las futuras tablas se registren.
- En `context.configure` se activa `compare_type=True` y `compare_server_default=True`,
  para que `--autogenerate` detecte cambios de tipo (por defecto los ignora).
- **Revisión inicial vacía**: `upgrade()` y `downgrade()` con `pass`. No hay tablas
  todavía; su función es demostrar que la cadena `alembic upgrade head` funciona y dar
  un punto de anclaje (`down_revision = None`) a las siguientes.

---

## Manifiestos y comandos

### `pyproject.toml`

- `[project]`: `name = "kanbai"`, `requires-python = ">=3.14"`, `dynamic = ["version"]`.
- Dependencias (mínimos, no máximos, según `CLAUDE.md` § 2):
  `fastapi>=0.141`, `pydantic>=2.13`, `pydantic-settings>=2.15`,
  `sqlalchemy[asyncio]>=2.0.52`, `alembic>=1.19`, `psycopg[binary,pool]>=3.3`,
  `uvicorn[standard]>=0.52`.
- `[dependency-groups] dev` (vía `uv add --dev`): `ruff>=0.16`, `mypy>=2.3`,
  `pytest>=9.1`, `pytest-asyncio>=1.4`, `pytest-cov>=7.1`, `httpx>=0.28`,
  `poethepoet>=0.48`.
- `[tool.hatch.build.targets.wheel] packages = ["src/kanbai"]`.

`[tool.poe.tasks]`:

| Tarea | Comando |
|-------|---------|
| `dev` | `uvicorn kanbai.main:app --reload --port 8000` |
| `lint` | `ruff check .` |
| `format` | secuencia: `ruff format .` + `ruff check --fix .` |
| `typecheck` | `mypy src tests` |
| `test` | `pytest` |
| `check` | secuencia: `lint` + `typecheck` + `test` |
| `openapi` | `python -m kanbai.openapi` |
| `migrate` | `alembic upgrade head` |

`[tool.ruff]`: `line-length = 100`, `target-version = "py314"`.
`[tool.ruff.lint] select = ["E","W","F","I","N","UP","B","C4","SIM","ASYNC","T20","RUF"]`,
con `per-file-ignores` para `tests/**` (permite asserts y fixtures sin docstring) y para
`migrations/**` (código generado). `T20` prohíbe `print` en código de producción.

`[tool.mypy]`: `strict = true`, `python_version = "3.14"`, `plugins = ["pydantic.mypy"]`,
`warn_unreachable = true`, `exclude = ["src/kanbai/migrations/versions/"]` (las
revisiones son generadas y no aportan tipado). mypy 2.x ya trae `--strict-bytes` y
`--local-partial-types` activados por defecto; no hay que configurarlos.

`[tool.pytest.ini_options]`: `asyncio_mode = "auto"`,
`asyncio_default_fixture_loop_scope = "session"` (si se deja sin fijar, pytest-asyncio
avisa y el default cambiará en versiones futuras), `testpaths = ["tests"]`,
`addopts = "-q --strict-markers --strict-config"`.

### `compose.yaml` (raíz del repo)

Servicio `db`: imagen `postgres:18-alpine`, `POSTGRES_USER=kanbai`,
`POSTGRES_PASSWORD=kanbai`, `POSTGRES_DB=kanbai`, puerto `5432:5432`, volumen nombrado
para los datos y `./docker/postgres/init.sql` montado en
`/docker-entrypoint-initdb.d/`, que hace `CREATE DATABASE kanbai_test;`. Healthcheck con
`pg_isready`. Las credenciales son de desarrollo local y así se indica en el archivo.

### `.env.example`

```
KANBAI_ENVIRONMENT=local
KANBAI_DEBUG=true
KANBAI_LOG_LEVEL=INFO
KANBAI_DATABASE_URL=postgresql+psycopg://kanbai:kanbai@localhost:5432/kanbai
KANBAI_DB_ECHO=false
KANBAI_CORS_ORIGINS=["http://localhost:5173"]
```

Valores de desarrollo, sin secretos reales. La URL de test
(`.../kanbai_test`) la fija `conftest.py`, no el `.env`.

---

## Contrato API

Esta tarea **crea** el contrato del que vivirá TASK-02.

```
GET /health                  →  200  {"status": "ok"}
GET /api/v1/health/ready     →  200  {"status": "ok", "database": "ok"}
                             →  503  {"status": "error", "database": "error"}
```

`GET /openapi.json` sirve el esquema; `poe openapi` lo vuelca a `backend/openapi.json`.
Todavía no hay listados, así que la forma de paginación `{items, total, page, size}` de
`CLAUDE.md` § 4 se implementará en la primera tarea que devuelva colecciones.

---

## Casos límite y errores

| Caso | Comportamiento esperado |
|------|-------------------------|
| Falta `KANBAI_DATABASE_URL` | La app **no arranca**: `ValidationError` de pydantic-settings con el nombre de la variable |
| Variable `KANBAI_*` desconocida | Falla al arrancar (`extra="forbid"`), no se ignora |
| Base de datos caída | `/health` sigue devolviendo 200; `/health/ready` devuelve 503 sin filtrar el error de PostgreSQL |
| Excepción no controlada en un endpoint | 500 con `{"detail": "Error interno del servidor."}`; la traza va al log, nunca a la respuesta |
| `openapi.json` desactualizado respecto al código | `test_openapi.py` falla y `poe check` se pone en rojo |
| Migraciones sin aplicar en la BD de test | La fixture de sesión aplica `alembic upgrade head` antes del primer test |
| Petición desde un origen no listado en `cors_origins` | Bloqueada por CORS |

---

## Plan de tests

`tests/conftest.py` — cuatro fixtures, en este orden:

1. `settings` (sesión): `Settings(database_url=...kanbai_test, environment="test")`.
   Falla con mensaje claro si la base de datos de test no está accesible.
2. `engine` (sesión): crea el engine de test y aplica las migraciones con
   `await asyncio.to_thread(command.upgrade, alembic_cfg, "head")`. Va en un hilo aparte
   **porque el `env.py` async de Alembic llama a `asyncio.run()`**, que reventaría dentro
   del bucle de eventos del test. Al terminar la sesión, `dispose()`.
3. `db_session` (función): abre conexión, `begin()`, y crea la `AsyncSession` con
   `join_transaction_mode="create_savepoint"`, de modo que un `commit()` del código bajo
   test se convierte en savepoint y **todo se revierte** al hacer `rollback()` de la
   transacción externa. Aislamiento real sin recrear el esquema por test.
4. `client` (función): `create_app(settings)` con
   `app.dependency_overrides[get_session] = lambda: db_session`, servida por
   `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.

Casos a cubrir:

| Test | Comprueba |
|------|-----------|
| `test_health_devuelve_ok` | `GET /health` → 200 y cuerpo exactamente `{"status": "ok"}` |
| `test_ready_consulta_la_base_de_datos` | `GET /api/v1/health/ready` → 200 con `database: "ok"` (recorre la pila entera) |
| `test_ready_devuelve_503_si_la_base_de_datos_falla` | Con la dependencia sustituida por una sesión que lanza `SQLAlchemyError`: 503 y **sin** detalles de PostgreSQL en el cuerpo |
| `test_ruta_inexistente_devuelve_404` | Un 404 de FastAPI no filtra información |
| `test_openapi_json_esta_sincronizado` | `json.loads(Path("openapi.json"))` == `create_app().openapi()`; el mensaje de fallo indica ejecutar `uv run poe openapi` |
| `test_settings_falla_sin_database_url` | Instanciar `Settings` sin la variable lanza `ValidationError` |

No hay tests de permisos todavía porque no hay recursos con dueño; la primera tarea de
dominio los traerá (`CLAUDE.md` § 4).

**Frontend:** no aplica en esta tarea.

**Verificación end-to-end manual** (a pegar en el reporte de `implement-task`):
`docker compose up -d db` → `uv sync` → `uv run poe migrate` → `uv run poe dev` →
`curl -s localhost:8000/health`, `curl -s localhost:8000/api/v1/health/ready` y `/docs`
cargando en el navegador. Después, `docker compose stop db` y comprobar que
`/health/ready` responde 503 mientras `/health` sigue en 200.

---

## Desviaciones respecto al plan

1. **`/health` se parte en dos endpoints** (liveness sin BD + readiness con BD). El plan
   pedía que "la rodaja vertical toque la base de datos" y el criterio de aceptación
   pide que `/health` responda exactamente `{"status": "ok"}`. Separarlos cumple ambos y
   además es la distinción correcta para producción. `/health` queda **fuera** del
   prefijo `/api/v1` por la misma razón.
2. **`backend/openapi.json` se commitea** y un test lo mantiene sincronizado. El plan
   solo preveía la tarea `poe openapi`. El archivo versionado hace que un cambio de
   contrato sea visible en la code review, que es justo lo que `CLAUDE.md` § 6 quiere
   evitar que se pierda.
3. **Convención de nombres de constraints en `Base.metadata`**, no mencionada en el
   plan. Es barata ahora e imposible de introducir sin dolor una vez existan tablas.
4. `compose.yaml` y `docker/postgres/init.sql` viven en la **raíz del repo**, no dentro
   de `backend/`, porque la base de datos es infraestructura del proyecto entero.

5. **No hay `app = create_app()` a nivel de módulo.** La spec preveía
   `uvicorn kanbai.main:app`; se usa `uvicorn kanbai.main:create_app --factory`. Con la
   variable global, importar `kanbai.main` exigía entorno configurado, lo que rompía
   `poe openapi` en un clon recién hecho. Con `--factory` no hay efectos al importar.
6. **`extra="forbid"` no rechaza variables de entorno desconocidas**, solo claves del
   `.env` y argumentos explícitos: pydantic-settings únicamente busca en el entorno los
   nombres que conoce. La tabla de casos límite decía lo contrario; el test
   (`test_settings_rechaza_claves_desconocidas_en_el_env`) comprueba el comportamiento
   real y el docstring de `Settings` lo documenta.
7. **El `SELECT 1` no vive en el router.** La spec lo ponía en el endpoint de readiness,
   lo que violaría la regla de capas de `CLAUDE.md` («nada de consultas SQL en un
   router»). Está en `repositories/health.py`, con `services/health.py` decidiendo qué
   hacer con el fallo. De paso, las capas `repositories` y `services` quedan estrenadas
   con un ejemplo real en vez de con carpetas vacías.
8. **El status HTTP se mapea con un atributo de clase** (`KanbaiError.status_code`) en
   lugar de un diccionario `tipo → status` en `main.py`. Mismo efecto, pero añadir un
   error nuevo no obliga a tocar dos archivos.
9. **`compose.yaml` monta el volumen en `/var/lib/postgresql`**, no en `.../data`:
   `postgres:18` cambió la convención y con la ruta antigua el contenedor se niega a
   arrancar. Descubierto al levantarlo.
10. **Dos tests extra** sobre los seis especificados: liveness sigue respondiendo 200 con
    la base de datos caída, y `.env` con clave desconocida.

## Correcciones tras la code review

La review de `/code-review` sacó 7 hallazgos; los 7 eran correctos y están corregidos:

| # | Hallazgo | Corrección |
|---|----------|------------|
| 1 | `build_schema()` construía `Settings` con la DSN de relleno pero **seguía leyendo el resto del entorno**: `KANBAI_APP_NAME` y `KANBAI_API_V1_PREFIX` alimentan el esquema, así que el `openapi.json` commiteado dependía de la máquina | `SchemaSettings` sobrescribe `settings_customise_sources` y deja **solo** `init_settings`; test nuevo `test_el_esquema_no_depende_del_entorno` |
| 2 | `get_engine()` usaba el `get_settings()` cacheado, no los settings pasados a `create_app()`. La suite solo esquivaba la base de datos de desarrollo porque sobrescribe `get_session`; cualquier código que abriera su propia sesión habría escrito en `kanbai` real | Engine, sessionmaker y settings viven en `app.state`; `get_session` los toma del `Request`. Sin globales de módulo. Test nuevo `test_la_app_usa_los_settings_que_recibe` |
| 3 | `handle_kanbai_error` no logueaba: un `KanbaiError` de 5xx desaparecía sin rastro | Loguea con traza cuando `status_code >= 500` |
| 4 | `/docs` y `/openapi.json` se publicaban siempre, y `debug` no lo leía nadie | La doc se apaga con `environment == "production"` (verificado a mano); `debug` se elimina en vez de fingir que hace algo |
| 5 | `.env.example` no documentaba `KANBAI_APP_NAME` ni `KANBAI_API_V1_PREFIX` (criterio de aceptación: «documenta todas las variables») | Documentadas, señalando que forman parte del contrato |
| 6 | El mensaje de la fixture mandaba levantar el contenedor, pero si falta `kanbai_test` la causa real es un volumen anterior a `init.sql` | El mensaje explica que hay que recrear el volumen (`docker compose down -v`) |
| 7 | `script.py.mako` generaba `Union[str, Sequence[str], None]`, sintaxis prohibida por `CLAUDE.md` § 4, y las exclusiones de ruff/mypy hacían que nadie fuera a detectarlo nunca | Plantilla y revisión existente pasadas a `str | Sequence[str] | None` |

## Riesgos que siguen abiertos

- ~~**`greenlet` en Python 3.14**~~ — **cerrado**: `greenlet 3.5.5` instaló rueda
  precompilada para 3.14, sin compilar nada.
- ~~**`mypy --strict` sobre las fixtures async**~~ — **cerrado**: `mypy` estricto pasa
  sobre `src` y `tests` **sin un solo `# type: ignore`** en el código.
- **Aún sin cubrir**: no hay tests de permisos (404 sobre recurso ajeno) porque todavía
  no existen recursos con dueño; llegan con la primera tarea de dominio. Tampoco hay
  paginación implementada por el mismo motivo.
