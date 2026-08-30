# TASK-11 · Comentarios en tarjetas

**Prioridad:** Alta · **Depende de:** TASK-06

## Objetivo

Abrir el canal donde una persona y un agente se hablan. El hilo de la tarjeta es donde
el agente explica qué ha hecho o qué necesita, y donde la persona responde, corrige o
desbloquea — sin salir del tablero.

## Alcance

**Entra:**
- Modelo `Comment` (tarjeta, actor autor, cuerpo, timestamps).
- Endpoints: listar paginado por tarjeta, crear, editar y borrar **los propios**.
- El esquema de respuesta identifica el autor y su tipo, para que la interfaz pueda
  distinguir persona de agente.
- Migración revisada y tests (feliz, validación, autoría ajena, tarjeta ajena).

**No entra:**
- Interfaz del hilo (TASK-15) y tiempo real (TASK-14).
- Menciones, reacciones, adjuntos, edición colaborativa.

## Criterios de aceptación

- [ ] Una persona y un agente comentan con el mismo endpoint y la respuesta identifica
      en ambos casos al autor y su tipo.
- [ ] Editar o borrar el comentario de otro actor está impedido.
- [ ] Comentar en una tarjeta de un tablero ajeno devuelve **404**.
- [ ] El listado está paginado con la forma `{items, total, page, size}`.
- [ ] El cuerpo se almacena tal cual, sin interpretar: el saneado es responsabilidad de
      quien lo renderiza.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- Un comentario no es un evento (TASK-12): el comentario es contenido escrito a
  propósito; el evento es el rastro automático de una acción. Crear un comentario
  **genera** un evento, pero son tablas distintas.
