# Plan · TASK-09 · Agentes como actores: alta y API keys

**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-09](../tasks/TASK-09-agentes-y-api-keys.md)

## Objetivo

Añadir una segunda forma de ser actor — el **agente** — y una segunda forma de
identificarse — la **API key** — sin tocar el dominio ya construido (TASK-04 a
TASK-06). Con una key válida, un agente usa exactamente los mismos endpoints de
tableros, columnas y tarjetas que una persona, con las mismas restricciones de
membresía, y sus acciones quedan atribuidas a él.

## Enfoque

Confirmado leyendo el código de TASK-03 a TASK-06: el modelo de actor ya está
preparado para esto de forma explícita.

- `models/actor.py` usa *joined-table inheritance* con `kind` como discriminador
  string (no enum nativo) precisamente para que TASK-09 añada `agents` sin
  `ALTER TYPE`. Se añade `Agent(Actor)` exactamente como `Person(Actor)`: tabla
  propia, `polymorphic_identity="agent"`, sin tocar `actors` ni `people`.
- `api/deps.py::get_current_actor` documenta ya el punto de extensión: la rama
  `Authorization: Bearer` se añade **dentro** de la misma función, probando
  primero la cookie y si no hay, la cabecera. La firma no cambia.
- `board_members`, `cards.created_by_actor_id`, etc. apuntan a `actors.id`, nunca a
  `people.actor_id`: un agente ya puede ser miembro de un tablero y crear tarjetas
  sin ningún cambio en esas tablas ni en los servicios que las usan.
- `tests/test_boards.py` ya incluye `_AgentDouble`, un doble de test que registra
  `polymorphic_identity="agent"` para probar el camino sin adelantar el modelo real
  — confirma que el resto del dominio ya se ejercitó mentalmente contra un segundo
  tipo de actor.

Estrategia de la API key: **prefijo identificador en claro + secreto hasheado**
(patrón "key con prefijo buscable", el mismo que usan GitHub/Stripe). La key en
claro tiene forma `<prefijo>.<secreto>`; se guarda `prefijo` en claro (indexado,
único, para localizar la fila con una query directa) y `hash(secreto)` con
SHA-256 (mismo mecanismo que ya usa `sessions.token_hash` — no hace falta Argon2
aquí: el secreto ya tiene alta entropía por ser aleatorio, a diferencia de una
contraseña elegida por un humano, así que un hash rápido y determinista que
permite indexar es la elección correcta; verificar con `secrets.compare_digest`
evita timing attacks en la comparación final). Esto evita el `SELECT` de todas las
keys para comparar una a una que la tarea prohíbe explícitcamente.

Revocación: columna `revoked_at` nullable en `agent_api_keys` en vez de borrar la
fila — conserva el historial de qué key existió y cuándo se revocó, útil para
TASK-12 (registro de actividad) más adelante, y hace que "clave inexistente" y
"clave revocada" sean estados distintos y comprobables por separado en los tests,
tal como pide la tarea.

Un agente **no tiene rol propio de owner**: se da de alta con una `owner_person_id`
(la persona que lo creó) y solo puede llegar a ser miembro de tableros de los que
esa persona ya sea miembro — así es como se demuestra "un agente nunca tiene más
permisos que la persona que lo dio de alta" sin ramificar el dominio: la regla vive
en `services/agents.py` al añadir el agente como miembro, no en `board_members` ni
en los routers de tableros/columnas/tarjetas, que no cambian.

## Alcance

- Backend (`backend/src/kanbai/`):
  - `models/agent.py` (nuevo): `Agent(Actor)` + `AgentApiKey`.
  - `models/__init__.py`: reexporta `Agent`, `AgentApiKey`.
  - Migración nueva (`alembic revision --autogenerate`): tablas `agents` y
    `agent_api_keys`.
  - `core/security.py`: helpers para generar y verificar la API key (prefijo +
    secreto + hash), reutilizando `hash_session_token`-style SHA-256.
  - `schemas/agent.py` (nuevo): `AgentCreate`, `AgentRead`, `ApiKeyCreated`
    (incluye la key en claro, solo en la respuesta de creación),
    `ApiKeyRead` (sin secreto).
  - `repositories/agents.py` (nuevo): consultas sobre `agents` y
    `agent_api_keys`, incluida la búsqueda por prefijo.
  - `services/agents.py` (nuevo): alta de agente (solo puede darlo de alta una
    persona autenticada, y el agente queda ligado a ella como
    `owner_person_id`), emisión de key, revocación, listado; nada de esto
    ramifica sobre `actor.kind` en ningún otro servicio.
  - `api/deps.py::get_current_actor`: añade la rama `Authorization: Bearer` sin
    cambiar la firma de `CurrentActor`.
  - `api/routers/agents.py` (nuevo): `/api/v1/agents` — alta, listado, detalle,
    emisión/revocación de key. Todo restringido a "mis agentes" (los que
    pertenecen a la persona autenticada); una API key nunca gestiona agentes.
  - `api/router.py`: monta el nuevo router.
  - `core/exceptions.py`: reutiliza las excepciones existentes, no se añaden.
  - `.env.example`: sin variables nuevas (no hay configuración propia).
  - Tests: `tests/test_agents.py` (alta, emisión, revocación, alcance de
    permisos, key inexistente/revocada) + ampliar `test_boards.py`/`test_cards.py`
    (o un nuevo `test_agents_e2e.py`) para demostrar que un agente autenticado con
    su key opera sobre tableros y tarjetas igual que una persona y con las mismas
    restricciones de membresía.
- Frontend: **no toca** en esta tarea (TASK-16 consume `/api/v1/agents`). Se
  exporta el contrato con `uv run poe openapi` para que `backend/openapi.json`
  quede al día; no se regenera `schema.d.ts` porque el frontend no lo consume aún
  (mismo criterio que aplicó TASK-03 para `/auth`).
- Contrato: sí cambia el OpenAPI (nuevo router `/agents`); no cambia ningún
  endpoint existente de TASK-04/05/06.

## Criterios de aceptación

- [x] Con una key válida, un agente llama a los endpoints de tableros y tarjetas y
      las acciones quedan atribuidas a él como actor.
- [x] Una key revocada o inexistente devuelve `401`.
- [x] La key en claro se devuelve solo en la respuesta de creación y no aparece en
      ningún log, traza ni otra respuesta.
- [x] Un agente solo ve los tableros de los que es miembro; el resto, `404`.
- [x] Un agente no puede acceder a nada a lo que su persona propietaria no llegue.
- [x] Ningún servicio ni router ramifica por el tipo de actor para funcionar (con
      la única excepción deliberada y documentada de `services/agents.py`, que
      define quién puede administrar agentes — ver spec).
- [x] `uv run poe check` en verde.

## Plan de verificación

- Backend: `uv run poe check` desde `backend/` (ruff + mypy + pytest).
- Migración: `--autogenerate`, revisión manual del archivo, `alembic upgrade
  head`, y un `--autogenerate` posterior vacío (revisión de comprobación
  descartada).
- `uv run poe openapi` para dejar `backend/openapi.json` al día.
- Prueba explícita de la invariante § 0: un agente autenticado por key ejerce
  contra `boards`, `columns` y `cards` de TASK-04/05/06 sin que esos módulos
  cambien una sola línea de lógica de autorización.

## Riesgos / decisiones abiertas

- **Esquema exacto de la API key** (formato del prefijo, longitud del secreto,
  algoritmo de hash): se fija en la spec, siguiendo el patrón ya usado por
  `sessions.token_hash` (SHA-256) para no introducir una dependencia nueva.
- **Quién puede dar de alta un agente y gestionar sus keys**: solo la persona
  propietaria (no cualquier miembro del tablero, no otro agente). Se detalla en
  la spec junto con los códigos de error exactos.
- **Relación agente↔tablero**: un agente se añade a un tablero con el mismo
  endpoint `POST /boards/{id}/members` que ya existe (TASK-04, "persona o agente
  por igual" ya está en su summary) — no se crea un endpoint nuevo de membresía;
  la spec confirma esto y añade la restricción de que solo se puede añadir un
  agente cuyo `owner_person_id` sea ya miembro (u owner) de ese tablero.
