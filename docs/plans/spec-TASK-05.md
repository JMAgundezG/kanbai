# Spec · TASK-05 · Columnas del tablero

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-05](plan-TASK-05.md) · **Tarea:** [TASK-05](../tasks/TASK-05-columnas.md)

## Esquema de posiciones (decisión central de la tarea)

**Float (`DOUBLE PRECISION`), no entero con reindexado.** Cada `BoardColumn` (y, por
herencia directa, cada `Card` en TASK-06) tiene una columna `position: float` y una
`UniqueConstraint(<padre>, position)` **aplazable**
(`deferrable=True, initially="DEFERRED"`, solo la respeta PostgreSQL — no SQLite):

```python
UniqueConstraint(
    "board_id", "position",
    name="uq_board_columns_board_id_position",
    deferrable=True,
    initially="DEFERRED",
)
```

Por qué esto y no reindexado entero:

- **Mover una fila es un único `UPDATE`.** Con reindexado entero (0,1,2,…), mover una
  columna/tarjeta a otra posición obliga a desplazar (`+1`/`-1`) todas las filas entre
  el origen y el destino en la misma transacción — más filas tocadas, más
  probabilidad de que dos movimientos concurrentes se pisen. Con float, el movimiento
  de una fila escribe solo esa fila: no hay contención con un movimiento concurrente
  de una fila distinta, que es justo lo que TASK-06 exige para tarjetas.
- **La unicidad aplazada resuelve el caso "reescribir varias filas a la vez" sin
  ceremonia.** El endpoint de reordenación de columnas SÍ toca varias filas en una
  llamada; sin aplazar el constraint, la fila `N` podría intentar tomar temporalmente
  el valor que la fila `M` todavía no ha soltado dentro de la misma transacción. Con
  `INITIALLY DEFERRED`, Postgres solo comprueba unicidad al hacer `COMMIT`, así que el
  orden interno de los `UPDATE` no importa.
- **Reutilizable tal cual por TASK-06**: mismo tipo de columna (`float`), mismo patrón
  de constraint aplazable con el nombre de la FK padre que corresponda
  (`column_id` en vez de `board_id`), mismas dos operaciones (`append` al crear,
  `set_positions` al reordenar/mover).

Asignación de valores:

- **Alta (crear columna nueva, o sembrar las iniciales de un tablero):** se añade al
  final: `position = max(posiciones existentes del tablero) + GAP`, con
  `GAP = 1024.0` (constante en `repositories/columns.py`, para que TASK-06 copie el
  mismo valor). Si el tablero no tiene columnas todavía, la primera toma `GAP`.
- **Reordenación completa (`PUT .../columns/reorder`):** dado el nuevo orden completo,
  se reasignan posiciones **enteras consecutivas como float** (`0.0, 1.0, 2.0, …`,
  índice de la lista recibida). Esto dej a la vez: (a) la propiedad literal "sin
  huecos ni posiciones repetidas" que pide el criterio de aceptación, con un test que
  lo comprueba directamente sobre los valores, y (b) sirve de recompactación
  automática — si alguna vez las inserciones fraccionales fueran erosionando la
  precisión de `float`, una reordenación (aunque sea con el mismo orden) la resetea.
- El valor de `position` no tiene significado fuera del orden relativo: el frontend
  (TASK-08) lo usa solo para ordenar, nunca lo muestra.

TASK-06 reutiliza exactamente este mecanismo para `cards.position` (constraint
aplazable sobre `(column_id, position)`, `GAP` al añadir, punto medio
`(antes.position + después.position) / 2` al mover una tarjeta entre dos vecinas sin
tocar ninguna otra fila).

## Decisiones abiertas cerradas

### 1. Columnas iniciales al crear un tablero

`services/columns.py::seed_default_columns(session, board_id) -> list[BoardColumn]`
crea tres columnas fijas, en español, en este orden:

1. "Por hacer"
2. "En curso"
3. "Hecho"

`services/boards.py::create_board` las siembra en la misma transacción que crea el
tablero y la membresía `owner`, antes del único `commit()` — un tablero nunca es
observable desde fuera sin su juego de columnas, igual que nunca lo es sin su owner.
Sin plantillas configurables (fuera de alcance, ver "No entra" de la tarea).

### 2. Borrar una columna con tarjetas

**Política decidida: bloquear el borrado con `409 Conflict`** si la columna tiene
tarjetas — no "exigir destino" (mover las tarjetas a otra columna antes de borrar es
una operación explícita del usuario, más simple de razonar que un
reasignado implícito, y no obliga a inventar en esta tarea un parámetro
`?move_cards_to=`).

Hoy las tarjetas no existen, así que no hay ninguna consulta que hacer contra una
tabla `cards` inexistente. `services/columns.py::delete_column` queda con un
comentario explícito marcando el punto de extensión:

```python
async def delete_column(session, *, actor, board_id, column_id) -> None:
    _, role = await boards_service.get_board(session, actor=actor, board_id=board_id)
    column = await _get_column_or_404(session, board_id=board_id, column_id=column_id)
    # TASK-06 adds the check here: if the column has cards, raise
    # ConflictError("No se puede borrar una columna con tarjetas."). No cards model
    # exists yet, so there is nothing to query — this comment is the contract TASK-06
    # must honor when it adds `Card`.
    await columns_repository.delete_column(session, column)
    await session.commit()
```

El test de hoy cubre "borrar una columna vacía funciona" (204); el test de
"borrar una columna con tarjetas devuelve 409" se añade en TASK-06, cuando exista algo
que crear dentro de la columna para probarlo. Se anota en
`docs/tasks/TASK-06-tarjetas.md` (nota, no criterio nuevo) al cerrar esta tarea.

## Rol requerido para gestionar columnas

**Cualquier miembro del tablero** (`owner` o `member`) puede crear, leer, renombrar,
reordenar y borrar columnas — a diferencia de renombrar/borrar el tablero o gestionar
membresía (TASK-04, solo `owner`). Las columnas son la estructura del flujo de
trabajo del equipo, no administración del tablero; no hay ninguna acción de columnas
que la tarea reserve al owner. Ningún router ni servicio de esta tarea comprueba
`actor.kind` (invariante §0).

## Backend (`backend/src/kanbai/`)

### Modelo (`models/board_column.py`)

```python
"""A board column: one phase of the board's workflow. Named `BoardColumn`, not
`Column`, to avoid shadowing `sqlalchemy.Column` and to match the `boards`/
`board_members` naming precedent.

`position` is a float with a deferrable unique constraint per board — see
docs/plans/spec-TASK-05.md for why float instead of integer reindexing. TASK-06
copies this exact mechanism for `cards.position`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class BoardColumn(Base):
    __tablename__ = "board_columns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # None = no WIP limit. TASK-06 enforces this when moving cards; this task only
    # stores it.
    wip_limit: Mapped[int | None] = mapped_column(nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "board_id", "position",
            name="uq_board_columns_board_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("wip_limit IS NULL OR wip_limit > 0", name="wip_limit_positive"),
    )
```

`models/__init__.py` añade `BoardColumn` a los reexports.

### Migración

`alembic revision --autogenerate -m "add board columns"` debe generar:

- `CREATE TABLE board_columns (id UUID PK, board_id UUID NOT NULL FK→boards.id ON
  DELETE CASCADE, name VARCHAR(100) NOT NULL, wip_limit INTEGER NULL, position
  DOUBLE PRECISION NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())`
- Índice `ix_board_columns_board_id`.
- `uq_board_columns_board_id_position` — **a revisar a mano que Alembic incluye
  `deferrable=True, initially='DEFERRED'` en el DDL generado** (`ALTER TABLE ...
  ADD CONSTRAINT ... UNIQUE (...) DEFERRABLE INITIALLY DEFERRED`); si el
  autogenerate lo omite, se añade a mano en el archivo antes de aplicarlo — es el
  motivo de existir de todo este esquema, no es opcional.
- `ck_board_columns_wip_limit_positive` con la condición `wip_limit IS NULL OR
  wip_limit > 0`.

Tras aplicar (`alembic upgrade head`), un `alembic revision --autogenerate -m
"check"` debe salir vacío; se borra esa revisión de comprobación.

### Schemas (`schemas/column.py`)

```python
"""Schemas for board columns."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wip_limit: int | None = Field(default=None, gt=0)


class ColumnUpdate(BaseModel):
    # Full replace, like BoardUpdate — not a partial PATCH. Avoids a sentinel type
    # to distinguish "wip_limit not sent" from "wip_limit explicitly cleared to
    # None", and matches the one PATCH pattern already established in the project.
    name: str = Field(min_length=1, max_length=100)
    wip_limit: int | None = Field(default=None, gt=0)


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    wip_limit: int | None
    position: float
    created_at: datetime


class ColumnReorder(BaseModel):
    # The complete, ordered set of column ids for the board — not a partial move.
    # Validated in the service against the board's actual columns (services/columns.py).
    column_ids: list[uuid.UUID]
```

### Repositorio (`repositories/columns.py`)

```python
"""Queries on board columns. The only place that talks SQL for this table."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.board_column import BoardColumn
from kanbai.repositories.membership import board_ids_for_actor

# Spacing left between two adjacent positions on append, so a future insert between
# them (TASK-06 also uses this constant's value as its own starting gap) has room
# for a plain midpoint without immediately needing a full reindex.
GAP = 1024.0


async def list_columns_for_board(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[BoardColumn], int]:
    """Filters by board_ids_for_actor in addition to board_id: the actual 404 for
    an unrelated board is still services.boards.get_board (an empty list alone
    cannot distinguish "not a member" from "a member of an empty board"), but every
    query here still scopes ownership in SQL itself, never in Python, per
    CLAUDE.md §4."""
    membership_filter = BoardColumn.board_id.in_(board_ids_for_actor(actor_id))
    total = await session.scalar(
        select(func.count())
        .select_from(BoardColumn)
        .where(BoardColumn.board_id == board_id, membership_filter)
    )
    result = await session.execute(
        select(BoardColumn)
        .where(BoardColumn.board_id == board_id, membership_filter)
        .order_by(BoardColumn.position)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def list_all_columns_for_board(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID
) -> list[BoardColumn]:
    """Unpaginated: the reorder endpoint needs every column in one shot to
    validate the incoming id set against it."""
    result = await session.execute(
        select(BoardColumn)
        .where(
            BoardColumn.board_id == board_id,
            BoardColumn.board_id.in_(board_ids_for_actor(actor_id)),
        )
        .order_by(BoardColumn.position)
    )
    return list(result.scalars().all())


async def get_column_by_id(
    session: AsyncSession, board_id: uuid.UUID, column_id: uuid.UUID
) -> BoardColumn | None:
    result = await session.execute(
        select(BoardColumn).where(BoardColumn.board_id == board_id, BoardColumn.id == column_id)
    )
    return result.scalar_one_or_none()


async def get_max_position(session: AsyncSession, board_id: uuid.UUID) -> float | None:
    return await session.scalar(
        select(func.max(BoardColumn.position)).where(BoardColumn.board_id == board_id)
    )


async def create_column(
    session: AsyncSession, *, board_id: uuid.UUID, name: str, wip_limit: int | None, position: float
) -> BoardColumn:
    column = BoardColumn(board_id=board_id, name=name, wip_limit=wip_limit, position=position)
    session.add(column)
    await session.flush()
    return column


async def update_column(
    session: AsyncSession, column: BoardColumn, *, name: str, wip_limit: int | None
) -> BoardColumn:
    column.name = name
    column.wip_limit = wip_limit
    await session.flush()
    return column


async def delete_column(session: AsyncSession, column: BoardColumn) -> None:
    await session.delete(column)


async def set_positions(
    session: AsyncSession, columns_by_id: dict[uuid.UUID, BoardColumn], ordered_ids: list[uuid.UUID]
) -> None:
    """One UPDATE per row, all inside the caller's transaction. Safe against the
    deferrable unique constraint colliding mid-transaction because the constraint
    is DEFERRABLE INITIALLY DEFERRED — Postgres only checks uniqueness at COMMIT,
    so it does not matter that row 2's new value might momentarily equal row 5's
    old value."""
    for index, column_id in enumerate(ordered_ids):
        columns_by_id[column_id].position = float(index)
    await session.flush()
```

`get_max_position` y el cálculo de `position = (max or 0.0) + GAP` para altas viven en
`services/columns.py` (regla de negocio, no una consulta más).

### Servicio (`services/columns.py`)

```python
"""Column rules. Any board member manages columns — unlike board-level admin
(renaming/deleting the board, membership) which TASK-04 reserves to the owner.
Nothing here branches on actor.kind (CLAUDE.md §0)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import NotFoundError, ValidationError
from kanbai.models.actor import Actor
from kanbai.models.board_column import BoardColumn
from kanbai.repositories import columns as columns_repository
from kanbai.services import boards as boards_service

_COLUMN_NOT_FOUND_MESSAGE = "La columna solicitada no existe."
_DEFAULT_COLUMNS = ("Por hacer", "En curso", "Hecho")


async def seed_default_columns(session: AsyncSession, *, board_id: uuid.UUID) -> list[BoardColumn]:
    columns = []
    for index, name in enumerate(_DEFAULT_COLUMNS, start=1):
        columns.append(
            await columns_repository.create_column(
                session,
                board_id=board_id,
                name=name,
                wip_limit=None,
                position=index * columns_repository.GAP,
            )
        )
    return columns


async def list_columns(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[BoardColumn], int]:
    await boards_service.get_board(session, actor=actor, board_id=board_id)  # 404 si ajeno
    return await columns_repository.list_columns_for_board(
        session, board_id, actor.id, limit=limit, offset=offset
    )


async def create_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, name: str, wip_limit: int | None
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    current_max = await columns_repository.get_max_position(session, board_id)
    position = (current_max or 0.0) + columns_repository.GAP
    column = await columns_repository.create_column(
        session, board_id=board_id, name=name, wip_limit=wip_limit, position=position
    )
    await session.commit()
    return column


async def _get_column_or_404(
    session: AsyncSession, *, board_id: uuid.UUID, column_id: uuid.UUID
) -> BoardColumn:
    column = await columns_repository.get_column_by_id(session, board_id, column_id)
    if column is None:
        raise NotFoundError(_COLUMN_NOT_FOUND_MESSAGE)
    return column


async def get_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_id: uuid.UUID
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    return await _get_column_or_404(session, board_id=board_id, column_id=column_id)


async def update_column(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    name: str,
    wip_limit: int | None,
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    column = await _get_column_or_404(session, board_id=board_id, column_id=column_id)
    column = await columns_repository.update_column(session, column, name=name, wip_limit=wip_limit)
    await session.commit()
    return column


async def delete_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_id: uuid.UUID
) -> None:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    column = await _get_column_or_404(session, board_id=board_id, column_id=column_id)
    # TASK-06 adds the check here: if the column has cards, raise
    # ConflictError("No se puede borrar una columna con tarjetas."). No cards model
    # exists yet, so there is nothing to query — this comment is the contract TASK-06
    # must honor when it adds `Card`.
    await columns_repository.delete_column(session, column)
    await session.commit()


async def reorder_columns(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_ids: list[uuid.UUID]
) -> list[BoardColumn]:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    existing = await columns_repository.list_all_columns_for_board(session, board_id, actor.id)
    existing_ids = {column.id for column in existing}
    if len(column_ids) != len(set(column_ids)) or set(column_ids) != existing_ids:
        raise ValidationError(
            "La lista debe incluir, sin repetidos, exactamente las columnas actuales del tablero."
        )
    columns_by_id = {column.id: column for column in existing}
    await columns_repository.set_positions(session, columns_by_id, column_ids)
    await session.commit()
    return [columns_by_id[column_id] for column_id in column_ids]
```

`services/boards.py::create_board` cambia a:

```python
from kanbai.services import columns as columns_service

async def create_board(session: AsyncSession, *, actor: Actor, name: str) -> tuple[Board, str]:
    board = await boards_repository.create_board(session, name=name)
    await board_members_repository.add_member(session, board_id=board.id, actor_id=actor.id, role=OWNER)
    await columns_service.seed_default_columns(session, board_id=board.id)
    await session.commit()
    return board, OWNER
```

### Router (`api/routers/columns.py`)

```
GET    /api/v1/boards/{board_id}/columns          ?page,size  → 200 Page[ColumnRead] / 404
POST   /api/v1/boards/{board_id}/columns           ColumnCreate → 201 ColumnRead / 404 / 422
GET    /api/v1/boards/{board_id}/columns/{id}                  → 200 ColumnRead / 404
PATCH  /api/v1/boards/{board_id}/columns/{id}      ColumnUpdate → 200 ColumnRead / 404 / 422
DELETE /api/v1/boards/{board_id}/columns/{id}                  → 204 / 404 (/ 409 desde TASK-06)
PUT    /api/v1/boards/{board_id}/columns/reorder   ColumnReorder → 200 list[ColumnRead] / 404 / 422
```

`APIRouter(prefix="/boards/{board_id}/columns", tags=["columns"])`, registrado en
`api/router.py` junto a `boards.router`. La ruta `/reorder` se declara **antes** que
`/{column_id}` en el archivo — aunque FastAPI no las confundiría (los métodos no
coinciden: `PUT` en una, no en la otra), mantiene la intención explícita en el
código. `PUT` para reordenar (no `POST`/`PATCH`): sustituye el orden completo, es
idempotente — llamarlo dos veces con el mismo cuerpo dej a el mismo resultado, la
semántica exacta de `PUT`.

Todas las rutas dependen de `CurrentActor` y `SessionDep`; ninguna comprueba rol
(cualquier miembro puede operar, ver más arriba). El router no compone SQL, solo
llama a `services.columns` y traduce a `ColumnRead` vía
`ColumnRead.model_validate(column)`.

`reorder_columns` no se envuelve en `Page[...]`: es la respuesta de una acción sobre
el conjunto completo que el cliente ya envió, no un listado filtrable — un
`list[ColumnRead]` plano es más honesto sobre lo que es.

## Contrato API

| Método | Ruta | Request | Response |
|--------|------|---------|----------|
| GET | `/api/v1/boards/{board_id}/columns` | query `page`, `size` | `200 Page[ColumnRead]` / `404` |
| POST | `/api/v1/boards/{board_id}/columns` | `ColumnCreate` | `201 ColumnRead` / `404` / `422` |
| GET | `/api/v1/boards/{board_id}/columns/{column_id}` | — | `200 ColumnRead` / `404` |
| PATCH | `/api/v1/boards/{board_id}/columns/{column_id}` | `ColumnUpdate` | `200 ColumnRead` / `404` / `422` |
| DELETE | `/api/v1/boards/{board_id}/columns/{column_id}` | — | `204` / `404` |
| PUT | `/api/v1/boards/{board_id}/columns/reorder` | `ColumnReorder` | `200 list[ColumnRead]` / `404` / `422` |

## Casos límite y errores

- Tablero ajeno (no soy miembro) en cualquier ruta → `404`, igual que TASK-04.
- Columna de otro tablero (`column_id` real pero de otro `board_id`) → `404`
  (`get_column_by_id` filtra por `board_id`, así que no aparece).
- `name` vacío o > 100 caracteres → `422`.
- `wip_limit` ≤ 0 → `422` (`Field(gt=0)`).
- `PUT .../reorder` con una lista que no es exactamente el conjunto de columnas
  actuales del tablero (falta alguna, sobra alguna, o repite un id) → `422`
  (`ValidationError`).
- `PUT .../reorder` con `column_ids: []` en un tablero sin columnas → `200 []`,
  caso trivial válido (no hay nada que reordenar).
- Reordenar N columnas deja posiciones `0.0 .. N-1` sin huecos ni repetidos —
  comprobado leyendo `position` de la respuesta, no solo el orden de `items`.
- Borrar una columna vacía → `204`. Borrar una con tarjetas: bloqueado con `409`
  desde TASK-06 (ver "Decisiones abiertas cerradas" arriba); no hay test aquí porque
  no hay manera de crear una tarjeta todavía.
- Crear un tablero siembra siempre exactamente 3 columnas en el orden fijo.
- `page`/`size` fuera de rango → `422` (mismo `PaginationDep` que TASK-04).
- Sin sesión → `401` (sin cambios, `CurrentActor`).

## Plan de tests

`backend/tests/test_columns.py`, mismo estilo que `test_boards.py` (nombres en
español, fixtures de actor vía `services.auth.create_person`, sesión por cookie):

- `test_crear_tablero_siembra_tres_columnas_por_defecto`
- `test_crear_columna_como_owner`
- `test_crear_columna_como_member_no_owner_funciona_igual` (demuestra que no hay
  gating por rol)
- `test_crear_columna_en_tablero_ajeno_devuelve_404`
- `test_crear_columna_nombre_vacio_devuelve_422`
- `test_crear_columna_wip_limit_no_positivo_devuelve_422`
- `test_listar_columnas_devuelve_orden_por_posicion`
- `test_listar_columnas_tablero_ajeno_devuelve_404`
- `test_obtener_columna_ajena_devuelve_404`
- `test_renombrar_columna`
- `test_renombrar_columna_ajena_devuelve_404`
- `test_borrar_columna_vacia`
- `test_borrar_columna_ajena_devuelve_404`
- `test_reordenar_columnas_deja_orden_sin_huecos_ni_repetidos` — crea N (≥4)
  columnas, las reordena en un orden distinto al de creación, comprueba que la
  respuesta trae exactamente esas N columnas en el nuevo orden **y** que sus
  `position` son `0.0, 1.0, …, N-1` sin duplicados (`len(set(positions)) == N`).
- `test_reordenar_columnas_con_id_repetido_devuelve_422`
- `test_reordenar_columnas_con_id_ajeno_devuelve_422`
- `test_reordenar_columnas_tablero_ajeno_devuelve_404`

Cubre camino feliz, validación, acceso ajeno (404) y la propiedad de reordenación que
pide el criterio de aceptación.

## Dependencias nuevas

Ninguna. `Float`/`UniqueConstraint(deferrable=...)` son parte de SQLAlchemy 2.0, ya
en el proyecto.

## Desviaciones respecto al plan

Ninguna de fondo. El plan ya fijaba float + constraint aplazable, tres columnas fijas
al crear tablero, y "bloquear con 409" para borrar con tarjetas; esta spec concreta
firmas, DDL exacto y el plan de tests.

Un ajuste detectado durante la implementación, no anticipado en la spec original:

- **Import circular entre `services/boards.py` y `services/columns.py`.**
  `services/columns.py` importa `services/boards.py` (reutiliza `get_board` para el
  404 de tablero ajeno, en cada una de sus funciones); `services/boards.py` necesita
  `services/columns.py::seed_default_columns` al crear un tablero. Un `import` a
  nivel de módulo en ambos lados es circular. Solución: el `import` de
  `kanbai.services.columns` dentro de `services/boards.py::create_board` se difiere
  al cuerpo de la función (no a nivel de módulo) — para cuando se ejecuta, ambos
  módulos ya están completamente inicializados. No cambia ningún comportamiento ni
  contrato, solo el punto donde se resuelve el import.

Cinco ajustes más, todos detectados en una code review posterior a la primera
implementación verde (`uv run poe check` en verde no los atrapó — son de
concurrencia, autorización en profundidad y semántica HTTP, no de tipos ni de los
tests que existían entonces):

- **Alta concurrente de columnas colisionaba en el `COMMIT`.** Dos `POST
  .../columns` a la vez sobre el mismo tablero podían leer el mismo
  `MAX(position)`, calcular el mismo valor y chocar contra el `UNIQUE` aplazado al
  hacer `commit()` — el segundo request recibía un `IntegrityError` sin traducir
  (500 opaco), no un error de dominio. Corregido con
  `repositories/boards.py::lock_board_for_update` (`SELECT ... FOR UPDATE` sobre la
  fila del tablero), llamado en `create_column` y `reorder_columns` antes de leer o
  escribir ninguna posición — serializa las dos peticiones en vez de dejarlas
  competir. Test de regresión:
  `test_crear_columnas_concurrentes_en_el_mismo_tablero_no_colisiona` (usa sesiones
  y conexiones reales e independientes, no la `db_session` compartida de
  `conftest.py`, porque esa fixture no puede demostrar concurrencia real).
- **La reordenación colapsaba las posiciones a `0.0, 1.0, 2.0, …`.** Cumplía la
  letra de "sin huecos ni repetidos" pero destruía el hueco de `GAP` entre vecinas
  que el esquema de posiciones existe para preservar (el motivo de ser de todo el
  diseño, ver más arriba). Corregido: `set_positions` ahora asigna
  `float(index) * GAP` (`0.0, 1024.0, 2048.0, …`) — sigue siendo "una columna por
  rango sucesivo, sin huecos ni duplicados en el rango", pero conserva sitio para
  insertar entre dos columnas más adelante.
- **`ColumnUpdate` de reemplazo completo servido por `PATCH` invitaba a perder
  datos.** Un cliente que solo quisiera renombrar mandaría un `PATCH` con solo
  `name` — un payload de `PATCH` completamente natural — y `wip_limit` se ponía a
  `None` en silencio. El precedente citado (`BoardUpdate`) no cubre este caso
  porque tiene un único campo, nada que perder al omitirlo. Corregido cambiando el
  endpoint de `PATCH` a `PUT`: el verbo deja explícito que hay que enviar el estado
  completo, sin necesitar un tipo centinela para distinguir "campo no enviado" de
  "campo puesto a `null`".
- **`get_column_by_id` no filtraba por pertenencia en la propia consulta.**
  Contradecía tanto CLAUDE.md §4 ("todo recurso se filtra por su dueño en la
  consulta, no después en Python") como el propio docstring de
  `list_columns_for_board` en el mismo archivo, que afirmaba que todas las
  consultas del módulo lo hacían. Era seguro hoy porque los cuatro servicios que la
  llaman comprueban membresía antes vía `boards_service.get_board`, pero esa
  garantía vivía en una convención de quien llama, no en la consulta — y era la
  función que TASK-06 más probablemente copiaría al mover tarjetas entre columnas.
  Corregido añadiendo el mismo filtro `board_ids_for_actor` que ya usaban las otras
  consultas del archivo.
- **Borrar todas las columnas de un tablero, una a una, no estaba bloqueado.** El
  tablero quedaba sin ningún sitio donde vivir una tarjeta y nada lo resiembra
  (`seed_default_columns` solo corre al crear el tablero). Corregido con el mismo
  patrón que "no puedes quitar al único owner" (TASK-04): bloquear con `409` al
  intentar borrar la última columna que queda.

También se añadió un test que no corrige un bug sino que demuestra que el propio
mecanismo central de la tarea es real y no solo declarado:
`test_constraint_de_posicion_se_aplaza_pero_se_comprueba_en_commit_real` abre su
propia conexión y hace un `COMMIT` de verdad (el resto de la suite corre dentro de
un `SAVEPOINT` que siempre se revierte, así que nunca llega a un `COMMIT` real) para
comprobar que el `UNIQUE ... DEFERRABLE INITIALLY DEFERRED` efectivamente rechaza
dos columnas con la misma posición al comprometerse la transacción.
