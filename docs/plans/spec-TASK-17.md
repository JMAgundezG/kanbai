# Spec · TASK-17 · Integración continua y entorno reproducible

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-09-08 · **Cerrado:** 2026-09-09
**Plan:** [plan-TASK-17](plan-TASK-17.md) · **Tarea:** [TASK-17](../tasks/TASK-17-ci-y-entorno.md)
**Responsable:** Codex · **Aprobación:** Aprobada para implementación

## Decisiones y precondiciones

Plan aprobado por el usuario. TASK-01 y TASK-02 están completadas y TASK-17 continúa
En progreso. Se adopta GitHub Actions como proveedor de CI. Es una decisión reversible:
los comandos de instalación y calidad permanecen en el repositorio y podrán invocarse
desde otro proveedor sin cambiar el dominio.

Se conserva el trabajo sin commit existente de Compose, Dockerfiles y proxy Vite,
revisándolo como base de esta tarea. Los cambios de TASK-08 y sus dependencias no se
reescriben ni se atribuyen a TASK-17. No hay remoto Git configurado; la implementación
local no acredita por sí sola una ejecución en verde en GitHub Actions.

## Archivos previstos

| Archivo | Cambio |
|---------|--------|
| `.github/workflows/ci.yml` | Flujo nuevo con tres jobs independientes |
| `compose.yaml` | Consolidar arranque local, aislamiento y salud |
| `backend/Dockerfile`, `backend/.dockerignore` | Instalación bloqueada y contexto limpio |
| `frontend/Dockerfile`, `frontend/.dockerignore` | npm reproducible y contexto limpio |
| `frontend/.node-version` | Nuevo selector `24` compartido con CI |
| `backend/.env.example`, `frontend/.env.example` | Documentar variables de ejecución |
| `.env.example` | Nuevo ejemplo de puertos publicados de Compose |
| `README.md`, `AGENTS.md`, `CLAUDE.md` | Arranque y guía operativa coherentes |
| `docs/tasks/TASK-17-ci-y-entorno.md` | Alinear referencias de guía con AGENTS.md |

No se añaden dependencias Python o npm. Alembic sube de 1.19.1 a 1.19.2: la primera
versión no detectó una columna añadida en la prueba temporal de `alembic check`, mientras
que 1.19.2 sí falló con la operación pendiente. Se mantienen los lockfiles de aplicación;
los cambios previos de `react-aria-components` quedan intactos. No se modifica
`frontend/vite.config.ts` más allá del proxy ya presente salvo un problema demostrado
en la verificación que requiera actualizar esta spec.

## Workflow de GitHub Actions

Nombre `CI`; eventos `push`, `pull_request` y `workflow_dispatch`, sin filtros de rutas
ni ramas. Runner `ubuntu-24.04`. Permisos globales `contents: read`, sin secretos.
Concurrencia por workflow y número de PR o ref; cancelar la ejecución anterior de ese
grupo al recibir cambios nuevos. Cada job tiene pasos con nombres descriptivos y
propaga el código de salida: no usar `continue-on-error` para comprobaciones.

Acciones: `actions/checkout`, `astral-sh/setup-uv` y `actions/setup-node`. Fijar sus
referencias a SHA de una release estable oficial, con versión en comentario, y verificar
esos SHA al implementar. No usar ramas móviles ni inventar SHA en esta spec.

Python se instala con `uv python install` desde `backend/`, respetando el selector
3.14 de `.python-version`; Node se configura desde `frontend/.node-version` (`24`).
uv se fija en `0.12.10`, versión documentada por Astral al consultar la guía. Comprobar
su disponibilidad y compatibilidad con el lockfile antes de construir las imágenes.
No se actualiza el uv global del usuario, actualmente 0.7.15.

Política de versiones: dependencias resueltas por lockfiles; uv exacto y acciones por
SHA. Python 3.14, Node 24 y PostgreSQL 18 admiten actualizaciones de parche. Las imágenes
usan las familias actuales `bookworm-slim` y `18-alpine`; no se promete identidad binaria
entre fechas. Registrar las versiones efectivas en la validación. Un cambio de major o
de lockfile requiere revisión explícita.

### Job `backend` — calidad y migraciones, timeout 15 minutos

Servicio PostgreSQL `postgres:18-alpine`, puerto 5432 en el runner, credenciales locales
`kanbai`/`kanbai` y `POSTGRES_DB=kanbai_test`. Healthcheck con `pg_isready -U kanbai -d
kanbai_test`, intervalo 5 s, timeout 3 s, 20 reintentos. Sin volumen persistente.

Entorno del job: `KANBAI_ENVIRONMENT=test`, `UV_LOCKED=true` y ambas variables
`KANBAI_DATABASE_URL` y `KANBAI_TEST_DATABASE_URL` apuntando explícitamente a
`postgresql+psycopg://kanbai:kanbai@localhost:5432/kanbai_test`. No copiar `.env`.

Pasos, en este orden, con comandos desde `backend/`:

1. Checkout e instalación de uv y Python. Imprimir versiones.
2. `uv sync --locked --dev`.
3. `uv run alembic upgrade head` sobre la base recién creada.
4. `uv run alembic check`.
5. `uv run poe check` (incluye la prueba de sincronización de OpenAPI).
6. `uv run poe openapi` y, desde la raíz, `git diff --exit-code -- backend/openapi.json`.

Cachear descargas de uv mediante `enable-cache: true` y
`cache-dependency-glob` con `backend/uv.lock` y `backend/pyproject.toml`. No cachear
PostgreSQL ni `.venv`. Una caché vacía debe producir el mismo resultado funcional.

### Job `frontend` — calidad, tipos y build, timeout 15 minutos

Checkout; setup-node con `node-version-file: frontend/.node-version`, `cache: npm`
y `cache-dependency-path: frontend/package-lock.json`. Cachear descargas npm, no
`node_modules`. Desde `frontend/`, imprimir Node/npm y ejecutar:

1. `npm ci`.
2. `npm install --package-lock-only --ignore-scripts` y, desde la raíz,
   `git diff --exit-code -- frontend/package-lock.json`. Así npm 11 no puede
   normalizar silenciosamente un lockfile desalineado.
3. `npm run gen:api` y, desde la raíz,
   `git diff --exit-code -- frontend/src/api/schema.d.ts`.
4. `npm run check`.
5. `npm run build`.

Consume el OpenAPI versionado del checkout; no necesita backend vivo ni transferir
artefactos entre jobs. La combinación de ambos jobs detecta divergencias en cada
eslabón del contrato.

### Job `compose` — arranque real, timeout 20 minutos

Desde la raíz, validar `docker compose config --quiet` y ejecutar
`docker compose up -d --build --wait --wait-timeout 180` con proyecto
`kanbai-ci`. La construcción no requiere herramientas Python/Node en el host.
Comprobar con peticiones HTTP que devuelvan éxito:

- `http://localhost:8000/health` y `/api/v1/health/ready`.
- `http://localhost:5173/` y `/api/v1/health/ready` por el proxy de Vite.

Comprobar además mediante `psql` dentro de `db` que existen `kanbai` y `kanbai_test`.
Ante fallo, recoger `docker compose ps -a` y logs. En un paso `always()`, desmontar
exclusivamente el proyecto de CI y sus volúmenes desechables. No publicar imágenes
ni artefactos. Inicialmente no hay caché Docker adicional: uv/npm ya tienen cachés
en los jobs de calidad y el smoke test verifica una construcción limpia.

## Comprobación de migraciones

Usar el entorno Alembic actual, que registra los modelos y habilita comparación de
tipos y defaults. `alembic check` utiliza la comparación de autogeneración y falla
si produciría operaciones; satisface el requisito de revisión autogenerada vacía sin
escribir archivos temporales de migración. Así lo documenta
[Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html#running-alembic-check-to-test-for-new-upgrade-operations).

No generar una migración de dominio para esta tarea. Un fallo real de sincronización
se diagnostica y documenta antes de corregirlo; no desactivar comparadores ni suprimir
diferencias para pasar CI. La detección conserva las limitaciones de Alembic para
renombrados y ciertos constraints; no sustituye la revisión humana de migraciones.

## Compose y Docker de desarrollo

Conservar los tres servicios y sus redes implícitas. Eliminar `container_name` fijo
para permitir aislamiento por proyecto. Mantener `kanbai-pgdata` como volumen lógico
de Compose, montado en `/var/lib/postgresql`, y el init SQL existente de solo lectura.
Los nombres de servicio `db`, `backend`, `frontend` permanecen estables.

Publicar en loopback con puertos sustituibles: `KANBAI_DB_PORT` por defecto 5432,
`KANBAI_BACKEND_PORT` 8000 y `KANBAI_FRONTEND_PORT` 5173. Los puertos internos no cambian.
La URL CORS de Compose usa el puerto frontend seleccionado. Estas tres variables se
documentan en `.env.example` raíz; no son settings del backend. No es obligatorio
copiar ese archivo para arrancar con los valores por defecto.

Backend espera a `db` sano; ejecuta `uv run --no-sync alembic upgrade head` y, solo si
funciona, arranca uvicorn con `exec`, `--factory`, host `0.0.0.0` y puerto 8000.
Healthcheck sobre `/api/v1/health/ready`, con el Python de la imagen y urllib,
timeout de petición 2 s; intervalo 5 s, timeout 3 s, 20 reintentos.

Backend Dockerfile: base `python:3.14-slim-bookworm`, copiar el binario uv desde la
imagen oficial `ghcr.io/astral-sh/uv:0.12.10`, copiar manifiestos, README, Alembic y
`src/`, e instalar con `uv sync --locked --dev`. Comando por defecto uvicorn mediante
`uv run --no-sync`. Mantener exclusión de tests porque la imagen sirve al desarrollo,
y excluir `.env`, `.env.*`, cachés y `.venv` del contexto; permitir `.env.example`.

Frontend Dockerfile: conservar `node:24-bookworm-slim`, `npm ci` antes de copiar el
código y ejecución Vite en `0.0.0.0:5173`. Excluir `node_modules`, `dist`, `.env` y
`.env.*`, permitiendo `.env.example`. Frontend espera a backend sano y recibe
`VITE_PROXY_TARGET=http://backend:8000`. Añadir healthcheck HTTP de `/` con Node y
fetch (timeout 2 s), intervalo 5 s, timeout 3 s y 20 reintentos.

El arranque completo no monta código del host: tras cambios se reconstruye con
`docker compose up -d --build --wait`. Para recarga del código se documenta el modo
con Python/Node en el host. No incluir configuración de producción.

## Variables y README

`backend/.env.example`: mantener settings existentes. Añadir documentación comentada
de `KANBAI_TEST_DATABASE_URL` y ejemplo de exportación en shell. No añadir una
asignación activa: `Settings(extra="forbid")` rechazaría esa clave en `.env` y las
fixtures solo leen la variable del proceso. No cambiar Settings para sortearlo.

`frontend/.env.example`: mantener `VITE_API_BASE_URL`. Documentar con comentario que
`VITE_PROXY_TARGET` se pasa al proceso, por ejemplo
`VITE_PROXY_TARGET=http://localhost:8000 npm run dev`; el `process.env` actual en
vite.config no carga por sí mismo ese valor desde `.env.local`.

README incluirá dos recorridos completos:

1. Docker Engine/Desktop y Compose v2 con soporte `--wait`; desde la raíz,
   `docker compose up -d --build --wait`, URLs, logs y `docker compose down` que
   conserva datos. No necesita `.env` ni Python/Node locales.
2. Desarrollo en host: `docker compose up -d db --wait`; desde backend copiar
   `.env.example` a `.env` si no existe, `uv sync --locked --dev`,
   `uv run poe migrate`, `uv run poe dev`; en otra terminal, desde frontend,
   `npm ci` y `npm run dev`. Documentar Python 3.14, Node 24 y uv seleccionado.

Añadir comandos de calidad, migraciones y generación del contrato con sus directorios,
explicación de jobs y cachés, puertos ocupados, diferencia localhost/db, diagnósticos
de salud y reconstrucción de imágenes. Para volúmenes antiguos sin `kanbai_test`,
comprobar su ausencia y crear solo esa base mediante `createdb` en el servicio `db`.
El borrado de volumen queda como opción destructiva explícita, nunca recuperación
por defecto. Actualizar las instrucciones equivalentes en AGENTS.md y CLAUDE.md y
alinear la cabecera obsoleta de este último con el estado real del tablero.

## Backend, frontend y contrato API

No hay nuevos modelos, columnas, índices, migraciones, schemas Pydantic, repositorios,
servicios ni routers. No hay nuevos endpoints, requests, responses, paginación ni
reglas de permisos. Se consumen los endpoints de salud actuales.

No hay nuevos tipos de API, hooks, claves de Query, componentes HeroUI o rutas de UI.
Se conserva TypeScript `~5.9.3` y el cliente generado. Carga, vacío y error de las
pantallas conservan su comportamiento. Esta tarea verifica el contrato sin alterarlo.

## Casos límite y errores

- Lockfile desalineado: instalación falla antes de los checks, sin regeneración automática.
- Base inaccesible o migración inválida: falla el paso correspondiente; Compose no
  declara backend sano ni arranca frontend antes de tiempo.
- Test roto o tipos desactualizados: job rojo con salida original y paso identificable.
- Caché ausente: instalación completa; nunca se omiten checks por acertar en caché.
- PR de fork: funciona sin secretos ni permisos de escritura.
- Puertos ocupados: usar variables de puerto y proyecto distintos; ajustar URL de
  backend local y proxy al usar herramientas en el host.
- Volumen existente: no se ejecuta de nuevo init.sql; recuperación preservando datos.
- Remoto ausente: registrar validación local y dejar pendiente la evidencia remota.
  No declarar TASK-17 En revisión si falta ese criterio; si bloquea el cierre de la
  implementación, registrar Bloqueada con el motivo y la acción necesaria.

## Plan de tests y aceptación

No añadir tests de API/UI que repitan suites existentes: no cambia su comportamiento.
Las nuevas verificaciones de infraestructura viven en el workflow. Durante la
implementación, guardar salida real de los siguientes escenarios:

| Escenario | Evidencia exigida |
|-----------|------------------|
| Calidad actual | `uv run poe check`, `npm run check` y `npm run build` en verde |
| Contrato | Regeneración sin diferencias en ambos archivos generados |
| Migraciones desde cero | Upgrade y check sobre PostgreSQL 18 vacío en verde |
| Diferencia de modelo | En copia temporal, añadir columna nullable al modelo sin migración; `alembic check` falla y menciona la diferencia |
| Fallo de test | En copia temporal, test con fallo intencional hace fallar `poe check`; retirada la alteración, vuelve a verde |
| Lockfiles | En copia temporal, desalinear manifiesto y comprobar que el recálculo deja diff |
| Arranque limpio | Copia del resultado incluyendo archivos nuevos, sin entornos locales; Compose completo y cuatro peticiones HTTP correctas |
| Modo host | Seguir README con solo db en Compose y herramientas locales |
| Persistencia | Reiniciar stack conservando volumen; datos de prueba creados para esta validación siguen presentes |
| Volumen antiguo | En proyecto aislado sin base de tests, aplicar recuperación y comprobar ambas bases |
| CI remota | Enlace a ejecución con tres jobs verdes; registrar funcionamiento con caché fría y caliente |

Las copias de verificación deben incluir los cambios sin commit relevantes, no solo
HEAD. Usar proyectos y puertos exclusivos; eliminar únicamente recursos creados para
esas pruebas. No ejecutar escenarios negativos sobre el checkout o volumen del usuario.
No hacer commits, pushes ni configurar remotos sin petición del usuario.

## Desviaciones respecto al plan

Se concreta GitHub Actions y se añade un job de humo de Compose para verificar el
arranque en cada cambio. Se elige `alembic check` como comprobación de autogeneración
vacía. Las variables de tests/proxy se documentan como entorno del proceso por sus
lectores actuales. Se precisa la reproducibilidad a lockfiles y familias de runtime,
sin prometer imágenes idénticas byte a byte.

## Referencias técnicas

- [Integración oficial de uv con GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/): instalación y versión de uv.
- [Caché de setup-uv](https://github.com/astral-sh/setup-uv/blob/main/docs/caching.md): activación e invalidación por manifiestos.
- [setup-node](https://github.com/actions/setup-node): selector de Node y caché npm por lockfile.

## Estado de verificación y cierre

La implementación local dejó en verde las suites, el build, la comprobación de
migraciones, la sincronía del contrato y dos arranques aislados con PostgreSQL 18. El
workflow se publicó y la [ejecución 34340591517](https://github.com/JMAgundezG/kanbai/actions/runs/34340591517)
confirmó en remoto los tres jobs en verde.
