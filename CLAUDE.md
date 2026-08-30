# CLAUDE.md — kanbai

Guía operativa para trabajar en este repositorio. **Léela entera antes de tocar
código.** Si algo aquí choca con lo que ves en el código, gana el código: avísalo y
actualiza este documento.

> **Estado del repo:** los cimientos están puestos (TASK-01 y TASK-02, cerradas el
> 2026-08-30). El backend sirve `/health` y `/api/v1/health/ready` con su layout por
> capas, Alembic y tests contra PostgreSQL real; el frontend los consume con tipos
> generados del OpenAPI. **No hay dominio todavía**: ni actores, ni tableros, ni
> tarjetas. Lo que en el árbol de abajo no esté aún en disco es estructura objetivo.

---

## 0. Qué es kanbai

Un tablero kanban donde **agentes y personas trabajan en conjunto**. Los dos son el
mismo tipo de participante — un **actor** — y ambos son miembros del tablero, mueven
tarjetas, comentan y dejan rastro. La descripción de producto y el glosario del dominio
están en [`README.md`](README.md); aquí quedan solo las reglas que condicionan el código.

**Invariantes del dominio** (si una decisión de implementación choca con una de estas,
gana la invariante):

- **Un actor es persona o agente**, y el dominio **no ramifica** por ello. Un
  `if actor.kind == "agent"` dentro de un servicio o un router es señal de que el
  modelo está mal planteado. La diferencia vive en cómo se autentica (sesión frente a
  API key), no en lo que puede hacer.
- **Toda escritura queda atribuida a un actor y genera un evento.** La trazabilidad no
  es una feature opcional: es lo que hace tolerable que un agente actúe solo.
- **Un agente nunca tiene más permisos que la persona que lo dio de alta.**
- **Coordinación por reclamación:** una tarjeta se reclama con vencimiento. Dos actores
  no trabajan la misma tarjeta a la vez, y una persona siempre puede liberar la
  reclamación de un agente atascado.
- **Recurso del que no eres miembro → 404**, nunca 403 (ver § 4).

---

## 1. Cómo se trabaja aquí: el ciclo de tarea

**Regla número uno: no se implementa nada fuera del ciclo de tareas.** Cada cambio de
funcionalidad nace como una tarea del tablero y recorre cuatro fases, con una **puerta
de aprobación humana entre cada una**:

```
/work-task  →  [apruebas el plan]  →  /spec-task  →  [das el OK]  →  /implement-task  →  [code review]  →  /close-task
PLANIFICAR                            ESPECIFICAR                    IMPLEMENTAR                            COMPLETAR
En progreso                           En progreso                    En progreso → En revisión              → Completada
```

| Fase | Skill | Produce | Termina |
|------|-------|---------|---------|
| Planificar | `/work-task TASK-NN` | `docs/plans/plan-TASK-NN.md` | Parando a por tu aprobación |
| Especificar | `/spec-task TASK-NN` | `docs/plans/spec-TASK-NN.md` | Parando a por tu OK |
| Implementar | `/implement-task TASK-NN` | código + tests verificados | Dejando la tarea `En revisión` |
| Completar | `/close-task TASK-NN` | tablero y docs propagados | Tarea `Completada` |

Cada skill **se detiene** al final de su fase. Ninguna avanza a la siguiente por su
cuenta: las fases las encadena el usuario. Si algo se atasca en cualquier fase, la
tarea pasa a `Bloqueada` con el motivo anotado en `docs/tasks/STATUS.md` y en el plan.

### El tablero

- `docs/tasks/TASK-NN-<slug>.md` — una tarea por archivo (objetivo, alcance,
  criterios de aceptación, notas). Plantilla en `docs/tasks/_plantilla-tarea.md`.
- `docs/tasks/STATUS.md` — tabla `ID | Tarea | Prioridad | Depende de | Estado |
  Responsable | Notas` + bloque **Resumen** con los conteos.
- Estados: `Pendiente · En progreso · En revisión · Bloqueada · Completada`.
- Tras **cualquier** cambio de estado: recalcula el "Resumen" y actualiza
  "Última actualización" (`date +%Y-%m-%d`). Cambia solo la fila implicada.
- No se arranca una tarea con dependencias sin `Completada`.

### Fuera del ciclo

Correcciones triviales (typo, formato, un mensaje de error) pueden ir directas, sin
tarea. Cualquier cosa que toque el modelo de datos, un endpoint, el contrato o la UI
va por el ciclo.

---

## 2. Stack

Versiones de referencia comprobadas el 2026-08-30. Fija los mínimos en los manifiestos,
no los máximos.

**Backend** — Python **3.14** gestionado con **uv**; FastAPI 0.141 · Pydantic 2.13 ·
pydantic-settings 2.15 · SQLAlchemy 2.0 (async) · Alembic 1.19 · psycopg 3.3 (async) ·
uvicorn 0.52. Calidad: ruff 0.16 · mypy 2.3 (estricto) · pytest 9 + pytest-asyncio +
httpx. Runner de tareas: poethepoet, definido en `pyproject.toml`.

**Frontend** — React **19** · Vite 8 · **HeroUI v3** (`@heroui/react` +
`@heroui/styles`) sobre **Tailwind CSS v4** · **Bootstrap 5.3 solo rejilla** ·
TanStack Query 5 · React Router 8. Calidad: eslint · `tsc -b --noEmit` · Vitest +
Testing Library. Tipos de la API generados con `openapi-typescript`; cliente
`openapi-fetch`.

**TypeScript queda anclado en la 5.x** (`~5.9.3`) aunque la última sea la 7:
`openapi-typescript` exige `typescript@^5.x` y `typescript-eslint` exige `<6.1.0`. La
intersección es 5.x. Se sube cuando ambas lo permitan; no toques esa versión sin
comprobar los dos peers.

**Base de datos** — PostgreSQL 18 en Docker Compose (`compose.yaml` en la raíz),
driver `psycopg` 3 async. Los tests corren contra PostgreSQL real (`kanbai_test`), no
SQLite: el objetivo es que lo probado sea lo que se despliega. Cada test vive en una
transacción que se revierte.

---

## 3. Estructura del repositorio

```
kanbai/
├── README.md                  # qué es kanbai: producto, dominio, invariantes
├── CLAUDE.md                  # este documento
├── compose.yaml               # PostgreSQL de desarrollo y de test
├── docker/postgres/init.sql   # crea las bases kanbai y kanbai_test
├── .claude/skills/            # work-task · spec-task · implement-task · close-task
├── docs/
│   ├── tasks/                 # tablero: STATUS.md + TASK-NN-<slug>.md
│   ├── plans/                 # plan-TASK-NN.md + spec-TASK-NN.md
│   └── features/              # documentación viva por feature (la escribe close-task)
├── backend/
│   ├── pyproject.toml         # uv + dependencias + [tool.poe.tasks] + ruff/mypy/pytest
│   ├── uv.lock                # se commitea
│   ├── .python-version        # 3.14
│   ├── .env.example           # todas las variables, sin valores reales
│   ├── openapi.json           # GENERADO por `poe openapi`; se commitea
│   ├── alembic.ini
│   ├── src/kanbai/
│   │   ├── main.py            # create_app(): monta routers, middleware, lifespan
│   │   ├── core/              # config.py (Settings), security.py, exceptions.py, logging.py
│   │   ├── db/                # engine, async_sessionmaker, Base declarativa
│   │   ├── models/            # SQLAlchemy 2.0 tipado (Mapped[...])
│   │   ├── schemas/           # Pydantic: *Create / *Update / *Read
│   │   ├── repositories/      # consultas: lo único que habla SQL
│   │   ├── services/          # reglas de negocio
│   │   ├── api/
│   │   │   ├── deps.py        # SessionDep, CurrentUser, paginación
│   │   │   └── routers/       # un módulo por recurso, montados bajo /api/v1
│   │   └── migrations/        # versiones de Alembic
│   └── tests/                 # conftest.py + tests por capa
└── frontend/
    ├── package.json
    ├── vite.config.ts         # alias @/ → src/, proxy /api → backend
    └── src/
        ├── main.tsx, App.tsx
        ├── styles/global.css  # capas: bootstrap → tailwind → heroui
        ├── api/               # schema.d.ts (GENERADO) + client.ts
        ├── features/<feature>/{api.ts,hooks.ts,components/}
        ├── components/        # UI compartida entre features
        ├── routes/            # páginas / rutas
        └── lib/               # utilidades sin dependencias de React
```

**Regla de dependencias:** `routers → services → repositories → models`. Nunca al
revés, y nunca saltando capas hacia abajo (un router no ejecuta consultas). Un módulo
de `features/` del frontend no importa de otro `features/`: lo común sube a
`components/` o `lib/`.

---

## 4. Backend

### Comandos (desde `backend/`)

| Comando | Qué hace |
|---------|----------|
| `uv sync` | Instala el entorno desde `uv.lock` |
| `uv run poe dev` | Levanta la API con recarga en `:8000` |
| `uv run poe lint` | `ruff check` + `ruff format --check` |
| `uv run poe format` | `ruff format` + `ruff check --fix` |
| `uv run poe typecheck` | `mypy` |
| `uv run poe test` | `pytest` |
| `uv run poe check` | lint + typecheck + test — **la puerta antes de dar nada por hecho** |
| `uv run poe openapi` | Regenera `backend/openapi.json` (el contrato commiteado) |
| `uv run poe migrate` | `alembic upgrade head` |
| `uv run alembic revision --autogenerate -m "..."` | Nueva migración |

La base de datos se levanta desde la raíz con `docker compose up -d db`. Si falta
`kanbai_test`, el volumen es anterior a `docker/postgres/init.sql`: recréalo con
`docker compose down -v && docker compose up -d db`.

Nunca `pip install` ni `python -m venv`: **todo pasa por uv**. Dependencias con
`uv add` / `uv add --dev`; `uv.lock` se commitea siempre.

### Reglas

- **Async de punta a punta.** Endpoints `async def`, SQLAlchemy async, `httpx` async.
  Si una librería es bloqueante, aíslala en un `run_in_threadpool`; no la llames
  directamente desde un endpoint async.
- **Inyección de dependencias con `Annotated`**, no valores por defecto sueltos:
  `async def list_boards(session: SessionDep, user: CurrentUser) -> Page[BoardRead]`.
  Los alias (`SessionDep`, `CurrentUser`) viven en `api/deps.py`.
- **Configuración** en `core/config.py` con `pydantic-settings`, instancia cacheada con
  `@lru_cache` y consumida por `Depends`. Cero `os.environ` repartido por el código.
  Cada variable nueva se documenta en `.env.example`.
- **Schemas ≠ modelos.** Los endpoints reciben y devuelven Pydantic; los modelos
  SQLAlchemy no salen nunca del backend. Todo endpoint declara `response_model` (o el
  tipo de retorno) y `status_code` explícito.
- **Errores.** Errores de dominio como excepciones propias en `core/exceptions.py`,
  traducidas a HTTP por manejadores registrados en `main.py`. En los routers, `raise
  HTTPException` solo para lo puramente HTTP. Los mensajes de error visibles van en
  español y nunca filtran detalles internos (SQL, rutas, trazas).
- **Autorización explícita en cada endpoint.** Todo recurso se filtra por su dueño en
  la consulta, no después en Python. Pedir un recurso ajeno devuelve **404**, no 403:
  no confirmamos que existe.
- **Listados siempre paginados** (`limit`/`offset` con máximo), con forma
  `{items, total, page, size}`. Nada de devolver una tabla entera.
- **Migraciones.** Cambiar un modelo obliga a generar migración en la misma tarea.
  Revisa siempre el archivo autogenerado (Alembic se equivoca con índices, enums y
  renombrados) y comprueba que un `--autogenerate` posterior sale vacío.
- **App factory.** La app se construye con `create_app(settings)`; nada de una `app`
  global a nivel de módulo (importar el módulo no debe exigir entorno configurado).
  Todo lo derivado de los settings —engine, sessionmaker— cuelga de `app.state`, nunca
  de un global: un global construido con `get_settings()` haría que los tests acabaran
  escribiendo en la base de datos de desarrollo el día que algo no pase por `SessionDep`.
- **Nada de lógica en `__init__.py`**, solo reexports.
- **Tipado estricto**: `mypy` en modo estricto, sin `Any` en firmas públicas y sin
  `# type: ignore` sin comentario que explique por qué.

### Python 3.14: aprovéchalo

- Las anotaciones se evalúan de forma diferida (PEP 649): **no** hace falta
  `from __future__ import annotations`.
- Genéricos nativos y sintaxis moderna: `list[Board]`, `Board | None`, `type Alias = …`.
  Nada de `typing.List`, `Optional`, `Union`.
- `except*` para grupos de excepciones cuando lances trabajo concurrente.

### Tests

- `pytest` con `httpx.AsyncClient` + `ASGITransport` contra la app: sin servidor real.
- Cada test se ejecuta en una transacción que se revierte; los tests no comparten
  estado ni dependen del orden.
- Fixtures de datos en `conftest.py`, parametrizadas; nada de datos mágicos copiados.
- Toda feature trae, como mínimo: camino feliz, validación que falla, y acceso de un
  usuario a un recurso ajeno.
- Se testea el **comportamiento observable** (respuesta, estado en base de datos), no
  la implementación interna.

---

## 5. Frontend

### Comandos (desde `frontend/`)

| Comando | Qué hace |
|---------|----------|
| `npm run dev` | Vite en `:5173`, con proxy de `/api` al backend |
| `npm run gen:api` | Regenera `src/api/schema.d.ts` desde el OpenAPI del backend |
| `npm run lint` | eslint |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run test` | Vitest |
| `npm run check` | lint + typecheck + test — **la puerta antes de dar nada por hecho** |
| `npm run build` | Bundle de producción |

### HeroUI + Tailwind + Bootstrap: cómo conviven

HeroUI v3 **está construido sobre Tailwind CSS v4** (peer dependencies: React ≥19,
Tailwind ≥4, react-aria-components). Bootstrap trae su propio reset (*Reboot*) y su
propio sistema de utilidades, que compiten con el *preflight* de Tailwind y con los
estilos de los componentes de HeroUI. Cargar `bootstrap.css` completo **rompe** el
aspecto de HeroUI.

Convivencia soportada en este proyecto: **HeroUI manda en los componentes; Bootstrap
aporta únicamente la rejilla**, en una cascade layer por debajo de Tailwind.

```css
/* src/styles/global.css — el orden importa, y está comprobado en navegador */
@layer theme, base, bootstrap, components, utilities;

/* Solo la rejilla: .row y .col-*. Sin Reboot, sin utilidades. */
@import "bootstrap/dist/css/bootstrap-grid.css" layer(bootstrap);

@import "tailwindcss";
@import "@heroui/styles";
```

Dos restricciones opuestas fijan ese orden (ver
[docs/features/estilos-frontend.md](docs/features/estilos-frontend.md)):

- **`bootstrap` después de `base`**: el preflight de Tailwind hace
  `*{margin:0;padding:0}`, y la capa manda sobre la especificidad. Con `bootstrap`
  antes, el reset **borra los gutters de la rejilla y el padding del contenedor**.
- **`bootstrap` antes de `components`/`utilities`**: así HeroUI y Tailwind ganan
  cualquier conflicto contra Bootstrap.

Reglas derivadas, no negociables:

- **Nunca** importes `bootstrap/dist/css/bootstrap.css`, `bootstrap-reboot.css`,
  `bootstrap-utilities.css` ni el JS de Bootstrap.
- De Bootstrap se usan **solo** `.row`, `.col-*` y sus variantes responsive.
  **El contenedor de página NO es el de Bootstrap**: Tailwind v4 define su propia
  utilidad `.container` y la capa `utilities` gana siempre, así que ese nombre está
  tomado. Usa `mx-auto w-full max-w-6xl px-4`. Espaciado, tipografía, color y estados:
  Tailwind o HeroUI.
- `className` sobre un slot de HeroUI (`Card.Content`) no sustituye a los estilos del
  slot: mete tu layout en un `div` dentro de él.
- Componentes interactivos (botones, inputs, modales, tablas, dropdowns, toasts):
  **siempre HeroUI**, nunca markup de Bootstrap. HeroUI se apoya en React Aria y nos
  da la accesibilidad; reimplementarla a mano es un error.
- HeroUI v3 **no** requiere `<Provider>`. El tema claro/oscuro se controla en `<html>`.
- Si un caso necesita algo de Bootstrap fuera de la rejilla, se discute antes: es señal
  de que falta un componente propio, no de que haya que importar más Bootstrap.

### Reglas

- **Estado de servidor con TanStack Query**, no `useEffect` + `fetch`. Claves de query
  jerárquicas (`['boards']`, `['boards', id]`) y la invalidación correspondiente en
  cada mutación. El estado de servidor no se duplica en `useState`.
- **Tipos generados, nunca escritos a mano.** Todo lo que venga de la API se tipa
  desde `src/api/schema.d.ts`. Si escribes una `interface` que refleja una respuesta
  del backend, lo estás haciendo mal.
- **Estructura por feature.** Cada feature se lleva su `api.ts`, sus hooks y sus
  componentes. Lo compartido sube; no hay imports cruzados entre features.
- **Componentes tontos + hooks con la lógica.** Un componente que hace fetch, formatea
  y renderiza se parte en tres.
- Toda vista contempla explícitamente **carga, vacío y error**. Nada de pantallas en
  blanco cuando la API falla.
- Sin `any` y sin `@ts-expect-error` sin comentario. `strict` activado.
- Tests con Testing Library sobre lo que ve el usuario (roles, texto), no sobre
  detalles internos ni snapshots gigantes.

---

## 6. El contrato front ↔ back

El contrato lo **manda el backend** y el frontend lo **consume generado**:

```
response_model (FastAPI)  →  uv run poe openapi  →  backend/openapi.json (commiteado)
                          →  npm run gen:api  →  src/api/schema.d.ts  →  tsc
```

`backend/openapi.json` se versiona a propósito: así un cambio de contrato aparece en el
diff de la code review, y el frontend genera tipos sin necesidad de levantar el servidor.
`tests/test_openapi.py` falla si el archivo y el código divergen.

- Cambias un `response_model` o un endpoint → en la **misma tarea** regeneras
  `schema.d.ts` y arreglas lo que rompa `tsc`. Un contrato desincronizado es un fallo
  de la tarea, no deuda para luego.
- `src/api/schema.d.ts` es **generado**: no se edita a mano jamás.
- Un cambio incompatible en un endpoint ya consumido se anota en la spec de la tarea
  con su plan de migración.

---

## 7. Convenciones transversales

- **Idioma.** Textos de cara al usuario (UI, mensajes de error, docs del repo): en
  **español**. Identificadores, nombres de archivo, comentarios, mensajes de commit y
  ramas: en **inglés**.
- **Nombres.** Python `snake_case`; TypeScript `camelCase` para valores y
  `PascalCase` para componentes y tipos; rutas de API en plural y kebab-case
  (`/api/v1/boards`, `/api/v1/board-columns`).
- **Comentarios.** Explican el *porqué*, no el *qué*. Sin comentarios decorativos ni
  bloques de código muerto: para eso está el historial.
- **Secretos.** Nunca en el repo. Variables de entorno documentadas en `.env.example`
  con valores de mentira. Ningún secreto en logs ni en respuestas de error.
- **Git.** No se hace commit salvo que el usuario lo pida. Cuando lo pida: ramas
  `task/TASK-NN-<slug>`, mensajes imperativos en inglés referenciando la tarea
  (`Add board reordering endpoint (TASK-07)`).
- **Dependencias nuevas.** Se justifican en la spec de la tarea antes de añadirlas.
  Preferimos la librería estándar y lo que ya está en el proyecto.

---

## 8. Definición de "hecho"

Una tarea no está lista para pasar a `En revisión` hasta que **todo** esto es cierto:

- [ ] Se cumplen los criterios de aceptación del archivo `TASK-NN-*.md`.
- [ ] `uv run poe check` en verde desde `backend/`.
- [ ] `npm run check` en verde desde `frontend/`.
- [ ] Hay tests nuevos que cubren lo implementado (feliz, error y permisos).
- [ ] Si cambió el modelo: migración generada, revisada y aplicada.
- [ ] Si cambió el contrato: `schema.d.ts` regenerado y `tsc` limpio.
- [ ] `.env.example` y `docs/features/*` actualizados si aplica.

**No declares nada verificado sin haber ejecutado los comandos.** Pega la salida real.
Si un test falla, dilo con su salida; si algo se ha quedado fuera, dilo explícitamente.

---

## 9. Errores que no queremos ver

| Anti-patrón | Qué hacer en su lugar |
|-------------|------------------------|
| Implementar sin plan y spec aprobados | Pasar por el ciclo de 4 fases |
| `pip install` / `venv` a mano | `uv add`, `uv sync` |
| Consultas SQL dentro de un router | Bajarlas al repositorio |
| Devolver un modelo SQLAlchemy | Devolver un schema Pydantic |
| Escribir a mano tipos de la API en el frontend | `npm run gen:api` |
| Importar todo Bootstrap | Solo `bootstrap-grid.css` en su layer |
| Reimplementar un botón/modal con markup propio | Usar el componente de HeroUI |
| `useEffect` + `fetch` para datos del servidor | TanStack Query |
| Cambiar un modelo sin migración | Generar y revisar la migración en la misma tarea |
| Devolver 403 en recursos ajenos | 404, sin confirmar existencia |
| Marcar `Completada` sin `close-task` | `/close-task TASK-NN` propaga y cierra |
