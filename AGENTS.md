# AGENTS.md — kanbai

Instrucciones compartidas para los agentes que trabajan en este repositorio.

## Forma de trabajar

- Trabaja directamente sobre la petición del usuario: inspecciona el código,
  implementa el cambio y comprueba el resultado.
- No uses el antiguo ciclo documental de tareas. No crees ni mantengas planes,
  especificaciones, estados o documentos de cierre como requisito para trabajar.
  Los archivos históricos de `docs/` son contexto opcional, no instrucciones de proceso.
- No invoques skills, plugins ni comandos del antiguo flujo de trabajo. No hacen
  falta herramientas adicionales ni revisiones delegadas para empezar o terminar.
- Resuelve las decisiones técnicas habituales por tu cuenta. Pregunta solo cuando
  falte información esencial o haya una decisión que corresponda al usuario.
- Mantén los cambios centrados en lo pedido y respeta el trabajo existente.
  No hagas commits ni publiques cambios salvo que el usuario lo pida.
- Explica brevemente qué cambió, qué comprobaste y qué queda pendiente. No declares
  una comprobación como superada si no la ejecutaste.

## Proyecto y estructura

kanbai es un tablero kanban donde personas y agentes colaboran como actores.

- `backend/`: Python 3.14, uv, FastAPI, Pydantic, SQLAlchemy async y Alembic.
- `frontend/`: React 19, TypeScript, Vite, HeroUI v3, Tailwind CSS v4 y TanStack Query.
  Se gestiona con pnpm; la versión va fijada en `packageManager` y se instala con Corepack.
- `compose.yaml`: PostgreSQL 18 y servicios de desarrollo.
- Las versiones y los comandos vigentes están en `backend/pyproject.toml`,
  `frontend/package.json` y sus lockfiles. Compruébalos antes de cambiar dependencias.

## Dominio y seguridad

- Personas y agentes comparten las reglas del dominio; la diferencia de
  autenticación no debe convertirse en permisos especiales para los agentes.
- Un agente nunca tiene más permisos que la persona que lo dio de alta.
- Las escrituras se atribuyen a un actor y generan eventos de trazabilidad.
- Las reclamaciones de tarjetas tienen vencimiento y evitan trabajo simultáneo.
  Una persona puede liberar la reclamación de un agente atascado.
- Comprueba la autorización en cada endpoint y filtra el acceso en la consulta.
  Un recurso ajeno devuelve 404 para no revelar su existencia.
- No guardes secretos en el repositorio ni los expongas en logs o errores.
  Conserva los datos y volúmenes existentes al resolver problemas del entorno.

## Backend

- Respeta las capas: `api/routers → services → repositories → models`.
  Las consultas SQL pertenecen a los repositorios y las reglas a los servicios.
- Mantén el flujo async y evita operaciones bloqueantes en los endpoints.
- Usa schemas Pydantic para entradas y salidas, con respuesta y estado HTTP
  explícitos. Los modelos SQLAlchemy no salen de la API.
- Centraliza configuración en `core/config.py` y dependencias en `api/deps.py`.
  La aplicación se crea con `create_app`; engine y sessionmaker viven en `app.state`.
- Traduce las excepciones de dominio mediante los manejadores de la aplicación.
  Los errores visibles van en español y no revelan detalles internos.
- Pagina los listados y conserva el contrato `{items, total, page, size}`.
- Mantén el tipado estricto y usa la sintaxis nativa de Python 3.14.
- Gestiona el entorno y las dependencias con uv, conservando `uv.lock` actualizado.
- Los cambios de esquema requieren una migración Alembic revisada y comprobada
  contra PostgreSQL. Ejecuta `uv run alembic check` tras aplicarla.

## Frontend

- Organiza por feature y coloca lo compartido en `components/` o `lib/`.
  Evita imports entre features y separa la lógica en hooks.
- Usa TanStack Query para el estado del servidor y actualiza o invalida las queries
  afectadas por cada mutación.
- Consume los tipos generados de `src/api/schema.d.ts`; no los edites a mano ni
  dupliques respuestas de la API en interfaces propias.
- Usa HeroUI para los componentes interactivos y conserva la accesibilidad.
  Contempla carga, vacío y error en cada vista.
- Bootstrap aporta únicamente la rejilla. No importes sus resets, utilidades ni JS.
  Conserva el orden CSS `theme, base, bootstrap, components, utilities` y las
  importaciones de Tailwind antes de HeroUI. Para contenedores de página usa
  utilidades como `mx-auto w-full max-w-6xl px-4`.
- Mantén TypeScript estricto y comprueba la compatibilidad de los peers antes de
  cambiar su versión. Justifica cualquier supresión de errores de tipos.

## Comandos y comprobaciones

Desde la raíz:

```sh
docker compose up -d db --wait
docker compose up -d --build --wait
```

El primer comando levanta solo la base de datos; el segundo, la aplicación completa.

Desde `backend/`:

```sh
uv sync
uv run poe dev
uv run poe check
uv run poe migrate
uv run poe openapi
```

Desde `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm run dev
pnpm run check
pnpm run build
pnpm run gen:api
```

- Para cambios de código, ejecuta las comprobaciones de las partes afectadas.
  `poe check` y `pnpm run check` incluyen lint, tipado y tests.
- Si cambia la API, regenera primero `backend/openapi.json` y después los tipos del
  frontend con los comandos anteriores; comprueba ambos proyectos.
- Añade o ajusta tests de comportamiento cuando cambie funcionalidad o se corrija
  un fallo. Cubre los casos de éxito, validación y permisos que correspondan.
- Los tests del backend usan PostgreSQL real y datos aislados en `kanbai_test`.
  Si falta esa base, créala con `docker compose exec db createdb -U kanbai kanbai_test`.
- Exporta `KANBAI_TEST_DATABASE_URL` en la shell de tests, no en el `.env` del backend.
  `VITE_PROXY_TARGET` también se proporciona al proceso que inicia Vite.
- Para cambios exclusivamente de texto basta revisar el diff y su formato.

## Convenciones

- Comunicación, UI y mensajes de error en español. Identificadores, comentarios,
  nombres de archivo y mensajes de commit en inglés.
- Sigue los patrones existentes y prefiere las dependencias ya disponibles.
- Comenta el motivo de las decisiones cuando aporte valor.
- Actualiza instrucciones de uso o `.env.example` cuando el cambio lo necesite,
  sin generar documentación de seguimiento.
- Mantén las instrucciones del proyecto únicamente aquí. `CLAUDE.md` importa este
  archivo para evitar duplicaciones.
