# Columnas del tablero

**Introducida por:** [TASK-05](../tasks/TASK-05-columnas.md) · **Última actualización:** 2026-08-30

Las **columnas** son las fases del flujo de trabajo de un tablero. Cualquier miembro
del tablero (`owner` o `member`, sin distinción de rol) las crea, renombra, reordena y
borra — a diferencia de la administración del tablero en sí (TASK-04), que sigue
siendo cosa solo del `owner`.

## Modelo

| Tabla | Columnas |
|-------|----------|
| `board_columns` | `id` (UUID), `board_id` (FK→`boards.id`, `ON DELETE CASCADE`), `name`, `wip_limit` (entero opcional, `CHECK > 0`), `position` (`DOUBLE PRECISION`), `created_at` |

La clase del modelo se llama `BoardColumn`, no `Column`: evita chocar con
`sqlalchemy.Column` y sigue el mismo patrón compuesto que `board_members`.

## El esquema de posiciones — decisión central, reutilizada por TASK-06

`position` es un **`float`**, no un entero con reindexado, con una
`UniqueConstraint(board_id, position)` **aplazable**
(`DEFERRABLE INITIALLY DEFERRED`, específico de PostgreSQL):

```python
UniqueConstraint(
    "board_id", "position",
    name="uq_board_columns_board_id_position",
    deferrable=True,
    initially="DEFERRED",
)
```

Por qué: mover una fila entre dos vecinas exige escribir **solo esa fila** (un
`UPDATE`), sin desplazar el resto — la propiedad que TASK-06 necesita para mover
tarjetas de forma atómica bajo concurrencia sin colisionar con otros movimientos
simultáneos. El aplazamiento del `UNIQUE` deja que una operación que sí toca varias
filas a la vez (la reordenación completa) escriba en cualquier orden dentro de la
misma transacción: PostgreSQL solo comprueba la unicidad al hacer `COMMIT`.

**El aplazamiento por sí solo no basta contra dos altas concurrentes**: dos
`POST .../columns` a la vez en el mismo tablero pueden leer el mismo
`MAX(position)` y calcular el mismo valor siguiente, chocando recién al hacer
`COMMIT` con un `IntegrityError` sin traducir (500 opaco). `create_column` y
`reorder_columns` en `services/columns.py` lo evitan bloqueando la fila del tablero
(`repositories/boards.py::lock_board_for_update`, `SELECT ... FOR UPDATE`) antes de
leer o escribir ninguna posición: dos peticiones concurrentes sobre el mismo
tablero quedan serializadas, nunca calculan el mismo valor. Detectado y corregido
en la code review de la tarea, con test de regresión en
`test_crear_columnas_concurrentes_en_el_mismo_tablero_no_colisiona`.

Asignación de valores:

- **Alta** (crear columna, o sembrar las tres iniciales de un tablero nuevo): se
  añade al final — `position = máximo existente del tablero + GAP`, con
  `GAP = 1024.0` (`repositories/columns.py::GAP`).
- **Reordenación completa** (`PUT .../columns/reorder`): reasigna posiciones en
  múltiplos consecutivos de `GAP` (`0.0, 1024.0, 2048.0, …`) según el índice de la
  lista recibida — garantiza "sin huecos ni posiciones repetidas" en el **rango**
  (exactamente una columna por rango sucesivo, sin ninguno vacío ni duplicado), y
  conserva el hueco entre vecinas que hace falta para insertar entre dos columnas
  más adelante. Colapsar a enteros desnudos (`0.0, 1.0, 2.0`) habría cumplido la
  letra del criterio pero destruido el motivo de ser del esquema — se corrigió tras
  la code review de la tarea.

**TASK-06 reutilizó exactamente este mecanismo** para `cards.position`: mismo tipo
`float`, mismo patrón de constraint aplazable sobre `(column_id, position)`, el mismo
`GAP` —importado de aquí, no redefinido— al añadir, y punto medio
`(antes.position + después.position) / 2` para mover una tarjeta entre dos vecinas sin
tocar ninguna otra fila. Lo que TASK-06 añadió por su cuenta es
`lock_column_for_update` (bloqueo de la fila de la *columna*, no del tablero: los
invariantes de una tarjeta —unicidad de posición y `wip_limit`— son por columna) y la
recompactación de una columna cuando la precisión del `float` se agota. Ver
[tarjetas.md](tarjetas.md).

## Columnas iniciales al crear un tablero

`services/boards.py::create_board` siembra siempre tres columnas fijas, en la misma
transacción que crea el tablero y la membresía `owner` (un tablero nunca es visible
desde fuera sin sus columnas, igual que nunca lo es sin su owner):

1. "Por hacer"
2. "En curso"
3. "Hecho"

Sin plantillas configurables (fuera de alcance de esta tarea).

## Borrar la última columna del tablero

Bloqueado con `409 Conflict` (`services/columns.py::delete_column`): un tablero sin
ninguna columna no tiene dónde vivir una tarjeta y nada lo resiembra
automáticamente (`seed_default_columns` solo corre al crear el tablero). Mismo
patrón que "no puedes quitar al único owner" en TASK-04 — la regla cuenta cuántas
columnas quedan, no cuál en concreto se borra.

## Borrar una columna con tarjetas

**Se bloquea con `409 Conflict`**, no se exige destino: mover las tarjetas a otra
columna antes de borrar es una operación explícita del usuario, más simple de
razonar que un reasignado implícito. TASK-06 hizo real la comprobación al introducir
el modelo `Card` — `services/columns.py::delete_column` cuenta las tarjetas de la
columna y responde "No se puede borrar una columna con tarjetas." si hay alguna
(test: `test_borrar_columna_con_tarjetas_devuelve_409`).

El recuento se hace **con la fila de la columna ya bloqueada**
(`lock_column_for_update`): sin ese bloqueo, una tarjeta creada entre el recuento y
el `DELETE` desaparecería en silencio por el `ON DELETE CASCADE` de
`cards.column_id`.

## Endpoints

Todos bajo `/api/v1/boards/{board_id}/columns`, requieren ser miembro del tablero
(`404` si no lo eres, igual que TASK-04) y **no exigen ningún rol concreto**:

| Método | Ruta | Respuesta |
|--------|------|-----------|
| `GET` | `/api/v1/boards/{board_id}/columns` | `200 Page[ColumnRead]` (orden por `position`) / `404` |
| `POST` | `/api/v1/boards/{board_id}/columns` | `201 ColumnRead` / `404` / `422` |
| `GET` | `/api/v1/boards/{board_id}/columns/{column_id}` | `200 ColumnRead` / `404` |
| `PUT` | `/api/v1/boards/{board_id}/columns/{column_id}` | `200 ColumnRead` / `404` / `422` |
| `DELETE` | `/api/v1/boards/{board_id}/columns/{column_id}` | `204` / `404` / `409` (última columna, o con tarjetas desde TASK-06) |
| `PUT` | `/api/v1/boards/{board_id}/columns/reorder` | `200 list[ColumnRead]` / `404` / `422` |

`PUT .../reorder` acepta el orden completo de columnas en una sola llamada
(`ColumnReorder.column_ids`): la lista debe ser exactamente el conjunto de columnas
actuales del tablero, sin repetidos ni ausentes, o devuelve `422`. No se envuelve en
`Page[...]`: es la respuesta de una acción sobre el conjunto completo que el cliente
ya envió, no un listado filtrable.

`ColumnUpdate` reemplaza el estado completo (`name` + `wip_limit`) y se sirve por
**`PUT`, no `PATCH`**: un `PATCH` con reemplazo completo permite que un cliente que
solo quiera renombrar (un payload de `PATCH` natural) borre sin darse cuenta el
`wip_limit` existente al omitirlo. `PUT` deja esa semántica explícita en el propio
verbo — el cliente sabe que envía el estado completo — sin necesitar un tipo
centinela que distinga "`wip_limit` no enviado" de "`wip_limit` puesto a `null`".
Detectado en la code review de la tarea (el precedente de `BoardUpdate`, un único
campo, no cubre este caso porque no hay nada que perder al omitirlo).

## Filtro de pertenencia

Reutiliza `repositories/membership.py::board_ids_for_actor` en
`repositories/columns.py`, en **toda** consulta de la tabla — listado, listado
completo para reordenar, y la búsqueda por id (`get_column_by_id`) que usan
obtener/renombrar/borrar. La autorización está en la propia consulta SQL, no es
solo una convención de que el servicio llame antes a
`boards_service.get_board()` — así lo exige CLAUDE.md §4 ("todo recurso se filtra
por su dueño en la consulta, no después en Python"); la primera versión de
`get_column_by_id` no lo hacía y se corrigió en la code review. El 404 de "tablero
ajeno" en el listado lo sigue dando `services/boards.py::get_board` — una lista
vacía por sí sola no distingue "no soy miembro" de "soy miembro de un tablero sin
columnas".

## No entra en esta feature

Plantillas de columnas por tablero configurables. La aplicación real del `wip_limit`
y la comprobación de "columna con tarjetas" al borrar las añadió TASK-06 (ver
[tarjetas.md](tarjetas.md)).

## Contrato

`backend/openapi.json` incluye ahora los seis endpoints de
`/api/v1/boards/{board_id}/columns`. El frontend no los consume todavía (la primera
vez es TASK-08); no se ha regenerado `frontend/src/api/schema.d.ts` por el mismo
motivo que TASK-04.
