# TASK-05 · Columnas del tablero

**Prioridad:** Alta · **Depende de:** TASK-04

## Objetivo

Modelar las fases del flujo de trabajo: columnas ordenadas dentro de un tablero, que se
pueden crear, renombrar, reordenar y limitar en trabajo en curso.

## Alcance

**Entra:**
- Modelo `Column` (tablero, nombre, posición, límite WIP opcional).
- CRUD bajo `/api/v1/boards/{board_id}/columns`.
- Endpoint de reordenación que acepta el nuevo orden completo en una sola llamada.
- Migración revisada y tests, incluida la reordenación y el acceso ajeno.

**No entra:**
- Tarjetas (TASK-06) y, por tanto, la **aplicación** del límite WIP, que se hará al
  mover tarjetas.
- Plantillas de tablero o columnas por defecto configurables.

## Criterios de aceptación

- [ ] Crear un tablero deja un juego de columnas inicial razonable: **decidido —
      siempre tres columnas fijas en español, "Por hacer" / "En curso" / "Hecho"**,
      sin plantillas configurables.
- [ ] Reordenar N columnas en una llamada deja un orden estable y sin huecos ni
      posiciones repetidas.
- [ ] Borrar una columna con tarjetas está impedido o exige destino: **decidido —
      se bloquea con `409 Conflict`** (no se exige destino). Las tarjetas no existen
      todavía (TASK-06); el servicio deja el punto de extensión comentado y TASK-06
      añade la comprobación real (contar tarjetas de la columna) y su test al añadir
      el modelo `Card`.
- [ ] Operar sobre una columna de un tablero ajeno devuelve **404**.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- **Representación de la posición: `float` con `UniqueConstraint` aplazable
  (`DEFERRABLE INITIALLY DEFERRED`) por tablero**, no entero con reindexado. Permite
  mover una fila con un único `UPDATE` sin desplazar el resto — la propiedad que
  TASK-06 exige para mover tarjetas de forma atómica bajo concurrencia. Detalle
  completo en `docs/plans/spec-TASK-05.md`. TASK-06 reutiliza el mismo mecanismo
  (`cards.position`, constraint sobre `(column_id, position)`).
- Cualquier miembro del tablero (no solo `owner`) puede gestionar columnas: crear,
  renombrar, reordenar y borrar. Es trabajo operativo del flujo, no administración
  del tablero (que sigue siendo solo-`owner`, TASK-04).
