# Spec · TASK-03 · Actores y autenticación de personas

**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-03](plan-TASK-03.md) · **Tarea:** [TASK-03](../tasks/TASK-03-actores-y-sesion.md)

## Backend (`backend/src/kanbai/`)

### Dependencia nueva

- `argon2-cffi` (`uv add argon2-cffi`). Justificación: hash de contraseña Argon2id,
  recomendación actual de OWASP para nuevo código; `passlib` (la alternativa más
  usada históricamente) está sin mantenimiento activo. No se añade `python-jose` ni
  similar: no hay JWT en esta tarea.

### Modelos (`models/`)

`models/actor.py` — *joined-table inheritance*:

```python
class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __mapper_args__ = {"polymorphic_identity": "actor", "polymorphic_on": "kind"}


class Person(Actor):
    __tablename__ = "people"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "person"}
```

- `kind` es el discriminador (`"person" | "agent"`, este último llega en TASK-09).
  Se guarda como `String(20)` y no como `Enum` de PostgreSQL: un `Enum` nativo obliga
  a `ALTER TYPE` en cada tarea que añada un valor (TASK-09), justo la migración
  frágil que Alembic peor maneja. Ninguna consulta filtra por `kind` fuera de la capa
  de autenticación: leer el actor por `id` ya basta, SQLAlchemy resuelve la subclase.
- `email` se normaliza a minúsculas en el servicio antes de guardar/consultar (evita
  duplicados por mayúsculas sin depender de `citext`, extensión no instalada).
- `id` es UUID generado en Python (`default=uuid.uuid4`), no serial: evita filtrar
  cuántos actores existen o su orden de alta por el propio identificador.

`models/session.py` — sesión de persona, no forma parte de la jerarquía de actor:

```python
class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- `token_hash` guarda el SHA-256 hexadecimal (64 chars) del token de sesión; el token
  en claro solo existe en la cookie del cliente, nunca en base de datos ni en logs
  (mismo patrón que usará TASK-09 para las API keys de agentes).
- Nombrada `AuthSession`, no `Session`: evita chocar por nombre con
  `sqlalchemy.ext.asyncio.AsyncSession`/`Session` en los mismos módulos.

`models/__init__.py` reexporta `Actor`, `Person`, `AuthSession` para que Alembic las
vea en `Base.metadata`.

### Migración (`migrations/versions/`)

`alembic revision --autogenerate -m "add actors, people and sessions"` debe generar:

- `CREATE TABLE actors (id UUID PK, kind VARCHAR(20) NOT NULL, display_name VARCHAR(100) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())`.
- `CREATE TABLE people (actor_id UUID PK FK→actors.id ON DELETE CASCADE, email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL)` + índice único `uq_people_email`.
- `CREATE TABLE sessions (id UUID PK, actor_id UUID NOT NULL FK→actors.id ON DELETE CASCADE, token_hash VARCHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL)` + índice único `uq_sessions_token_hash` + índice `ix_sessions_actor_id`.

A revisar a mano: que el FK de `people.actor_id` lleve `ondelete="CASCADE"` (Alembic a
veces lo omite si no está explícito en el modelo — ya lo está), que los tipos
`TIMESTAMPTZ` sean correctos (no `TIMESTAMP` sin zona) y que los nombres de
constraint sigan la convención de `db/base.py`. Tras aplicar, correr
`alembic revision --autogenerate -m "check"` y confirmar que sale vacía; borrar esa
revisión de comprobación.

### Configuración (`core/config.py`)

Dos campos nuevos en `Settings`, documentados en `.env.example`:

```python
session_cookie_name: str = "kanbai_session"
session_ttl_days: int = 14
```

### Errores (`core/exceptions.py`)

```python
class AuthenticationError(KanbaiError):
    """Credenciales ausentes, inválidas o sesión caducada."""

    status_code = HTTPStatus.UNAUTHORIZED
    default_message = "No has iniciado sesión."
```

Se usa con mensaje por defecto para "sin sesión" y con un mensaje explícito
("El email o la contraseña no son correctos.") para login fallido — el mismo texto
tanto si el email no existe como si la contraseña es incorrecta.

### Seguridad (`core/security.py`)

```python
_hasher = PasswordHasher()  # argon2.PasswordHasher, parámetros por defecto (Argon2id)
_DUMMY_HASH = _hasher.hash("no-existe-pero-tarda-lo-mismo")

def hash_password(password: str) -> str: ...
def verify_password(password: str, password_hash: str) -> bool: ...  # nunca lanza; False si no coincide o el hash es inválido
def verify_dummy_password(password: str) -> None: ...  # gasta el mismo tiempo que verify_password cuando el email no existe, para no filtrar por timing si hay cuenta o no

def generate_session_token() -> str: ...  # secrets.token_urlsafe(32)
def hash_session_token(token: str) -> str: ...  # sha256(token).hexdigest()
```

### Schemas (`schemas/`)

`schemas/actor.py`:

```python
class ActorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["person", "agent"]
    display_name: str
    created_at: datetime
```

Deliberadamente **sin** `email`: el actor autenticado se identifica por tipo e
identidad visible, no por su credencial. Mantiene `/auth/me` agnóstico del tipo —
cuando TASK-09 añada agentes, el mismo schema les sirve sin tocarlo.

`schemas/auth.py`:

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr  # nunca aparece en claro en reprs, logs ni /docs de ejemplo
```

`POST /auth/login` responde `ActorRead` (la sesión viaja en la cookie, no en el
cuerpo). `POST /auth/logout` responde `204 No Content`. `GET /auth/me` responde
`ActorRead`.

### Repositorios (`repositories/`)

`repositories/actors.py`:
- `get_person_by_email(session, email: str) -> Person | None`
- `create_person(session, *, email: str, password_hash: str, display_name: str) -> Person`
- `get_actor_by_id(session, actor_id: uuid.UUID) -> Actor | None` (carga polimórfica:
  `select(Actor).where(Actor.id == actor_id)` ya devuelve la subclase concreta).

`repositories/sessions.py`:
- `create_session(session, *, actor_id, token_hash, expires_at) -> AuthSession`
- `get_valid_session_by_token_hash(session, token_hash: str) -> AuthSession | None`
  (filtra `expires_at > now()` en la propia consulta).
- `delete_session_by_token_hash(session, token_hash: str) -> None`

Todas las consultas SQL viven aquí; ningún router ni service compone `select(...)`.

### Servicios (`services/auth.py`)

- `async def login(session, *, email, password, ttl) -> tuple[Person, str, datetime]`:
  normaliza el email, busca la persona; si no existe, llama a
  `verify_dummy_password` y lanza `AuthenticationError` con el mensaje genérico. Si
  existe, verifica la contraseña con `verify_password`; si falla, mismo error y
  mensaje. Si es válida: genera token, hash, `create_session`, `session.commit()`,
  y devuelve `(person, token_en_claro, expires_at)`.
- `async def resolve_actor(session, token: str) -> Actor`: hashea el token, busca
  sesión válida; si no hay, `AuthenticationError()` (mensaje por defecto). Carga el
  actor por `session_row.actor_id`; si por lo que sea no existe (no debería, hay FK
  `CASCADE`), mismo error.
- `async def logout(session, token: str) -> None`: hashea el token y borra la
  sesión si existe (idempotente: no falla si ya no está), `session.commit()`.
- `async def create_person(session, *, email, password, display_name) -> Person`:
  uso interno (tests, semillas futuras), no expuesto por HTTP. Hashea la contraseña y
  delega en el repositorio; traduce `IntegrityError` (email duplicado) a
  `ConflictError("Ya existe una persona con ese email.")`.

Commits los hace el servicio, no el router (mismo patrón que documenta
`db/session.py`).

### API (`api/deps.py`)

```python
async def get_current_actor(request: Request, session: SessionDep, settings: SettingsDep) -> Actor:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthenticationError()
    return await auth_service.resolve_actor(session, token)

CurrentActor = Annotated[Actor, Depends(get_current_actor)]
```

Preparada para TASK-09: cuando lleguen las API keys de agente, la rama
`Authorization: Bearer` se añade **dentro** de esta misma función (probar cookie,
si no hay, probar cabecera) sin tocar su firma ni ningún router/servicio que ya la
use — la ramificación vive en la dependencia de infraestructura de autenticación,
que es sobre credenciales, no sobre el tipo de dominio del actor (cumple la regla de
`CLAUDE.md` § 0: nada de `if actor.kind == "agent"` en servicios o routers).

### Router (`api/routers/auth.py`)

```
POST /api/v1/auth/login
  body: LoginRequest
  200 → ActorRead + Set-Cookie: kanbai_session=<token>; HttpOnly; SameSite=Lax;
        Secure (fuera de "local"); Max-Age=<session_ttl_days*86400>; Path=/
  401 → AuthenticationError si las credenciales no son válidas

POST /api/v1/auth/logout
  204 → borra la sesión si el token de la cookie es válido (no exige sesión activa:
        si no hay cookie o ya no es válida, sigue devolviendo 204 e igualmente
        limpia la cookie del cliente) + Set-Cookie que expira la cookie

GET /api/v1/auth/me
  200 → ActorRead del actor de CurrentActor
  401 → AuthenticationError si no hay sesión válida
```

`api/router.py` monta `auth.router` (prefijo `/auth`, tag `auth`) bajo el router de
`/api/v1`.

## Frontend (`frontend/src/`)

No toca en esta tarea (TASK-07 consume estos endpoints). Se exporta igualmente el
contrato con `uv run poe openapi` para que `backend/openapi.json` quede al día; la
regeneración de `frontend/src/api/schema.d.ts` se deja anotada como pendiente de
TASK-07 en sus notas, no se ejecuta aquí porque el frontend no tiene ningún consumidor
de estos tipos todavía.

## Contrato API

| Método | Ruta | Request | Response |
|--------|------|---------|----------|
| POST | `/api/v1/auth/login` | `LoginRequest` | `200 ActorRead` / `401` |
| POST | `/api/v1/auth/logout` | — | `204` |
| GET | `/api/v1/auth/me` | — | `200 ActorRead` / `401` |

Ningún listado en esta tarea: no aplica la forma `{items, total, page, size}`.

## Casos límite y errores

- Email con mayúsculas distintas en login vs. alta → se normaliza a minúsculas en
  ambos lados, no hay falso negativo.
- Dos personas con el mismo email → `IntegrityError` de la unicidad de `people.email`
  traducida a `ConflictError` (409) en `create_person`; no hay endpoint público que lo
  dispare en esta tarea, pero el test lo cubre a nivel de servicio.
- Contraseña incorrecta vs. email inexistente → mismo `401` y mismo mensaje; el test
  verifica que el cuerpo de la respuesta es idéntico en ambos casos.
- Sesión caducada (`expires_at` pasado) → `resolve_actor` no la encuentra (la
  consulta filtra por `expires_at > now()`) → `401` igual que sin cookie.
- Logout sin sesión activa (cookie ausente o inválida) → `204` igualmente, no `401`:
  cerrar sesión es idempotente por diseño.
- Contraseña nunca en claro fuera de la petición: `SecretStr` en el schema, y
  `password_hash`/`token_hash` son lo único que toca el disco.

## Plan de tests

`backend/tests/`, nuevo `tests/test_auth.py` (más una fixture de persona en
`conftest.py` o en el propio archivo, ya que hoy no hay factoría de datos):

- `test_login_correcto_devuelve_sesion_y_200`: crea una persona vía
  `services.auth.create_person`, hace login con las credenciales correctas, comprueba
  `200`, cuerpo `ActorRead` (`kind == "person"`), cookie de sesión presente.
- `test_login_password_incorrecta_devuelve_401_generico`
- `test_login_email_inexistente_devuelve_401_generico_e_igual_al_anterior`: compara
  el cuerpo de ambas respuestas 401 y confirma que son idénticas (no delata si el
  email existe).
- `test_login_no_expone_la_contrasena_en_la_respuesta`
- `test_me_sin_sesion_devuelve_401`
- `test_me_con_sesion_devuelve_el_actor`
- `test_logout_invalida_la_sesion`: login, logout (`204`), `/me` posterior → `401`.
- `test_logout_sin_sesion_devuelve_204`
- `test_create_person_email_duplicado_devuelve_conflicto` (nivel servicio,
  `ConflictError`).
- Reutiliza el patrón de `tests/test_health.py` para el estilo (nombres en español,
  `httpx.AsyncClient` + `ASGITransport`, fixtures de `conftest.py`).

## Desviaciones respecto al plan

Ninguna de fondo: el plan ya fijaba herencia (*joined-table*), sesión en cookie
respaldada en base de datos y Argon2 vía `argon2-cffi`; esta spec solo los concreta.
Dos ajustes detectados durante la implementación, no en la spec original:

- **Dependencia adicional no anticipada:** `email-validator`, requerida en tiempo de
  ejecución por `pydantic.EmailStr` (no viene con `pydantic` a secas). Se justifica
  igual que `argon2-cffi`: es la dependencia estándar de facto para ese tipo, no hay
  alternativa razonable en la librería estándar.
- **Flag `Secure` de la cookie de sesión:** la spec proponía `secure=True` fuera de
  `environment == "local"`, lo que también la activaba en `environment == "test"`.
  El propio test suite lo detectó: `httpx.AsyncClient` habla HTTP plano (no HTTPS)
  incluso contra la app en memoria, así que una cookie `Secure` se descarta en
  silencio y `/auth/me` nunca ve la sesión recién creada. Corregido a
  `secure=(environment == "production")`: `local` y `test` corren sobre HTTP
  (dev local sin TLS y el transporte ASGI de los tests), solo `production` está
  garantizado detrás de TLS.
