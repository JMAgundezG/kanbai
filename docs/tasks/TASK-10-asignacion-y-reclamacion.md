# TASK-10 · Asignación y reclamación de tarjetas

**Prioridad:** Alta · **Depende de:** TASK-06, TASK-09

## Objetivo

Impedir que dos actores trabajen la misma tarjeta a la vez. Una tarjeta se **reclama**
con un plazo de vencimiento: mientras esté vigente, es de quien la reclamó; si el plazo
expira — porque el agente murió o se colgó — vuelve a estar disponible. Y una persona
siempre puede liberarla a mano.

## Alcance

**Entra:**
- Responsable de la tarjeta (`assignee`), que puede ser cualquier actor.
- Reclamación con vencimiento: reclamar, renovar y liberar.
- Toma de una reclamación vencida por otro actor.
- Liberación forzada por una persona con permiso sobre el tablero.
- Tests explícitos de concurrencia y de vencimiento.

**No entra:**
- Selección automática de la siguiente tarjeta (TASK-13).
- Notificaciones y reflejo en la interfaz (TASK-14, TASK-15).
- Reglas de reparto automático entre agentes.

## Criterios de aceptación

- [ ] Dos actores reclamando la misma tarjeta a la vez: uno recibe `200` y el otro
      `409`, siempre — verificado con un test concurrente real.
- [ ] Una reclamación vencida puede ser tomada por otro actor; una vigente, no.
- [ ] El actor que reclama puede renovar el plazo mientras trabaja.
- [ ] Una persona miembro del tablero puede liberar la reclamación de un agente
      atascado.
- [ ] Reclamar una tarjeta de un tablero ajeno devuelve **404**.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- La exclusión se resuelve en base de datos con una actualización condicional o un
  bloqueo de fila; una comprobación previa en Python **no** es aceptable aquí.
- El plazo por defecto se configura en `core/config.py` y se documenta en `.env.example`.
