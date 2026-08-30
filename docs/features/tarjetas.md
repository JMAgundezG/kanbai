# Tarjetas: CRUD y movimiento

**Introducida por:** [TASK-06](../tasks/TASK-06-tarjetas.md) · **Última actualización:** 2026-08-30

La **tarjeta** es la unidad de trabajo del tablero: vive en una columna, ocupa una
posición dentro de ella y recuerda qué actor la creó. Cualquier miembro del tablero
las crea, edita, mueve y borra, sin distinción de rol (igual que las columnas de
TASK-05, y a diferencia de la administración del tablero de TASK-04).

## Modelo

| Tabla | Columnas |
|-------|----------|
| `cards` | `id` (UUID), `board_id` (FK→`boards.id`, `ON DELETE CASCADE`), `column_id` (FK→`board_columns.id`, `ON DELETE CASCADE`), `title` (≤200), `description` (texto opcional), `position` (`DOUBLE PRECISION`), `created_by_actor_id` (FK→**`actors.id`**, `ON DELETE RESTRICT`), `created_at`, `updated_at` |

`created_by_actor_id` apunta a `actors`, nunca a `people`: es la invariante de
`CLAUDE.md` § 0 hecha esquema. El creador se toma del actor autenticado y ningún
servicio ni router mira `actor.kind` — un agente firmará sus tarjetas por este mismo
camino, sin tocar nada, el día que TASK-09 exista. La clave ajena es **`RESTRICT`** y
no `CASCADE` a propósito: borrar un actor no puede ni borrar su trabajo ni dejarlo sin
firma; si algún día hay que dar de baja a un actor, tendrá que ser una operación
explícita que decida qué pasa con su rastro.

`board_id` está denormalizado (la columna ya implica el tablero) para que el listado y
el filtro de pertenencia no necesiten un `JOIN` extra. La coherencia entre `board_id` y
`column_id` la garantiza el servicio: la columna de destino se resuelve **siempre** con
`columns_repository.get_column_by_id(board_id, ...)`, que filtra por tablero, así que
apuntar a una columna de otro tablero es imposible (devuelve `404`).

`updated_at` lo calcula la base de datos (`onupdate=func.now()`), y el modelo lleva
`__mapper_args__ = {"eager_defaults": True}` para que el `UPDATE` lo devuelva con
`RETURNING`: sin eso SQLAlchemy solo invalidaría el atributo y volvería a leerlo más
tarde, que es E/S perezosa y en async revienta con `MissingGreenlet` en cuanto el
router serializa la tarjeta.

## El esquema de posiciones: el mismo de TASK-05, reutilizado

`position` es un `float` con `UniqueConstraint(column_id, position)` **aplazable**
(`DEFERRABLE INITIALLY DEFERRED`), y `GAP` se **importa** de
`repositories/columns.py` en lugar de redefinirse, para que las dos tablas no puedan
separarse. Ver [columnas-de-tablero.md](columnas-de-tablero.md) para el porqué del
`float`.

Cómo se asigna:

| Caso | `position` |
|------|-----------|
| Crear una tarjeta | `máximo de la columna + GAP` (siempre al final) |
| Mover al índice 0 | `primera - GAP` |
| Mover al final | `última + GAP` |
| Mover entre dos vecinas | `(anterior + siguiente) / 2` |
| Columna de destino vacía | `GAP` |

Si el punto medio **no cae estrictamente entre las dos vecinas** —la precisión del
`float` se agota tras muchas inserciones seguidas en el mismo hueco— la columna se
recompacta entera (`0, GAP, 2·GAP, …`, sin alterar el orden) dentro de la misma
transacción y ya bloqueada, y la posición se recalcula sobre los valores nuevos.
Reescribir varias filas a la vez es seguro justo porque el `UNIQUE` es aplazado:
PostgreSQL solo comprueba unicidad al `COMMIT`.

## El movimiento atómico

```
POST /api/v1/boards/{board_id}/cards/{card_id}/move   {"column_id": ..., "position": 2}
```

Los dos invariantes que un movimiento puede romper son **de la columna de destino**:
la unicidad de `(column_id, position)` y su `wip_limit`. Por eso la serialización se
hace **bloqueando la fila de la columna de destino**
(`repositories/columns.py::lock_column_for_update`, `SELECT ... FOR UPDATE`) antes de
leer nada de ella, y manteniéndola hasta el `commit()`. Como PostgreSQL lee en
`READ COMMITTED`, la transacción que se quedó esperando vuelve a leer y ve lo que la
anterior ya comprometió: cuenta las tarjetas que la otra acaba de meter y las
posiciones que acaba de escribir. **No hay lectura en Python seguida de escritura**:
la lectura ocurre dentro de una sección crítica que impone la base de datos.

No se bloquea el tablero (lo que sí hace TASK-05 para asignar posiciones de
*columnas*): eso serializaría también los movimientos hacia columnas distintas del
mismo tablero, que no comparten ninguno de los dos invariantes. El grano del bloqueo
es el grano del invariante.

Después del bloqueo de la columna se toma el de la **tarjeta**
(`lock_card_for_update`), que además la devuelve refrescada: el servicio decide sobre
la columna en la que la tarjeta está *ahora*, no sobre la que leyó al autorizar la
petición, y un borrado concurrente sale como `404` limpio en lugar de un 500. El orden
de adquisición es global y único —**columna, luego tarjeta, y nunca dos columnas en la
misma transacción**—, que es lo que descarta los interbloqueos.

La escritura sigue siendo **un `UPDATE` de una sola fila**: se reescribe la tarjeta que
se mueve y ninguna otra.

`position` en el cuerpo es un **índice deseado** (base 0) dentro de la columna de
destino, no la posición flotante: es lo que una interfaz de arrastrar y soltar tiene a
mano, y el servidor recalcula las vecinas por su cuenta. Se ajusta al tamaño real de la
columna en el momento de ejecutarlo (un índice mayor deja la tarjeta al final), porque
la vista del cliente puede estar legítimamente desfasada; un índice negativo sí es
`422`. La respuesta trae la `position` real calculada por el servidor.

Está cubierto por dos tests de concurrencia **real** (`tests/test_cards.py`), con
conexiones y sesiones independientes que hacen `COMMIT` de verdad — la suite normal
corre dentro de un `SAVEPOINT` que siempre se revierte y no podría demostrar nada:

- cuatro tarjetas movidas a la vez al mismo hueco de la misma columna: ninguna falla,
  ninguna se pierde y no hay dos posiciones iguales;
- dos movimientos simultáneos hacia una columna con un solo hueco libre: entra uno y el
  otro se lleva el `409`.

Ambos se comprobaron quitando el bloqueo: sin él fallan con
`UniqueViolation` en `uq_cards_column_id_position` y con los dos movimientos colándose
por encima del límite.

## Límite de trabajo en curso (WIP)

Si la columna de destino tiene `wip_limit` y ya lo ha alcanzado, la operación se
rechaza con **`409 Conflict`**:

```
No se pueden añadir más tarjetas a «Nombre de la columna»: ha alcanzado su límite de N tarjetas.
```

Dos matices:

- **Se aplica también al crear**, no solo al mover: un límite que se esquiva creando la
  tarjeta directamente en la columna llena no es un límite.
- **No se aplica al reordenar dentro de la misma columna**: la tarjeta ya está contada,
  y bloquearlo dejaría congelada cualquier columna que esté en su límite.

La comprobación y la escritura ocurren bajo el mismo bloqueo de columna, así que dos
movimientos simultáneos no pueden colarse los dos en el último hueco.

## Endpoints

Todos bajo `/api/v1/boards/{board_id}/cards`; ser miembro del tablero es obligatorio
(`404` si no lo eres) y no se exige ningún rol concreto:

| Método | Ruta | Respuesta |
|--------|------|-----------|
| `GET` | `/api/v1/boards/{board_id}/cards` | `200 Page[CardRead]` / `404` |
| `POST` | `/api/v1/boards/{board_id}/cards` | `201 CardRead` / `404` / `409` / `422` |
| `GET` | `/api/v1/boards/{board_id}/cards/{card_id}` | `200 CardRead` / `404` |
| `PUT` | `/api/v1/boards/{board_id}/cards/{card_id}` | `200 CardRead` / `404` / `422` |
| `DELETE` | `/api/v1/boards/{board_id}/cards/{card_id}` | `204` / `404` |
| `POST` | `/api/v1/boards/{board_id}/cards/{card_id}/move` | `200 CardRead` / `404` / `409` / `422` |

El listado acepta `?column_id=<uuid>` y va ordenado por `(posición de la columna,
posición de la tarjeta)`: el orden en el que se pinta el tablero.

`PUT` reemplaza el estado completo (`title` + `description`), mismo criterio que
`ColumnUpdate` en TASK-05; **no mueve la tarjeta**, para eso está `/move`.

`/move` es `POST` y no `PUT` —a diferencia de `PUT .../columns/reorder`— porque su
cuerpo no es el estado final del recurso sino una intención relativa que se resuelve
contra el estado vivo de la columna: repetir la llamada puede dar una `position`
distinta, así que la idempotencia que `PUT` promete no se cumple.

## Filtro de pertenencia

`repositories/cards.py` reutiliza `repositories/membership.py::board_ids_for_actor` en
**toda** consulta que exponga datos (listado y búsqueda por id), como exige
CLAUDE.md § 4. Las dos que no lo llevan —`count_cards_in_column` y
`list_positions_in_column`— no exponen nada (un entero y una lista de flotantes
anónimos) y sus llamantes ya han resuelto la pertenencia contra la columna; queda dicho
en el docstring de cada una.

## Borrar una columna con tarjetas

Queda cerrado el pendiente que TASK-05 dejó marcado: `services/columns.py::delete_column`
cuenta las tarjetas de la columna y devuelve **`409 Conflict`** ("No se puede borrar una
columna con tarjetas.") si hay alguna. El recuento se hace **con la fila de la columna
ya bloqueada**: sin ese bloqueo, una tarjeta creada entre el recuento y el `DELETE`
desaparecería en silencio por el `ON DELETE CASCADE` de `cards.column_id`.

## No entra en esta feature

Asignación y reclamación con vencimiento (TASK-10), comentarios (TASK-11), eventos de
actividad (TASK-12), etiquetas, fechas de vencimiento, adjuntos y subtareas.

## Contrato

`backend/openapi.json` incluye ahora los seis endpoints de
`/api/v1/boards/{board_id}/cards`. El frontend no los consume todavía (la primera vez
es TASK-08); no se ha regenerado `frontend/src/api/schema.d.ts`, mismo criterio que
TASK-04 y TASK-05.
