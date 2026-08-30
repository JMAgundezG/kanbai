# Spec · TASK-04 · Tableros y membresía

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-04](plan-TASK-04.md) · **Tarea:** [TASK-04](../tasks/TASK-04-tableros-y-membresia.md)

## Backend (`backend/src/kanbai/`)

### Modelos (`models/`)

`models/board.py`:

```python
class Board(Base):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

Sin `owner_id`: la propiedad "quién es owner" vive enteramente en `board_members`
(una fila con `role="owner"`), no duplicada como columna del tablero — evita que las
dos fuentes de verdad se desincronicen. Sin `updated_at`: no lo pide ningún criterio
de aceptación y no hay lectura que lo necesite todavía; se añade el día que haga
falta.

`models/board_member.py`:

```python
class BoardMember(Base):
    __tablename__ = "board_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[Actor] = relationship(Actor, lazy="selectin")

    __table_args__ = (
        UniqueConstraint("board_id", "actor_id", name="uq_board_members_board_id_actor_id"),
        CheckConstraint("role IN ('owner', 'member')", name="ck_board_members_role"),
    )
```

Decisiones:

- **FK a `actors.id`, no a `people.actor_id`.** Es literalmente la invariante de
  §0: la tabla de membresía no sabe ni le importa si el actor es persona o agente.
  `ON DELETE CASCADE` en ambas FKs: borrar un tablero borra sus membresías; borrar
  un actor (fuera de alcance aquí, pero es la FK correcta) borra sus membresías.
- **`role` como `String(20)`, no `Enum` de Postgres**, mismo criterio que
  `Actor.kind` en TASK-03: evita `ALTER TYPE` si algún día aparece un tercer rol.
  A diferencia de `kind` (que sí anticipa un tercer valor en TASK-09), aquí no hay
  ningún tercer rol previsto por ninguna tarea del tablero — así que, a diferencia
  de `kind`, sí se añade un `CHECK` a nivel de base de datos que fija los dos
  valores válidos: una fila con un rol inválido nunca debería poder existir, y ese
  riesgo es real (open a los datos entran por más de un servicio a la vez que este
  proyecto crezca).
- **`UniqueConstraint(board_id, actor_id)`**: un actor no puede tener dos filas de
  membresía en el mismo tablero. Nombrada a mano porque la convención de
  `db/base.py` para `uq` solo usa `column_0_name` (colisionaría con cualquier otra
  unicidad futura sobre `board_id` en solitario).
- **`relationship(Actor, lazy="selectin")`**: `BoardMemberRead` anida `ActorRead`
  (ver más abajo); `selectin` evita N+1 al listar miembros sin tener que acordarse
  de pasar `.options(selectinload(...))` en cada consulta que toque esta relación.

`models/__init__.py` añade `Board`, `BoardMember` a los reexports.

### Migración (`migrations/versions/`)

`alembic revision --autogenerate -m "add boards and board members"` debe generar:

- `CREATE TABLE boards (id UUID PK, name VARCHAR(200) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())`.
- `CREATE TABLE board_members (id UUID PK, board_id UUID NOT NULL FK→boards.id ON DELETE CASCADE, actor_id UUID NOT NULL FK→actors.id ON DELETE CASCADE, role VARCHAR(20) NOT NULL DEFAULT 'member', created_at TIMESTAMPTZ NOT NULL DEFAULT now())` + índices `ix_board_members_board_id`, `ix_board_members_actor_id` + `uq_board_members_board_id_actor_id` + `ck_board_members_role`.

A revisar a mano: ambos `ondelete="CASCADE"` presentes en el SQL generado (Alembic a
veces los omite si no detecta el `ondelete` del modelo — aquí está explícito), que
el `CHECK` se genera con la condición correcta y no como un `Enum` nativo, y que los
nombres de índice/constraint siguen la convención de `db/base.py`. Tras aplicar,
`alembic revision --autogenerate -m "check"` debe salir vacía; se borra esa revisión.

### Errores (`core/exceptions.py`)

Nueva excepción:

```python
class AuthorizationError(KanbaiError):
    """The actor already knows the resource exists (is a member of its board) but
    lacks the role the action requires. Distinct from NotFoundError, which is for
    an actor with no visibility into the resource at all."""

    status_code = HTTPStatus.FORBIDDEN
    default_message = "No tienes permisos suficientes para esta acción."
```

No sustituye a `NotFoundError` en ningún caso de "no soy miembro": esa sigue siendo
siempre 404, por la propia invariante del dominio. `AuthorizationError` solo aparece
cuando el actor **ya es miembro confirmado** del tablero (por tanto ya sabe que
existe) y la acción concreta exige el rol `owner`.

### Schemas (`schemas/`)

`schemas/pagination.py` (genérico, primer uso en el proyecto — lo reutiliza
cualquier listado futuro):

```python
from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    page: int
    size: int
```

`schemas/board.py`:

```python
class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BoardUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BoardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    # The requesting actor's own role on this board — not a column on `Board`,
    # assembled by the router from the (board, role) pair the service returns.
    # Cheap (already queried to authorize the request) and something the
    # frontend needs to decide what to show (e.g. only an owner sees "delete").
    role: Literal["owner", "member"]
```

`schemas/board_member.py`:

```python
class BoardMemberCreate(BaseModel):
    actor_id: uuid.UUID
    role: Literal["owner", "member"] = "member"


class BoardMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    actor: ActorRead
    role: Literal["owner", "member"]
    created_at: datetime
```

`BoardMemberRead.actor` reutiliza `ActorRead` de TASK-03 tal cual — indiferente al
tipo de actor por construcción, sin ningún campo nuevo. `model_validate(member)`
resuelve el anidado directamente desde el ORM porque `BoardMember.actor` es una
relación cargada (`lazy="selectin"`) y `ActorRead` ya declara `from_attributes=True`.

### Repositorios (`repositories/`)

`repositories/membership.py` — la pieza reutilizable central de esta tarea:

```python
"""The one place that encodes 'boards this actor belongs to' as SQL. Any future
repository whose rows hang off a board — columns, cards (via their column),
comments and events (via their card) — filters through this subquery instead of
re-deriving the join. Reused here by repositories/boards.py; TASK-05 onward reuses
it the same way for its own tables."""

import uuid

from sqlalchemy import Select, select

from kanbai.models.board_member import BoardMember


def board_ids_for_actor(actor_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return select(BoardMember.board_id).where(BoardMember.actor_id == actor_id)
```

Uso previsto en tareas futuras: `.where(Column.board_id.in_(board_ids_for_actor(actor_id)))`
(TASK-05), `.join(Column, ...).where(Column.board_id.in_(board_ids_for_actor(actor_id)))`
para tarjetas (TASK-06), y análogamente para comentarios y eventos vía su tarjeta.

`repositories/boards.py`:

- `list_boards_for_actor(session, actor_id, *, limit, offset) -> tuple[list[tuple[Board, str]], int]`
  — un `SELECT Board, BoardMember.role JOIN board_members ...` (necesita el rol por
  fila, así que hace el join directo a `board_members` en vez de pasar por la
  subconsulta); el conteo total sí reutiliza `board_ids_for_actor` porque no
  necesita el rol:
  `select(func.count()).select_from(Board).where(Board.id.in_(board_ids_for_actor(actor_id)))`.
- `get_board_for_actor(session, board_id, actor_id) -> tuple[Board, str] | None` —
  mismo join, filtrado también por `Board.id == board_id`. Devuelve `None` tanto si
  el tablero no existe como si existe pero el actor no es miembro — el router nunca
  distingue esos dos casos (404 en ambos, por diseño).
- `create_board(session, *, name) -> Board`.
- `rename_board(session, board, name) -> Board`.
- `delete_board(session, board) -> None`.

`repositories/board_members.py`:

- `list_members(session, board_id, *, limit, offset) -> tuple[list[BoardMember], int]`.
- `get_member_by_actor(session, board_id, actor_id) -> BoardMember | None`.
- `get_member_by_id(session, board_id, member_id) -> BoardMember | None`.
- `count_owners(session, board_id) -> int`.
- `add_member(session, *, board_id, actor_id, role) -> BoardMember`.
- `remove_member(session, member) -> None`.

Todas las consultas SQL de tableros y membresía viven en estos tres módulos; ningún
router ni service compone `select(...)`.

### Servicios (`services/boards.py`)

```python
OWNER = "owner"
MEMBER = "member"

async def list_boards(session, *, actor, limit, offset) -> tuple[list[tuple[Board, str]], int]
async def create_board(session, *, actor, name) -> tuple[Board, str]
async def get_board(session, *, actor, board_id) -> tuple[Board, str]              # 404 si no es miembro
async def rename_board(session, *, actor, board_id, name) -> tuple[Board, str]     # 404 / 403 si no es owner
async def delete_board(session, *, actor, board_id) -> None                        # 404 / 403 si no es owner
async def list_members(session, *, actor, board_id, limit, offset) -> tuple[list[BoardMember], int]  # 404
async def add_member(session, *, actor, board_id, new_actor_id, role) -> BoardMember   # 404 / 403 / 404 (actor destino) / 409 (duplicado)
async def remove_member(session, *, actor, board_id, member_id) -> None                # 404 / 403 / 404 (miembro) / 409 (único owner)
```

Reglas:

- `create_board`: crea el `Board`, añade al actor como `owner` en la misma
  transacción, `commit()` único. Ningún tablero existe nunca sin owner, ni por un
  instante observable desde fuera.
- `get_board` es la base de `rename_board`, `delete_board`, `list_members`,
  `add_member` y `remove_member`: todas empiezan comprobando membresía con la
  misma función, así que el 404 por "no soy miembro" es idéntico en las seis rutas.
- `rename_board` / `delete_board`: tras confirmar membresía, si `role != OWNER` →
  `AuthorizationError`. El actor ya sabe que el tablero existe (es miembro); lo que
  no tiene es el rol — de ahí 403, no 404.
- `add_member`: solo `owner`. Si `new_actor_id` no corresponde a ningún `Actor` →
  `NotFoundError("El actor indicado no existe.")` (mismo tipo de error que "tablero
  ajeno", pero por un motivo distinto: aquí el recurso referenciado sencillamente
  no existe, no es que se oculte). Si ya es miembro → `ConflictError`.
- `remove_member`: permitido si el actor que pide es `owner`, **o** si
  `member.actor_id == actor.id` (quitarse a uno mismo, sin importar el rol propio).
  Cualquier otro caso (no-owner intentando quitar a alguien más) → 403. Si el
  miembro a quitar tiene `role == OWNER`, se cuenta cuántos owners quedan en el
  tablero (`count_owners`); si es 1, `ConflictError("No puedes quitar al único
  owner del tablero.")` — se aplica igual sea el propio owner quitándose o (en
  teoría, nunca alcanzable porque ya se exige ser owner o ser uno mismo) otro
  intentándolo.

Ningún servicio ni router de esta tarea contiene `if actor.kind == ...`: la única
lectura de `kind` en todo el flujo es la que ya hacía TASK-03 al construir
`ActorRead`.

### API (`api/deps.py`)

Paginación reutilizable, mismo patrón "clase con `__init__` + `Depends()` vacío"
que documenta FastAPI para dependencias con parámetros de query:

```python
class PaginationParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Página, empieza en 1")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="Tamaño de página, máximo 100")] = 20,
    ) -> None:
        self.page = page
        self.size = size

    @property
    def limit(self) -> int:
        return self.size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


PaginationDep = Annotated[PaginationParams, Depends()]
```

`size` topa en 100 a nivel de validación de FastAPI (`le=100`): pedir más devuelve
`422`, no un truncado silencioso — es el "máximo de `limit` aplicado" del criterio
de aceptación, hecho explícito en el contrato en vez de escondido en el servicio.

### Router (`api/routers/boards.py`)

```
POST   /api/v1/boards                        BoardCreate  → 201 BoardRead
GET    /api/v1/boards         ?page,size                  → 200 Page[BoardRead]
GET    /api/v1/boards/{board_id}                           → 200 BoardRead / 404
PATCH  /api/v1/boards/{board_id}              BoardUpdate  → 200 BoardRead / 404 / 403
DELETE /api/v1/boards/{board_id}                           → 204 / 404 / 403
GET    /api/v1/boards/{board_id}/members ?page,size        → 200 Page[BoardMemberRead] / 404
POST   /api/v1/boards/{board_id}/members      BoardMemberCreate → 201 BoardMemberRead / 404 / 403 / 409
DELETE /api/v1/boards/{board_id}/members/{member_id}        → 204 / 404 / 403 / 409
```

Todas las rutas dependen de `CurrentActor` (401 si no hay sesión, ya lo resuelve
`CurrentActor` de TASK-03 sin cambios) y `SessionDep`. El router no compone SQL: solo
llama a `services.boards`, y traduce `(Board, role)` a `BoardRead` con un pequeño
helper local `_board_read(board, role)`. `api/router.py` añade
`api_router.include_router(boards.router)`.

## Frontend (`frontend/src/`)

No se toca. `uv run poe openapi` deja `backend/openapi.json` sincronizado (lo exige
`tests/test_openapi.py`, ya existente). Ningún código de `frontend/` consume
`/boards` todavía — la primera vez será TASK-08 — así que no se regenera
`schema.d.ts` (mismo criterio que aplicó TASK-03 a `/auth`).

## Contrato API

| Método | Ruta | Request | Response |
|--------|------|---------|----------|
| POST | `/api/v1/boards` | `BoardCreate` | `201 BoardRead` |
| GET | `/api/v1/boards` | query `page`, `size` | `200 Page[BoardRead]` |
| GET | `/api/v1/boards/{board_id}` | — | `200 BoardRead` / `404` |
| PATCH | `/api/v1/boards/{board_id}` | `BoardUpdate` | `200 BoardRead` / `404` / `403` |
| DELETE | `/api/v1/boards/{board_id}` | — | `204` / `404` / `403` |
| GET | `/api/v1/boards/{board_id}/members` | query `page`, `size` | `200 Page[BoardMemberRead]` / `404` |
| POST | `/api/v1/boards/{board_id}/members` | `BoardMemberCreate` | `201 BoardMemberRead` / `404` / `403` / `409` |
| DELETE | `/api/v1/boards/{board_id}/members/{member_id}` | — | `204` / `404` / `403` / `409` |

## Casos límite y errores

- Tablero ajeno (no soy miembro) en cualquier ruta bajo `/boards/{board_id}...` →
  `404`, nunca `403` — cubre lectura, renombrado, borrado y gestión de miembros.
- Soy miembro pero no `owner` e intento renombrar/borrar el tablero, o añadir/quitar
  a otro miembro → `403` (`AuthorizationError`), distinto del caso anterior porque
  ya sé que el recurso existe.
- Añadir como miembro a un `actor_id` que no existe en absoluto → `404`.
- Añadir como miembro a un actor que ya es miembro → `409`.
- Añadir como miembro a un actor con `kind="agent"` (sin fila en `people`, estado
  previo a TASK-09) → funciona exactamente igual que con una persona; es el test
  que demuestra la invariante de §0.
- Quitar al único `owner` (sea el propio owner quitándose, o intentarlo — solo el
  propio owner o otro owner pueden iniciar la baja) → `409` con mensaje claro.
- Un miembro no-owner se quita a sí mismo → `204`, permitido (abandonar el
  tablero no requiere ser owner).
- Hay más de un `owner` y uno de ellos se quita → `204`, permitido: la regla mira
  cuántos owners quedan, no quién concretamente se va.
- `page`/`size` fuera de rango (`page < 1`, `size < 1` o `size > 100`) → `422` de
  validación de FastAPI.
- `name` vacío o de más de 200 caracteres en crear/renombrar → `422`.
- Petición sin sesión a cualquier ruta de `/boards` → `401` (comportamiento ya
  existente de `CurrentActor`, sin tocar).

## Plan de tests

`backend/tests/test_boards.py`, siguiendo el estilo de `test_auth.py` (nombres en
español, fixtures de actor vía `services.auth.create_person`, `httpx.AsyncClient` +
cookies de sesión, login/logout secuencial sobre el mismo cliente para simular
actores distintos):

- `test_crear_tablero_deja_al_actor_como_owner`
- `test_crear_tablero_sin_sesion_devuelve_401`
- `test_crear_tablero_nombre_vacio_devuelve_422`
- `test_listar_tableros_devuelve_solo_los_propios` (dos personas, cada una con su
  tablero; cada una ve solo el suyo en `GET /boards`)
- `test_listar_tableros_respeta_paginacion` (forma `{items, total, page, size}`)
- `test_listar_tableros_size_por_encima_del_maximo_devuelve_422`
- `test_obtener_tablero_propio_devuelve_detalle_con_rol`
- `test_obtener_tablero_ajeno_devuelve_404`
- `test_renombrar_tablero_como_owner`
- `test_renombrar_tablero_ajeno_devuelve_404`
- `test_renombrar_tablero_como_member_no_owner_devuelve_403`
- `test_borrar_tablero_como_owner`
- `test_borrar_tablero_como_member_no_owner_devuelve_403`
- `test_anadir_miembro_persona`
- `test_anadir_miembro_agente_funciona_igual_que_persona` (crea un `Actor` crudo
  con `kind="agent"`, sin fila `people` — la invariante de §0 en un test concreto)
- `test_anadir_miembro_duplicado_devuelve_409`
- `test_anadir_miembro_actor_inexistente_devuelve_404`
- `test_anadir_miembro_como_no_owner_devuelve_403`
- `test_listar_miembros_incluye_al_owner`
- `test_listar_miembros_tablero_ajeno_devuelve_404`
- `test_quitar_miembro_como_owner`
- `test_quitar_unico_owner_devuelve_409`
- `test_owner_puede_quitarse_si_hay_otro_owner`
- `test_miembro_no_owner_puede_quitarse_a_si_mismo`
- `test_quitar_a_otro_miembro_sin_ser_owner_devuelve_403`
- `test_quitar_miembro_inexistente_devuelve_404`

Cubre camino feliz, validación, acceso ajeno (404) y permisos por rol (403/409) en
cada endpoint, más la invariante central de la tarea.

## Desviaciones respecto al plan

Ninguna de fondo. El plan ya fijaba: `BoardMember` apuntando a `Actor` (no a
`Person`), el filtro de pertenencia encapsulado en `repositories/membership.py`,
paginación genérica nueva, y permisos `owner`-only para renombrar/borrar/gestionar
miembros con 403 vía una `AuthorizationError` nueva. Esta spec solo los concreta en
firmas y consultas exactas.

Un ajuste detectado durante la implementación, no anticipado en la spec original:

- **El test de la invariante persona/agente no puede crear un `Actor(kind="agent")`
  a secas.** La herencia *joined-table* de SQLAlchemy valida el discriminador contra
  los `polymorphic_identity` registrados en cuanto se vuelve a leer la fila —
  `select(Actor)` (usado por `get_actor_by_id`, que `add_member` llama siempre)
  falla con `AssertionError: No such polymorphic_identity 'agent' is defined`
  porque hoy no existe ninguna subclase `Agent` (eso es TASK-09). Solución: el
  propio `tests/test_boards.py` declara una subclase de test
  `_AgentDouble(Actor)` con `__mapper_args__ = {"polymorphic_identity": "agent"}`
  y sin `__tablename__` (herencia de tabla única, no añade columnas ni tabla) —
  registra la identidad polimórfica solo para la duración de la suite, sin tocar
  código de producción ni adelantar alcance de TASK-09. El resto del test corre
  contra el repositorio/servicio real sin ningún atajo.
