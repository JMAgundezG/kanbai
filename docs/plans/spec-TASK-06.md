# Spec · TASK-06 · Tarjetas: CRUD y movimiento

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-06](plan-TASK-06.md) · **Tarea:** [TASK-06](../tasks/TASK-06-tarjetas.md)

## El movimiento atómico (decisión central de la tarea)

Mover una tarjeta significa escribir, en una sola operación, su nueva `column_id` y su
nueva `position`. Los dos invariantes que eso pone en riesgo son **por columna**:

- `UNIQUE (column_id, position)` — no puede haber dos tarjetas en la misma posición
  de la misma columna.
- `wip_limit` de la columna de destino — no pueden entrar más tarjetas de las que
  permite.

Por eso la serialización se hace **bloqueando la fila de la columna de destino**, no
la del tablero:

```python
# repositories/columns.py
async def lock_column_for_update(
    session: AsyncSession, column_id: uuid.UUID
) -> BoardColumn | None:
    result = await session.execute(
        select(BoardColumn)
        .where(BoardColumn.id == column_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
```

Devuelve la columna **tal como queda una vez tomado el bloqueo** (`populate_existing`
refresca lo que el llamante hubiera leído antes de esperar), no solo el bloqueo: el
`wip_limit` que se aplica es el vigente después de esperar, no el que se leyó antes. Y
`None` si otra transacción la borró mientras tanto, que el servicio convierte en `404`
en lugar de dejarlo llegar a una violación de clave ajena.

`services/cards.py` toma ese bloqueo **antes** de leer nada de la columna de destino
(ni el recuento para el WIP ni las posiciones vecinas) y lo mantiene hasta el
`commit()`. En `READ COMMITTED` —el nivel por defecto— cada sentencia toma una
instantánea nueva, así que la transacción que quedó esperando en el `FOR UPDATE`
vuelve a leer **el estado ya comprometido** por la que iba delante: cuenta las
tarjetas que la otra acaba de meter y ve las posiciones que la otra acaba de escribir.
No hay lectura-en-Python-y-escritura-después: la lectura ocurre dentro de una sección
crítica que impone la base de datos.

Por qué la columna y no el tablero (que es lo que hace TASK-05 al crear/reordenar
columnas, con `repositories/boards.py::lock_board_for_update`): bloquear el tablero
serializaría también los movimientos hacia columnas **distintas**, que no comparten
ninguno de los dos invariantes. En un tablero donde varios agentes trabajan a la vez
—el caso de uso del producto— eso es contención inventada. El bloqueo de columna es
el grano exacto del invariante.

**Orden global de adquisición de bloqueos: columna → tarjeta, y como mucho una columna
por transacción.** Ninguna operación de esta tarea toma dos bloqueos de columna, y
ninguna toma el de la tarjeta antes que el de la columna, así que no hay ciclo posible
y no hay interbloqueos. Queda escrito aquí y en un comentario del servicio porque es
una propiedad global, no local a una función.

El bloqueo de la tarjeta (`lock_card_for_update`) se toma después del de la columna y
devuelve la tarjeta ya refrescada (`populate_existing`), no un simple booleano. Sirve
para tres cosas: que dos movimientos de **la misma tarjeta** no se pisen a mitad de
escritura; que el servicio decida sobre la columna en la que la tarjeta está *ahora* y
no sobre la que leyó al autorizar la petición (de eso depende si toca comprobar el WIP);
y que un borrado concurrente se resuelva como `404` limpio en lugar de un
`StaleDataError` (500) al hacer `flush()` de un `UPDATE` que no afecta a ninguna fila.

El movimiento en sí sigue siendo **un `UPDATE` de una sola fila**: se reescribe la
tarjeta que se mueve y ninguna otra. Esa es la propiedad por la que TASK-05 eligió
posiciones `float` con hueco (`GAP`) en vez de reindexado entero, y esta tarea la
hereda tal cual.

## Decisiones abiertas cerradas

### 1. Cómo se expresa la posición de destino: índice entero, ajustado al tamaño real

`CardMove` lleva `column_id` (destino) y `position: int` (índice de destino dentro de
esa columna, base 0), no `after_card_id`. Razones:

- Es lo que una interfaz de arrastrar y soltar (TASK-08) tiene a mano: el hueco entre
  dos tarjetas donde se suelta es un índice de la lista que está pintando.
- El cliente no necesita conocer los ids de las vecinas, y el servidor no necesita
  confiar en que sigan siendo vecinas: **el servidor recalcula las vecinas** leyendo
  la columna de destino ya bloqueada.

`position` es un **índice deseado**, y se ajusta (`clamp`) al rango real
`[0, N]` —siendo `N` el número de tarjetas de la columna de destino sin contar la que
se mueve— en el momento de ejecutar el movimiento. Un índice mayor deja la tarjeta al
final. No devuelve `422`: la vista del cliente puede estar legítimamente desfasada
(alguien acaba de borrar dos tarjetas de esa columna) y un `422` obligaría a recargar
por algo que tiene una respuesta obvia y correcta. Un índice **negativo** sí es `422`,
porque no es una vista desfasada sino una petición mal formada (`Field(ge=0)`, lo
rechaza Pydantic antes de llegar al servicio).

Cálculo de la posición real, con las posiciones de la columna de destino ya leídas en
orden y **excluyendo la tarjeta que se mueve** (importante: mover dentro de la misma
columna no debe tomarse a sí misma como vecina):

| Caso | `position` resultante |
|------|----------------------|
| Columna de destino vacía | `GAP` |
| Índice 0 (al principio) | `primera - GAP` |
| Índice `N` (al final) | `última + GAP` |
| Entre dos vecinas | `(anterior + siguiente) / 2` |

`GAP` se **importa** de `repositories/columns.py` (`from kanbai.repositories.columns
import GAP`), no se redefine: TASK-05 dejó esa constante con el comentario de que
TASK-06 reutiliza ese mismo valor, y reutilizarla de verdad evita que las dos se
separen. Las posiciones negativas (insertar repetidamente al principio) son
inofensivas: `position` no significa nada fuera del orden relativo.

### 2. Verbo del movimiento: `POST /cards/{card_id}/move`

No va en el `PUT` de edición (`CardUpdate` solo lleva `title` y `description`): mezclar
"renombrar" y "mover" en el mismo cuerpo obligaría a resolver un movimiento en cada
edición de texto y haría imposible aplicar el bloqueo de columna solo cuando hace
falta.

`POST` y no `PUT` —a diferencia de `PUT .../columns/reorder` de TASK-05— porque el
cuerpo **no es el estado final del recurso**: es una intención relativa
("ponla en esta columna, en este hueco") que se resuelve contra el estado vivo de la
columna en el instante de ejecutarla. Repetir la misma llamada dos veces puede dar
posiciones distintas (aunque la colocación lógica sea la misma), así que la
idempotencia que `PUT` promete no se cumple. `reorder` sí manda el estado completo y
por eso allí `PUT` es correcto.

Devuelve `200 CardRead` con la tarjeta ya movida: el cliente necesita la `position`
real que el servidor calculó, que casi nunca es el índice que mandó.

### 3. El límite WIP se aplica también al crear

La tarea solo lo pide al mover ("aplicación del límite WIP de la columna destino"),
pero un límite que se puede saltar creando la tarjeta directamente en la columna llena
no es un límite. `create_card` hace exactamente la misma comprobación, bajo el mismo
bloqueo de columna, y devuelve el mismo `409` con el mismo mensaje.

La comprobación es `if wip_limit is not None and count >= wip_limit` y **solo se hace
cuando la columna de destino es distinta de la actual**: reordenar una tarjeta dentro
de su propia columna ya llena tiene que seguir funcionando (la tarjeta ya está
contada; bloquearlo dejaría una columna en su límite congelada, sin poder ni
reordenarse).

Mensaje, en español y sin filtrar nada interno:
`No se pueden añadir más tarjetas a «<nombre>»: ha alcanzado su límite de <N> tarjetas.`
Se sirve como `409 Conflict` (`ConflictError`, ya existente): el estado del recurso
choca con la operación, no es un problema de forma del cuerpo (que sería `422`).

### 4. Claves ajenas y borrados

| FK | `ON DELETE` | Por qué |
|----|-------------|---------|
| `board_id → boards.id` | `CASCADE` | Borrar un tablero se lleva todo lo suyo, igual que `board_columns` y `board_members`. |
| `column_id → board_columns.id` | `CASCADE` | Necesario para que el `CASCADE` del tablero funcione sin chocar: al borrar un tablero, PostgreSQL borra sus columnas, y esas columnas no pueden quedar bloqueadas por tarjetas. El borrado *directo* de una columna con tarjetas lo impide la regla de negocio (`409`), no la base de datos. |
| `created_by_actor_id → actors.id` | `RESTRICT` | La atribución es una invariante del dominio (CLAUDE.md § 0: toda escritura queda atribuida a un actor). Borrar el actor no puede ni borrar su trabajo ni dejarlo sin firma; si algún día hay que dar de baja a un actor, será una operación explícita que decida qué pasa con su rastro, no un `CASCADE` silencioso. |

`Card.board_id` es redundante con `column.board_id`, y se guarda a propósito: el
listado por tablero y el filtro de pertenencia no necesitan un `JOIN` extra, y la
tarjeta cuelga del tablero aunque su columna cambie. La coherencia entre ambos la
garantiza el servicio: la columna de destino se resuelve **siempre** con
`columns_repository.get_column_by_id(session, board_id, column_id, actor_id)`, que
filtra por `board_id`, así que nunca se puede apuntar a una columna de otro tablero
(devuelve `404`). La alternativa —FK compuesta `(board_id, column_id) →
board_columns(board_id, id)`— exigiría añadir un índice único nuevo a `board_columns`
(tabla de otra tarea) y es de las cosas que Alembic peor autogenera; se descarta por
coste/beneficio y queda anotada aquí.

### 5. Recompactación cuando se agota la precisión del `float`

Insertar repetidamente entre las mismas dos vecinas divide el hueco a la mitad cada
vez. Con `GAP = 1024.0` hacen falta decenas de inserciones seguidas en el mismo hueco
para agotar la mantisa de un `double`, pero cuando ocurre el punto medio deja de estar
estrictamente entre las vecinas y se produciría una posición duplicada — precisamente
lo que el criterio de aceptación prohíbe.

Se cierra con una comprobación explícita: si el punto medio calculado **no queda
estrictamente entre las dos vecinas**, se recompacta la columna entera
(`renumber_column`: `0, GAP, 2*GAP, …` en el orden actual) dentro de la **misma
transacción, con la columna ya bloqueada**, y se recalcula la posición sobre las
posiciones nuevas. La reescritura de varias filas a la vez es segura precisamente
porque el `UNIQUE` es `DEFERRABLE INITIALLY DEFERRED`: PostgreSQL comprueba la
unicidad al `COMMIT`, no sentencia a sentencia. Es el mismo argumento que
`repositories/columns.py::set_positions` documenta para la reordenación de columnas.

## Backend (`backend/src/kanbai/`)

### Modelo (`models/card.py`)

```python
"""A card: the unit of work on a board. Lives in a column, keeps its own position
inside that column, and records which actor created it.

`position` reuses TASK-05's scheme unchanged: float with a deferrable unique
constraint per column (see docs/plans/spec-TASK-05.md for why float instead of
integer reindexing), and the same GAP.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("board_columns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    # RESTRICT, not CASCADE: attribution is a domain invariant (CLAUDE.md § 0) and
    # deleting an actor must not silently delete or unsign their work.
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "column_id", "position",
            name="uq_cards_column_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
```

`models/__init__.py` añade `Card` a los imports y a `__all__`.

### Migración

`uv run alembic revision --autogenerate -m "add cards"` debe generar:

- `CREATE TABLE cards (id UUID PK, board_id UUID NOT NULL FK→boards.id ON DELETE
  CASCADE, column_id UUID NOT NULL FK→board_columns.id ON DELETE CASCADE, title
  VARCHAR(200) NOT NULL, description TEXT NULL, position DOUBLE PRECISION NOT NULL,
  created_by_actor_id UUID NOT NULL FK→actors.id ON DELETE RESTRICT, created_at
  TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())`
- Índices `ix_cards_board_id`, `ix_cards_column_id`, `ix_cards_created_by_actor_id`.
- `uq_cards_column_id_position` — **revisar a mano que lleva `deferrable=True,
  initially='DEFERRED'`**; si el autogenerate lo omite, se añade a mano antes de
  aplicar. Es el motivo de ser del esquema, no es opcional.

Tras `uv run poe migrate`, un `--autogenerate` de comprobación debe salir vacío; esa
revisión se borra.

### Schemas (`schemas/card.py`)

```python
class CardCreate(BaseModel):
    column_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CardUpdate(BaseModel):
    # Full replace over PUT, same reasoning as ColumnUpdate (TASK-05): every field
    # is required, so a client cannot silently null out what it did not send.
    # Moving is deliberately NOT here — it is POST .../move.
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CardMove(BaseModel):
    column_id: uuid.UUID
    # Desired 0-based index inside the destination column; the server clamps it to
    # the column's real size at execution time (see spec §1).
    position: int = Field(ge=0)


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: str | None
    position: float
    created_by_actor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

`CardRead` lleva `created_by_actor_id` como UUID, no un `ActorRead` embebido: un
listado de 100 tarjetas con el actor embebido obliga a cargar el actor de cada una, y
ningún consumidor de esta tarea lo necesita. TASK-15 (detalle de tarjeta) puede
embeberlo cuando de verdad haga falta.

### Repositorio (`repositories/cards.py`)

Únicas consultas SQL sobre `cards`. Todas las que exponen datos filtran pertenencia en
SQL con `board_ids_for_actor` (CLAUDE.md § 4), igual que `repositories/columns.py`:

```python
GAP importado de kanbai.repositories.columns

async def list_cards_for_board(session, board_id, actor_id, *, column_id: uuid.UUID | None,
                               limit: int, offset: int) -> tuple[list[Card], int]
    # JOIN a board_columns para ordenar por (posición de la columna, posición de la
    # tarjeta): el orden natural del tablero. Filtro opcional por column_id.

async def get_card_by_id(session, board_id, card_id, actor_id) -> Card | None
async def create_card(session, *, board_id, column_id, title, description, position,
                      created_by_actor_id) -> Card
async def update_card(session, card, *, title, description) -> Card
async def delete_card(session, card) -> None
async def set_placement(session, card, *, column_id, position) -> Card   # el UPDATE del movimiento
async def count_cards_in_column(session, column_id) -> int               # WIP y el 409 de columnas
async def lock_card_for_update(session, card_id) -> Card | None          # FOR UPDATE + refresco
async def list_positions_in_column(session, column_id, *, exclude_card_id) -> list[float]
async def renumber_column(session, column_id) -> list[float]             # recompactación (§5)
```

`count_cards_in_column` y `list_positions_in_column` no llevan filtro de pertenencia:
no exponen datos (devuelven un entero y una lista de flotantes anónimos) y sus dos
llamantes ya han resuelto la pertenencia contra la columna antes de invocarlas. Queda
dicho en el docstring de cada una.

### Servicio (`services/cards.py`)

```python
async def list_cards(session, *, actor, board_id, column_id, limit, offset)
async def create_card(session, *, actor, board_id, column_id, title, description) -> Card
async def get_card(session, *, actor, board_id, card_id) -> Card
async def update_card(session, *, actor, board_id, card_id, title, description) -> Card
async def delete_card(session, *, actor, board_id, card_id) -> None
async def move_card(session, *, actor, board_id, card_id, column_id, position) -> Card
```

Ninguna función ramifica por `actor.kind` (CLAUDE.md § 0): el creador se registra con
`created_by_actor_id=actor.id`, que vale igual para una persona que para un agente.

`move_card`, paso a paso:

1. `boards_service.get_board(...)` → `404` si no soy miembro del tablero.
2. `_get_card_or_404(...)` → `404` si la tarjeta no existe o no es de un tablero mío
   (el filtro va en la consulta).
3. `columns_repository.get_column_by_id(session, board_id, column_id, actor.id)` →
   `404` "La columna de destino no existe." si no existe o es de otro tablero.
4. **`columns_repository.lock_column_for_update(session, column_id)`** — a partir de
   aquí todo lo que se lee de esa columna es fresco y nadie más puede tocarla.
5. `cards_repository.lock_card_for_update(session, card_id)` → `404` si otra
   transacción la borró mientras tanto; devuelve la tarjeta ya refrescada, y es esa
   —no la leída en el paso 2— la que se usa a partir de aquí.
6. Si `column_id != card.column_id` y la columna tiene `wip_limit`: contar y, si
   `count >= wip_limit`, `ConflictError` (`409`).
7. Calcular la posición (tabla del §1), recompactando si el punto medio no cabe (§5).
8. `set_placement(card, column_id, position)` + `commit()`.

`create_card` sigue el mismo esqueleto sin el paso 5 (no hay tarjeta todavía) y con la
posición siempre al final (`máximo + GAP`).

### Cambio en `services/columns.py`

Cierra el pendiente que TASK-05 dejó marcado con un comentario en `delete_column`:

```python
await columns_repository.lock_column_for_update(session, column_id)
if await cards_repository.count_cards_in_column(session, column_id) > 0:
    raise ConflictError("No se puede borrar una columna con tarjetas.")
```

El bloqueo va **antes** de contar: sin él, una tarjeta creada a la vez entraría entre
el recuento y el `DELETE`, y el `ON DELETE CASCADE` de `cards.column_id` la borraría
en silencio. Con él, crear una tarjeta y borrar su columna se serializan.

### Router (`api/routers/cards.py`)

`APIRouter(prefix="/boards/{board_id}/cards", tags=["cards"])`, registrado en
`api/router.py`. Ninguna ruta comprueba rol: cualquier miembro del tablero gestiona
tarjetas, igual que las columnas en TASK-05. El router no compone SQL: llama a
`services.cards` y traduce con `CardRead.model_validate(card)`.

## Contrato API

| Método | Ruta | Request | Response |
|--------|------|---------|----------|
| GET | `/api/v1/boards/{board_id}/cards` | query `column_id?`, `page`, `size` | `200 Page[CardRead]` / `404` |
| POST | `/api/v1/boards/{board_id}/cards` | `CardCreate` | `201 CardRead` / `404` / `409` / `422` |
| GET | `/api/v1/boards/{board_id}/cards/{card_id}` | — | `200 CardRead` / `404` |
| PUT | `/api/v1/boards/{board_id}/cards/{card_id}` | `CardUpdate` | `200 CardRead` / `404` / `422` |
| DELETE | `/api/v1/boards/{board_id}/cards/{card_id}` | — | `204` / `404` |
| POST | `/api/v1/boards/{board_id}/cards/{card_id}/move` | `CardMove` | `200 CardRead` / `404` / `409` / `422` |

`DELETE /api/v1/boards/{board_id}/columns/{column_id}` gana un `409` real ("No se
puede borrar una columna con tarjetas"), que hasta ahora solo estaba documentado.

El listado va ordenado por `(posición de la columna, posición de la tarjeta)`: el orden
en que se pinta el tablero, no un orden arbitrario.

## Frontend (`frontend/src/`)

No se toca. Ningún módulo de `frontend/` consume todavía `/boards` (el primero será
TASK-08), así que `frontend/src/api/schema.d.ts` no se regenera — mismo criterio
explícito de TASK-04 y TASK-05. Lo que sí se regenera es `backend/openapi.json`
(`uv run poe openapi`), que es el contrato commiteado y del que TASK-08 generará los
tipos.

## Casos límite y errores

- Tablero ajeno en cualquier ruta → `404`.
- Tarjeta de otro tablero (`card_id` real, `board_id` mío) → `404`.
- Columna de destino de otro tablero → `404`, sin confirmar que existe.
- `title` vacío o > 200 → `422`; `description` > 5000 → `422`.
- `position` negativa en el movimiento → `422`; `position` mayor que el tamaño de la
  columna → se ajusta al final, `200`.
- Mover una tarjeta a su misma columna y su misma posición → `200`, sin cambio
  observable de orden.
- Mover dentro de la misma columna con el WIP lleno → `200` (la tarjeta ya está
  contada).
- Crear o mover hacia una columna con el WIP alcanzado → `409` en español.
- Borrar una columna con tarjetas → `409`.
- Sin sesión → `401`.
- `page`/`size` fuera de rango → `422` (mismo `PaginationDep`).

## Plan de tests

`backend/tests/test_cards.py`, mismo estilo que `test_columns.py` (nombres en español,
fixtures de actor vía `services.auth.create_person`, sesión por cookie):

Creación, edición, borrado y permisos:
- `test_crear_tarjeta_registra_al_actor_creador`
- `test_crear_tarjeta_en_columna_de_otro_tablero_devuelve_404`
- `test_crear_tarjeta_en_tablero_ajeno_devuelve_404`
- `test_crear_tarjeta_titulo_vacio_devuelve_422`
- `test_listar_tarjetas_ordenadas_por_columna_y_posicion`
- `test_listar_tarjetas_filtrando_por_columna`
- `test_listar_tarjetas_tablero_ajeno_devuelve_404`
- `test_obtener_tarjeta_ajena_devuelve_404`
- `test_editar_tarjeta` · `test_editar_tarjeta_ajena_devuelve_404`
- `test_borrar_tarjeta` · `test_borrar_tarjeta_ajena_devuelve_404`

Movimiento:
- `test_mover_tarjeta_a_otra_columna_y_posicion_persiste` — comprueba el orden al
  releer, no solo la respuesta.
- `test_mover_tarjeta_dentro_de_la_misma_columna_reordena`
- `test_mover_tarjeta_con_indice_mayor_que_la_columna_la_deja_al_final`
- `test_mover_tarjeta_con_posicion_negativa_devuelve_422`
- `test_mover_tarjeta_a_columna_de_otro_tablero_devuelve_404`
- `test_mover_tarjeta_ajena_devuelve_404`
- `test_mover_tarjeta_entre_vecinas_sin_hueco_recompacta_la_columna` — pone dos
  vecinas en posiciones flotantes consecutivas (`math.nextafter`) y comprueba que el
  movimiento entre ellas deja posiciones distintas y el orden pedido (§5).

Límite WIP:
- `test_mover_a_columna_con_wip_lleno_devuelve_409` — comprueba también el mensaje en
  español y que la tarjeta no se movió.
- `test_crear_en_columna_con_wip_lleno_devuelve_409`
- `test_mover_dentro_de_la_misma_columna_con_wip_lleno_funciona`

Concurrencia **real** (sesiones y conexiones independientes con `COMMIT` de verdad, la
técnica de `test_columns.py`; la suite normal corre dentro de un `SAVEPOINT` que
siempre se revierte, así que no puede demostrar concurrencia). Ambos limpian sus datos
al terminar (`DELETE FROM boards` —que arrastra columnas y tarjetas por `CASCADE`— y
después `DELETE FROM actors`, en ese orden porque `created_by_actor_id` es `RESTRICT`):

- `test_movimientos_concurrentes_a_la_misma_columna_no_duplican_ni_pierden_tarjetas` —
  cuatro tarjetas de una columna se mueven **a la vez** al índice 0 de la misma
  columna de destino. Comprueba que las cuatro llamadas terminan bien, que las cuatro
  tarjetas están en el destino, que hay cuatro posiciones **distintas** y que el total
  de tarjetas del tablero no ha cambiado (ninguna perdida ni duplicada).
- `test_movimientos_concurrentes_no_superan_el_limite_wip` — columna de destino con
  `wip_limit = 1` y vacía; dos movimientos simultáneos. Exactamente uno termina bien y
  exactamente uno recibe `ConflictError`; la columna acaba con **una** tarjeta.

Verificación adicional durante la implementación (no queda en la suite): quitar
temporalmente `lock_column_for_update` y comprobar que **los dos tests de concurrencia
fallan**. Un test de concurrencia que pasa igual con y sin el mecanismo que dice
proteger no demuestra nada, y se anota el resultado real en el informe.

`backend/tests/test_columns.py` añade:
- `test_borrar_columna_con_tarjetas_devuelve_409`

## Dependencias nuevas

Ninguna. `with_for_update()`, `Float`, `Text` y `UniqueConstraint(deferrable=...)` son
SQLAlchemy 2.0, ya en el proyecto; `math.nextafter` es de la biblioteca estándar.

## Desviaciones respecto al plan

Ninguna de fondo: el plan ya fijaba el bloqueo de la columna de destino como
mecanismo y dejaba cinco decisiones abiertas, que esta spec cierra. Los dos añadidos
que el plan no anticipaba son el bloqueo de la fila de la tarjeta (paso 5 de
`move_card`, para que un borrado concurrente sea `404` y no un 500) y la
recompactación por agotamiento de precisión (§5).
