# TASK-06 · Tarjetas: CRUD y movimiento

**Prioridad:** Alta · **Depende de:** TASK-05

## Objetivo

La unidad de trabajo del tablero. Una tarjeta vive en una columna, tiene una posición y
recuerda **qué actor la creó**. Moverla entre columnas es la operación central del
producto y tiene que aguantar que varios actores — personas y agentes — la toquen a la
vez.

## Alcance

**Entra:**
- Modelo `Card` (tablero, columna, título, descripción, posición, actor creador,
  timestamps).
- CRUD bajo `/api/v1/boards/{board_id}/cards`, con listado paginado por tablero y
  filtrable por columna.
- Endpoint de movimiento: columna destino + posición destino, en una sola operación
  atómica.
- Aplicación del límite WIP de la columna destino, si está definido.
- Migración revisada y tests, incluida concurrencia de movimientos.

**No entra:**
- Asignación y reclamación (TASK-10), comentarios (TASK-11), eventos (TASK-12).
- Etiquetas, fechas de vencimiento, adjuntos, subtareas.

## Criterios de aceptación

- [ ] Se crea, edita y borra una tarjeta, y el creador registrado es el actor
      autenticado, sea persona o agente.
- [ ] Mover una tarjeta a otra columna y a otra posición persiste correctamente y el
      orden se conserva al releer.
- [ ] Dos movimientos concurrentes sobre la misma columna **no** dejan posiciones
      duplicadas ni pierden una tarjeta (test explícito de concurrencia).
- [ ] Mover a una columna que ya alcanzó su límite WIP devuelve un error claro en
      español.
- [ ] Una tarjeta de un tablero ajeno devuelve **404**.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- La atomicidad del movimiento es el punto delicado: resuélvelo en base de datos
  (bloqueo o actualización condicional), no con lecturas previas en Python.
- Reutiliza el esquema de posiciones decidido en TASK-05.
