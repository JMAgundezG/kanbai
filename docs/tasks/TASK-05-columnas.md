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

- [ ] Crear un tablero deja un juego de columnas inicial razonable (decidido en la spec).
- [ ] Reordenar N columnas en una llamada deja un orden estable y sin huecos ni
      posiciones repetidas.
- [ ] Borrar una columna con tarjetas está impedido o exige destino (se decide en la
      spec y se refleja aquí antes de implementar).
- [ ] Operar sobre una columna de un tablero ajeno devuelve **404**.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- La representación de la posición (entero con reindexado frente a valor fraccional) se
  decide aquí y **se reutiliza tal cual en las tarjetas** (TASK-06): que no acaben
  siendo dos mecanismos distintos.
