# Spec · TASK-09 · Agentes como actores: alta y API keys

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrada:** 2026-08-30
**Plan:** [plan-TASK-09](plan-TASK-09.md) · **Tarea:** [TASK-09](../tasks/TASK-09-agentes-y-api-keys.md)

## Hallazgo que condiciona esta spec

Verificando la invariante § 0 sobre TASK-04 (`services/boards.py`) antes de diseñar,
encontré un hueco real: `add_member` deja que **cualquier owner de un tablero** añada
**cualquier actor existente** (persona o agente) por su `actor_id`, sin comprobar
relación alguna entre el agente y su persona propietaria. Y `create_board` convierte
al actor creador en el único owner del tablero nuevo. Combinados: hoy, un agente
puede acabar siendo miembro (incluso owner) de un tablero al que su persona
propietaria no tiene acceso — viola literalmente "un agente nunca tiene más permisos
que la persona que lo dio de alta".

No lo arreglo con un `if actor.kind == "agent"` en `boards.py` (eso sí sería la
ramificación que la invariante prohíbe). Lo arreglo añadiendo **un método
polimórfico** a `Actor`, que `Agent` es la única subclase en sobrescribir:

```python
# models/actor.py
def permission_ceiling_actor_id(self) -> uuid.UUID | None:
    """El actor cuyo acceso este actor nunca debe superar, o None si no aplica
    (una persona no tiene techo: su acceso nace solo de su propia membresía).
    Sobrescrito por Agent — ver models/agent.py."""
    return None
```

```python
# models/agent.py
def permission_ceiling_actor_id(self) -> uuid.UUID:
    return self.owner_person_id
```

`services/boards.py` llama a `target_actor.permission_ceiling_actor_id()` — nunca
lee `kind`, ni hace `isinstance`. Es *dispatch* de tipos, la forma correcta de
evitar la ramificación, no un rodeo para colarla. Dos puntos de aplicación:

1. **`add_member`**: si el actor a añadir tiene techo, su techo debe ya ser miembro
   de ese tablero con un rol **igual o superior** al que se le va a conceder al
   actor techado. Si no, `409` — el agente no puede entrar (o entrar con más rol)
   donde su persona no llega.
2. **`create_board`**: si quien crea el tablero tiene techo, ese techo se añade
   también como miembro, con el mismo rol (`owner`) que el creador — así un agente
   nunca es dueño de algo que su persona no pueda ver ni administrar, sin negarle
   la posibilidad de crear tableros (que sí forma parte de "los mismos endpoints
   que una persona").

Esto **sí toca `services/boards.py`** (TASK-04, ya `Completada`). Lo hago de forma
explícita, documentado aquí y en el informe final — no a escondidas — tal como pide
la tarea. El resto de TASK-04/05/06 (columnas, tarjetas, listados, movimiento) no
cambia ni una línea: ya eran agnósticos de `kind`, confirmado leyendo el código.

**Limitación aceptada, fuera de alcance:** esto se aplica solo en el momento de
conceder (alta de miembro / creación de tablero). Si más tarde la persona
propietaria pierde su membresía (la quitan del tablero), el agente no se revoca en
cascada — eso exigiría releer `kind` en cada petición, justo lo que la invariante
evita. Se deja anotado para una tarea futura si se decide abordarlo (posiblemente
TASK-12, registro de actividad, o una limpieza periódica).

## Backend (`backend/src/kanbai/`)

### Dependencias nuevas

Ninguna. El esquema de API key reutiliza `secrets` y `hashlib` (stdlib), igual que
`core/security.py` ya hace para los tokens de sesión.

### Modelos (`models/`)

`models/actor.py` — añade el método polimórfico (sin tocar columnas ni la tabla):

```python
def permission_ceiling_actor_id(self) -> uuid.UUID | None:
    return None
```

`models/agent.py` (nuevo) — *joined-table inheritance*, igual que `Person`:

```python
class Agent(Actor):
    __tablename__ = "agents"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.actor_id", ondelete="CASCADE"), nullable=False, index=True
    )

    __mapper_args__ = {"polymorphic_identity": "agent"}

    def permission_ceiling_actor_id(self) -> uuid.UUID:
        return self.owner_person_id
```

`display_name` y `created_at` vienen heredados de `Actor`, igual que en `Person`.
`owner_person_id` con `ondelete="CASCADE"` (a diferencia de
`Card.created_by_actor_id`, que es `RESTRICT`): un agente sin persona propietaria no
tiene sentido — no hay atribución que preservar aquí, el agente entero deja de tener
dueño y debe desaparecer con ella.

`models/agent.py` también define la key:

```python
class AgentApiKey(Base):
    __tablename__ = "agent_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.actor_id", ondelete="CASCADE"), nullable=False, index=True
    )
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Esquema de la key — prefijo en claro + secreto hasheado:**

- La key completa que ve el agente: `kanbai_agent_<prefix>.<secret>` — `prefix`
  (`secrets.token_urlsafe(9)`, ~12 caracteres) y `secret`
  (`secrets.token_urlsafe(32)`, ~43 caracteres), ambos generados con el CSPRNG del
  sistema.
- Se guarda `prefix` **en claro** (columna única e indexada: localizar la fila es un
  `WHERE prefix = :prefix`, `O(1)` por el índice, nunca un `SELECT` de todas las
  keys) y `secret_hash = sha256(secret)` (igual que `sessions.token_hash` — el
  secreto ya nace con alta entropía aleatoria, no es una contraseña elegida por un
  humano, así que no hace falta Argon2 aquí; lo que hace falta es una comparación a
  tiempo constante, con `secrets.compare_digest`).
- `revoked_at` nullable: revocar no borra la fila (conserva qué key existió), deja
  "inexistente" (prefijo no encontrado) y "revocada" (`revoked_at IS NOT NULL`) como
  estados distintos y comprobables — la búsqueda por prefijo ya filtra
  `revoked_at IS NULL`, así que ambos casos devuelven el mismo `401` sin filtrar
  cuál de los dos fue (paralelo exacto al 401 genérico de login).
- Colisión de `prefix` entre dos keys: probabilidad despreciable (72 bits de
  entropía); si ocurriera, el `UniqueConstraint` la convierte en un error 500, igual
  que ya acepta el proyecto para la generación de tokens de sesión (no hay
  reintento especial en ningún sitio del código existente).

`models/__init__.py` reexporta `Agent`, `AgentApiKey`.

### Migración

`alembic revision --autogenerate -m "add agents and agent api keys"` debe generar:

- `CREATE TABLE agents (actor_id UUID PK FK→actors.id ON DELETE CASCADE, description TEXT NULL, owner_person_id UUID NOT NULL FK→people.actor_id ON DELETE CASCADE)` + índice `ix_agents_owner_person_id`.
- `CREATE TABLE agent_api_keys (id UUID PK, agent_id UUID NOT NULL FK→agents.actor_id ON DELETE CASCADE, prefix VARCHAR(16) NOT NULL, secret_hash VARCHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), revoked_at TIMESTAMPTZ NULL)` + índice único `uq_agent_api_keys_prefix` + índice `ix_agent_api_keys_agent_id`.

A revisar a mano: nombres de constraint según `db/base.py`, `ondelete` explícito en
ambos FKs, `TIMESTAMPTZ` no `TIMESTAMP`. `permission_ceiling_actor_id` no genera
ninguna migración (no es una columna). Tras aplicar, `alembic revision
--autogenerate -m "check"` debe salir vacía; se descarta esa revisión.

### Seguridad (`core/security.py`)

```python
_API_KEY_HEADER_PREFIX = "kanbai_agent_"
_API_KEY_PREFIX_BYTES = 9   # ~12 chars base64url
_API_KEY_SECRET_BYTES = 32  # ~43 chars base64url

def generate_api_key() -> tuple[str, str, str]:
    """Devuelve (key_en_claro, prefix, secret_hash). La key en claro solo existe
    aquí y en la respuesta de creación; lo único que se guarda es prefix y hash."""
    prefix = secrets.token_urlsafe(_API_KEY_PREFIX_BYTES)
    secret = secrets.token_urlsafe(_API_KEY_SECRET_BYTES)
    full_key = f"{_API_KEY_HEADER_PREFIX}{prefix}.{secret}"
    return full_key, prefix, hash_api_key_secret(secret)

def hash_api_key_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

def split_api_key(key: str) -> tuple[str, str] | None:
    """(prefix, secret) a partir de la key presentada; None si está malformada."""
    if not key.startswith(_API_KEY_HEADER_PREFIX):
        return None
    prefix, sep, secret = key.removeprefix(_API_KEY_HEADER_PREFIX).partition(".")
    if not sep or not prefix or not secret:
        return None
    return prefix, secret

def verify_api_key_secret(secret: str, secret_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key_secret(secret), secret_hash)
```

### Schemas (`schemas/agent.py`, nuevo)

```python
class AgentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: Literal["agent"]
    display_name: str
    description: str | None
    owner_person_id: uuid.UUID
    created_at: datetime

class ApiKeyRead(BaseModel):
    """Nunca lleva el secreto: `prefix` es lo único que se puede volver a leer
    después de la creación."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    prefix: str
    created_at: datetime
    revoked_at: datetime | None

class ApiKeyCreated(ApiKeyRead):
    """Solo la devuelve el endpoint de creación: `api_key` es la única vez que el
    valor en claro existe fuera del cliente."""
    api_key: str
```

### Repositorios (`repositories/agents.py`, nuevo)

- `create_agent(session, *, display_name, description, owner_person_id) -> Agent`
- `list_agents_for_owner(session, owner_person_id, *, limit, offset) -> tuple[list[Agent], int]`
- `get_agent_for_owner(session, agent_id, owner_person_id) -> Agent | None`
- `create_api_key(session, *, agent_id, prefix, secret_hash) -> AgentApiKey`
- `list_api_keys_for_agent(session, agent_id, *, limit, offset) -> tuple[list[AgentApiKey], int]`
- `get_api_key_for_agent(session, key_id, agent_id) -> AgentApiKey | None`
- `get_active_key_by_prefix(session, prefix) -> AgentApiKey | None` — filtra
  `revoked_at IS NULL` en la propia consulta; es la única query del camino de
  autenticación, y solo toca este índice único, nunca una tabla completa.
- `revoke_api_key(session, key) -> AgentApiKey` — pone `revoked_at = now()`.

Reutiliza `repositories/actors.py::get_actor_by_id` para resolver el `Actor`
polimórfico tras validar la key (no se duplica esa query en `agents.py`).

### Servicios (`services/agents.py`, nuevo)

Única excepción deliberada a "ningún servicio ramifica por `kind`" en todo el
proyecto — justificada porque **la función entera de este servicio es la frontera
de quién puede dar de alta o administrar un agente**, no una operación de dominio
compartida:

```python
def _require_person(actor: Actor) -> Person:
    if not isinstance(actor, Person):
        raise AuthorizationError("Solo una persona puede gestionar agentes.")
    return actor
```

`isinstance`, no `actor.kind == "person"`: usa el sistema de tipos en vez de
comparar el discriminador a mano.

- `create_agent(session, *, actor, display_name, description) -> Agent`
- `list_agents(session, *, actor, limit, offset) -> tuple[list[Agent], int]`
- `get_agent(session, *, actor, agent_id) -> Agent` — 404 si no existe o no es del
  actor.
- `create_api_key(session, *, actor, agent_id) -> tuple[AgentApiKey, str]` — la
  segunda posición es la key en claro, generada aquí y nunca almacenada.
- `list_api_keys(session, *, actor, agent_id, limit, offset) -> tuple[list[AgentApiKey], int]`
- `revoke_api_key(session, *, actor, agent_id, key_id) -> AgentApiKey`
- `resolve_actor_by_api_key(session, presented_key) -> Actor` — llamado desde
  `CurrentActor`, no desde un router. `split_api_key` → busca por prefijo (activa)
  → `verify_api_key_secret` con `compare_digest` → si falla cualquier paso,
  `AuthenticationError()` (mismo error y mensaje genérico en los tres casos:
  malformada, inexistente, revocada, secreto incorrecto — ninguno delata cuál fue).
  Si todo encaja, resuelve el `Actor` por `key.agent_id` vía
  `actors_repository.get_actor_by_id` y lo devuelve.

Commits los hace el servicio (mismo patrón que `services/auth.py` y
`services/boards.py`).

### `services/boards.py` — el fix de la invariante

```python
_ROLE_RANK = {MEMBER: 0, OWNER: 1}

async def create_board(session, *, actor, name) -> tuple[Board, str]:
    ...
    board = await boards_repository.create_board(session, name=name)
    await board_members_repository.add_member(session, board_id=board.id, actor_id=actor.id, role=OWNER)
    ceiling_id = actor.permission_ceiling_actor_id()
    if ceiling_id is not None:
        await board_members_repository.add_member(session, board_id=board.id, actor_id=ceiling_id, role=OWNER)
    await columns_service.seed_default_columns(session, board_id=board.id)
    await session.commit()
    return board, OWNER

async def add_member(session, *, actor, board_id, new_actor_id, role) -> BoardMember:
    ...  # autorización de "actor" (el owner que invita) sin cambios
    target_actor = await actors_repository.get_actor_by_id(session, new_actor_id)
    if target_actor is None:
        raise NotFoundError("El actor indicado no existe.")

    ceiling_id = target_actor.permission_ceiling_actor_id()
    if ceiling_id is not None:
        ceiling_membership = await board_members_repository.get_member_by_actor(session, board_id, ceiling_id)
        if ceiling_membership is None or _ROLE_RANK[ceiling_membership.role] < _ROLE_RANK[role]:
            raise ConflictError(
                "El agente no puede tener en este tablero más permisos que su persona propietaria."
            )
    ...  # resto sin cambios
```

Nada de esto lee `kind`; ambos puntos llaman a `permission_ceiling_actor_id()`, que
para una `Person` siempre es `None` — cero cambio de comportamiento observable para
el 100% de los tests y flujos existentes de persona.

### API (`api/deps.py`)

```python
async def get_current_actor(request: Request, session: SessionDep, settings: SettingsDep) -> Actor:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        return await auth_service.resolve_actor(session, token)

    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer" and credential:
            return await agents_service.resolve_actor_by_api_key(session, credential)

    raise AuthenticationError()
```

Firma **sin cambios**. Cookie primero (si hay cookie pero es inválida, no se
intenta la cabecera — mismo comportamiento que documentó TASK-03: "probando la
cookie, si no hay, probar la cabecera", presencia, no validez, decide la rama).

### Router (`api/routers/agents.py`, nuevo)

Todo bajo `/api/v1/agents`, todo exige `CurrentActor` sea una `Person` (403 si no).

```
POST   /api/v1/agents                          → 201 AgentRead
GET    /api/v1/agents                          → 200 Page[AgentRead]  (solo los propios)
GET    /api/v1/agents/{agent_id}                → 200 AgentRead | 404
POST   /api/v1/agents/{agent_id}/keys           → 201 ApiKeyCreated | 404
GET    /api/v1/agents/{agent_id}/keys           → 200 Page[ApiKeyRead] | 404
POST   /api/v1/agents/{agent_id}/keys/{key_id}/revoke → 200 ApiKeyRead | 404
```

`api/router.py` monta `agents.router` junto a los demás bajo `/api/v1`.

No hay endpoint de borrado de agente (fuera de alcance según la tarea: solo entra
alta, key y revocación de key).

## Frontend

No toca (TASK-16 lo consume). `uv run poe openapi` deja `backend/openapi.json` al
día; `schema.d.ts` no se regenera — mismo criterio que TASK-03 con `/auth`.

## Contrato API

| Método | Ruta | Request | Response |
|--------|------|---------|----------|
| POST | `/api/v1/agents` | `AgentCreate` | `201 AgentRead` / `401` / `403` |
| GET | `/api/v1/agents` | — | `200 Page[AgentRead]` / `401` / `403` |
| GET | `/api/v1/agents/{agent_id}` | — | `200 AgentRead` / `401` / `403` / `404` |
| POST | `/api/v1/agents/{agent_id}/keys` | — | `201 ApiKeyCreated` / `404` |
| GET | `/api/v1/agents/{agent_id}/keys` | — | `200 Page[ApiKeyRead]` / `404` |
| POST | `/api/v1/agents/{agent_id}/keys/{key_id}/revoke` | — | `200 ApiKeyRead` / `404` |

## Casos límite y errores

- Key con formato correcto pero prefijo inexistente / revocada / secreto
  incorrecto → mismo `401` genérico en los tres casos.
- Cabecera `Authorization` sin esquema `Bearer` (p. ej. `Basic ...`) → se ignora,
  cae al `401` genérico (no se interpreta como intento de key).
- Un agente autenticado con su key llama a `/api/v1/agents` → `403` (no es una
  persona); nunca `404`, porque no es "un agente ajeno", es una acción vetada a su
  tipo — la única ruta de todo el backend donde esto pasa.
- Una persona intenta gestionar un agente de otra persona → `404` (no delata que
  existe, igual que un tablero ajeno).
- Alta de agente por un agente → `403` (verificado con test, ver más abajo).
- `add_member` con un agente cuya persona propietaria no es miembro del tablero →
  `409`. Con la persona ya miembro pero solo `member`, y el agente se intenta
  añadir como `owner` → también `409` (el techo es por rol, no solo por presencia).
- `create_board` por un agente → el tablero se crea, el agente queda `owner`, y su
  persona propietaria se añade automáticamente como `owner` también (fila
  adicional en `board_members`), en la misma transacción.
- Revocar una key ya revocada → idempotente, `200` con `revoked_at` sin cambiar
  (no se sobrescribe la fecha original).

## Plan de tests

`backend/tests/test_agents.py` (nuevo):

- `test_crear_agente_devuelve_201_y_queda_ligado_al_creador`
- `test_crear_agente_sin_sesion_devuelve_401`
- `test_agente_no_puede_crear_agentes_devuelve_403` (agente autenticado por key)
- `test_persona_no_ve_agentes_de_otra_persona` (list vacío + detalle 404)
- `test_emitir_api_key_devuelve_el_valor_en_claro_una_sola_vez`: la respuesta de
  creación trae `api_key`; una llamada posterior a listar keys **no** trae ese
  campo en el JSON.
- `test_key_en_claro_no_se_guarda_en_base_de_datos`: lee la fila de
  `AgentApiKey` directamente por sesión y confirma que `secret_hash` no coincide
  con el valor en claro y que no hay columna que lo contenga.
- `test_key_revocada_devuelve_401`
- `test_key_inexistente_devuelve_401`
- `test_key_malformada_devuelve_401` (sin el prefijo `kanbai_agent_`, sin punto)
- `test_revocar_key_de_otro_agente_devuelve_404` (aislamiento entre personas)
- `test_agente_opera_tableros_columnas_y_tarjetas_igual_que_una_persona`: la
  persona crea un tablero, se emite una key para su agente, se añade al agente
  como miembro, y **con la key** (cabecera `Authorization: Bearer ...`, sin
  cookie) el agente lista tableros, crea una tarjeta y la mueve; se comprueba
  `created_by_actor_id == agent.id` y que el tablero listado es el correcto.
- `test_agente_no_miembro_de_un_tablero_recibe_404` (mismo trato que una persona
  no miembro).
- `test_anadir_agente_cuya_persona_no_es_miembro_devuelve_409` — el test central
  de "un agente nunca tiene más permisos que su persona propietaria": tablero de
  un tercero, agente cuya persona propietaria no es miembro → `409`; se añade la
  persona propietaria como miembro → la misma petición de añadir al agente
  ahora sí funciona (`201`).
- `test_anadir_agente_como_owner_cuando_su_persona_es_solo_member_devuelve_409`
- `test_crear_tablero_como_agente_añade_tambien_a_su_persona_propietaria`

Ajustes en tests existentes:

- `tests/test_boards.py`: elimina `_AgentDouble` (con el modelo `Agent` real,
  registrar una segunda clase con `polymorphic_identity="agent"` rompe la
  configuración del mapper de SQLAlchemy — colisión de identidad polimórfica) y
  usa `services.agents.create_agent` + `services.agents.create_api_key` para el
  agente de prueba en `test_anadir_miembro_agente_funciona_igual_que_persona`,
  ajustado para que la persona propietaria del agente ya sea miembro del tablero
  (si no, ahora falla con `409` por el fix de esta tarea — correcto, se documenta
  en el propio test).

## Desviaciones respecto al plan

- El plan ya anticipaba el esquema de key (prefijo + secreto hasheado) y el punto
  de extensión en `CurrentActor`; esta spec lo concreta.
- **Cambio no anticipado en el plan, señalado ahí como "decisión abierta" y
  resuelto aquí**: `services/boards.py` (`add_member`, `create_board`) se modifica
  para cerrar el hueco de la invariante "un agente nunca tiene más permisos que su
  persona propietaria", vía el método polimórfico `permission_ceiling_actor_id`
  en `Actor`/`Agent` — no vía ramificación por `kind`. Ver la sección "Hallazgo"
  al principio de este documento.
- **Dos hallazgos más, de la code review posterior a la implementación inicial,
  corregidos antes de cerrar la tarea:**
  - **Condición de carrera en el techo de permisos.** La primera versión de
    `add_member` leía la membresía de la persona propietaria del agente y
    después insertaba, sin nada entre medio: un `remove_member` concurrente
    sobre esa misma fila podía colarse en el hueco. Arreglado con
    `boards_repository.lock_board_for_update` — el mismo primitivo que ya usa
    `services/columns.py` para el mismo tipo de invariante — al principio de
    `add_member` **y** de `remove_member` (las dos operaciones que escriben
    `board_members` tienen que tomar el mismo lock para que sirva de algo).
    Demostrado con una prueba de concurrencia real
    (`tests/test_boards.py::test_anadir_agente_lee_el_techo_de_permisos_tras_esperar_el_lock`,
    que sí falla si se quita el `lock_board_for_update`, comprobado a mano).
  - **`MissingGreenlet` real al leer `Agent.owner_person_id`.** Al escribir esa
    misma prueba de concurrencia con una sesión realmente nueva (no la
    compartida y ya "caliente" de `db_session`), `permission_ceiling_actor_id()`
    hacía saltar `sqlalchemy.exc.MissingGreenlet`: `select(Actor)` (consulta
    polimórfica por la clase base) no unía por defecto la tabla del subtipo
    concreto, así que leer una columna propia de `Agent` sobre un actor cargado
    así disparaba una carga perezosa fuera de cualquier `await` — y toda
    petición real usa una sesión nueva (`db/session.py`), así que esto habría
    reventado con `500` en producción cada vez que se intentara añadir un
    agente como miembro o que un agente creara un tablero. Ninguna prueba
    anterior lo detectó porque `db_session` se comparte durante todo el test:
    el objeto ya estaba "caliente" en el *identity map*. Arreglado en
    `models/actor.py` con `with_polymorphic="*"` en `Actor.__mapper_args__`: una
    consulta por la clase base ahora hace el `JOIN` a `people`/`agents` en la
    misma consulta, siempre. No afecta al contrato ni a ninguna migración —
    es solo la estrategia de carga del ORM.
