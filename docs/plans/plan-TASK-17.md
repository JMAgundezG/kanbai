# Plan · TASK-17 · Integración continua y entorno reproducible

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-09-08 · **Cerrado:** 2026-09-09 · **Responsable:** Codex
**Tarea:** [TASK-17](../tasks/TASK-17-ci-y-entorno.md)

## Objetivo

Ejecutar automáticamente la puerta de calidad de backend y frontend en cada cambio,
detectar migraciones pendientes y permitir arrancar el proyecto desde un clon limpio
con instrucciones reproducibles y PostgreSQL real.

## Precondiciones y estado observado

- TASK-01 y TASK-02 están `Completada` en el tablero. TASK-17 estaba `Pendiente`.
- No existe `.github/` ni hay remoto Git configurado. Se propone GitHub Actions;
  confirmar el proveedor en la especificación. La ejecución remota requerirá un
  repositorio conectado, pero esto no impide planificar ni validar localmente.
- `compose.yaml` ya tiene cambios sin commit que añaden backend y frontend, espera
  de salud, migraciones al arrancar y proxy interno. Hay Dockerfiles y archivos
  `.dockerignore` nuevos en ambos directorios; `frontend/vite.config.ts` incorpora
  `VITE_PROXY_TARGET`. Son trabajo previo, todavía no validado en esta fase.
- También existen cambios de TASK-08, documentación y dependencias frontend.
  Preservarlos y delimitar su procedencia al implementar; no atribuirlos a TASK-17.
- El README raíz carece de instrucciones de arranque. `VITE_PROXY_TARGET` no aparece
  en `frontend/.env.example` y `KANBAI_TEST_DATABASE_URL`, usada por las fixtures,
  no está en `backend/.env.example`.
- Las fixtures ya aplican migraciones y aíslan cada test en una transacción sobre
  `kanbai_test`. Existe una prueba de sincronización de OpenAPI, pero no un flujo
  de CI ni una comprobación automática de diferencias entre modelos y migraciones.

## Enfoque

1. Consolidar el entorno local existente: conservar `docker compose up -d db`
   para quien ejecuta Python y Node en el host, y completar el arranque de todo el
   stack mediante Compose como opción de un comando. Las imágenes serán únicamente
   de desarrollo, con instalación desde los lockfiles y migración previa al servicio.
2. Crear un flujo de CI para pushes y pull requests, con comprobaciones separadas
   de backend y frontend. Usar Python 3.14, Node 24 como base del Dockerfile actual
   y PostgreSQL 18; concretar versiones de herramientas y acciones en la spec.
   Instalar con `uv sync --locked` y `npm ci`, cacheando descargas según los lockfiles.
3. Ejecutar los comandos oficiales de calidad y comprobar las migraciones sobre una
   base desechable vacía: aplicar `alembic upgrade head` y exigir que la comparación
   posterior con los modelos no produzca operaciones. La spec decidirá el mecanismo
   de comprobación, conservando el requisito de autogeneración vacía y evitando
   dejar revisiones artificiales en el repositorio.
4. Verificar también que la generación de tipos frontend no deja diferencias respecto
   al contrato versionado, y que el bundle de producción se construye. Esto valida
   el código existente sin ampliar el alcance a despliegue o publicación.
5. Documentar requisitos, arranque, migraciones, comandos de calidad, URLs, variables,
   parada y diagnóstico de fallos. Explicar los volúmenes existentes sin convertir
   su borrado en un paso habitual ni eliminar datos locales durante la validación.

Se propone CI con herramientas en el runner y PostgreSQL como servicio para reutilizar
los comandos del repositorio. Los Dockerfiles actuales sirven al arranque local: el
backend excluye `tests/`, por lo que no es una imagen preparada para la suite de CI.

## Alcance

- Infraestructura: flujo nuevo de CI, `compose.yaml`, Dockerfiles y `.dockerignore`
  existentes; inicialización de PostgreSQL si la validación identifica ajustes.
- Backend: configuración de herramientas y comprobación de migraciones si hace falta;
  reutilizar tests y configuración Alembic. Sin cambios previstos en modelos, schemas,
  repositorios, servicios o routers, ni nuevas migraciones de dominio.
- Frontend: configuración reproducible de Node/npm y proxy Vite existente. Sin cambios
  de UI, features, hooks o rutas. Mantener TypeScript en `~5.9.3`.
- Contrato: no cambia OpenAPI. Verificar sincronización de `backend/openapi.json` y
  `frontend/src/api/schema.d.ts`; no editar a mano los tipos generados.
- Documentación: README, ejemplos de entorno y guía operativa donde corresponda;
  documentar el resultado en `docs/features/` durante el cierre.
- Fuera: despliegue, imágenes de producción, entornos remotos de aplicación,
  publicación de artefactos, versionado y nuevas funcionalidades de producto.

## Criterios de aceptación

- [x] `docker compose up -d db` y las instrucciones del `README.md` dejan el proyecto
      funcionando desde un clon limpio.
- [x] La integración continua pasa en verde sobre el estado actual del repositorio.
- [x] Falla, y se ve por qué, si un test falla o si queda una migración sin generar.
- [x] Los tests corren contra **PostgreSQL real**, no SQLite (`AGENTS.md` § 2).

## Plan de verificación

- Backend: `uv run poe check` desde `backend/` (ruff, mypy y pytest).
- Frontend: `npm run check` y `npm run build` desde `frontend/`.
- Contrato: regenerar OpenAPI y los tipos con los comandos oficiales y comprobar
  que no dejan diferencias inesperadas.
- Migraciones: aplicar desde cero y comprobar autogeneración vacía en una base
  desechable; introducir en una copia temporal una diferencia de modelo para demostrar
  que la puerta falla y explica la causa. No alterar la base de desarrollo.
- CI: probar instalaciones sin caché y con caché, y verificar un fallo de test
  controlado en una copia temporal. Registrar una ejecución remota cuando exista
  remoto y autorización para publicar los cambios; no sustituirla por un éxito local.
- Entorno: validar Compose y seguir el README desde una copia limpia del resultado,
  con volumen aislado y sin depender de `.env`, `.venv` o `node_modules` preexistentes.
  Comprobar `/health`, `/api/v1/health/ready`, acceso al frontend y proxy de API.
- Registrar comandos y salidas reales en la implementación. En esta fase se ha
  realizado inspección estática; no se han ejecutado suites ni construido imágenes.

## Riesgos / decisiones abiertas

- GitHub Actions adoptado en la especificación como decisión reversible; la ausencia
  de remoto impide acreditar hoy el criterio de CI remota en verde.
- Los cambios previos de Compose/Docker se solapan con esta tarea y requieren revisión
  y pruebas, no una sustitución automática. No se hacen commits en esta fase.
- Las etiquetas actuales de imágenes son móviles: fijar una política de versiones
  de runtime y herramientas en la spec, sin actualizar dependencias de aplicación
  de forma incidental.
- `container_name` y los puertos fijos de Compose pueden impedir pruebas simultáneas;
  prever aislamiento para la verificación del clon limpio.
- La inicialización de `kanbai_test` solo ocurre con volúmenes nuevos. Documentar una
  recuperación que preserve datos y distinguirla del reinicio destructivo opcional.
- TASK-17 y README citan `CLAUDE.md`, mientras esta ejecución usa `AGENTS.md`; ambos
  archivos existen, pero la cabecera de CLAUDE.md todavía describe solo TASK-01 y
  TASK-02. Alinear referencias al actualizar documentación. Se ha corregido la ruta
  de skills en AGENTS.md de `.Codex/skills/` a `.agents/skills/` tras comprobarla.

## Implementación y verificación

- `uv run poe check`: ruff y formato correctos, mypy sin incidencias y 111 pruebas
  aprobadas contra PostgreSQL real.
- `npm run check`: lint, TypeScript y 32 pruebas aprobadas; `npm run build` también
  termina correctamente.
- `uv run alembic check` contra `kanbai_test` no detecta operaciones de migración.
  Ese mismo comando es una puerta sin `continue-on-error` en CI, por lo que deja la
  diferencia de modelos sin migración visible en el job que falla.
- En una copia temporal, Alembic 1.19.1 no detectó una columna artificial; se actualizó
  a 1.19.2 y `alembic check` falló mostrando `add_column boards.review_marker`.
- La misma copia temporal confirmó un fallo de pytest intencional (1 fallida, 111
  aprobadas). Para npm, el recálculo del lockfile queda comprobado con un diff:
  cambiar TypeScript a 5.8 lo actualiza frente al lock versionado y el job falla.
- La regeneración de OpenAPI y de los tipos no deja diferencias. `docker compose
  config --quiet`, la sintaxis del workflow y `git diff --check` también pasan.
- En proyectos Compose aislados y puertos alternativos se construyó la pila completa,
  quedaron sanos los tres servicios, respondieron las cuatro rutas HTTP y existieron
  las bases `kanbai` y `kanbai_test`. También se validó el modo de solo PostgreSQL
  documentado en el README. Ambos entornos efímeros fueron desmontados con sus
  volúmenes al terminar.

## Cierre

La revisión independiente fue aprobada tras corregir los hallazgos y se publicó el
workflow. La [ejecución 34340591517](https://github.com/JMAgundezG/kanbai/actions/runs/34340591517)
terminó con los jobs de backend, frontend y humo de Compose en verde.
