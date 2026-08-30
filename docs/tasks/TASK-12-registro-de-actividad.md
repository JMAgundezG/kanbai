# TASK-12 · Registro de actividad (eventos)

**Prioridad:** Alta · **Depende de:** TASK-06, TASK-09

## Objetivo

Hacer reconstruible lo que pasa en un tablero. Cuando parte del trabajo lo ejecuta un
agente sin supervisión, saber **qué se hizo, sobre qué y quién lo hizo** deja de ser un
lujo de auditoría y pasa a ser lo que hace tolerable delegar.

## Alcance

**Entra:**
- Modelo `Event` inmutable: tablero, tarjeta opcional, actor, tipo, datos del cambio,
  marca de tiempo.
- Emisión de eventos desde la capa de servicios para: crear/editar/mover/borrar tarjeta,
  asignar, reclamar y liberar, comentar, y cambios de columnas.
- Consulta paginada y filtrable por tablero, tarjeta, actor y tipo.
- Migración revisada y tests: cada acción cubierta genera su evento con el actor
  correcto.

**No entra:**
- Transporte en vivo hacia el navegador (TASK-14).
- Interfaz de la línea de actividad (TASK-15).
- Retención, archivado o exportación del histórico.

## Criterios de aceptación

- [ ] Mover, asignar, reclamar y comentar generan un evento con su actor y sus datos.
- [ ] No existe ningún endpoint que permita editar o borrar un evento.
- [ ] Se puede consultar la actividad de una tarjeta y la de un actor, paginadas.
- [ ] Si la acción falla y se revierte la transacción, **no** queda evento huérfano.
- [ ] Los eventos de un tablero ajeno devuelven **404**.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- El evento se escribe en la **misma transacción** que el cambio que describe: o pasan
  los dos o no pasa ninguno.
- Emítelos en los servicios, nunca en los routers, para que valga igual una llamada de
  la interfaz que una de un agente.
- Este registro es la fuente de la que bebe el tiempo real de TASK-14: diseña el tipo y
  los datos del evento pensando en que se van a serializar hacia el navegador.
