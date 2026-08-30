# TASK-13 · API de agentes: cola de trabajo

**Prioridad:** Alta · **Depende de:** TASK-10, TASK-11, TASK-12

## Objetivo

Cerrar el bucle del producto: que un agente pueda operar de forma autónoma con un solo
token y sin estado de sesión. Pide trabajo, lo reclama, informa de lo que va haciendo y
lo devuelve al tablero — o pide ayuda a una persona.

## Alcance

**Entra:**
- `GET /api/v1/agent/tasks/next`: siguiente tarjeta candidata para el agente
  autenticado, según su membresía y los criterios de selección definidos en la spec.
- Reclamación atómica de la tarjeta devuelta (apoyada en TASK-10).
- Informar de progreso: comentario + movimiento de columna en una operación coherente.
- Marcar una tarjeta como **necesita revisión humana**, con motivo.
- Documentación de uso para integradores en `docs/features/`.
- Tests del flujo completo y de dos agentes compitiendo por la misma tarjeta.

**No entra:**
- Cualquier ejecución de agentes: kanbai expone la superficie, no orquesta modelos.
- Reparto inteligente, prioridades dinámicas o planificación.
- Interfaz para observarlo (TASK-15, TASK-16).

## Criterios de aceptación

- [ ] Un agente con su key obtiene una tarjeta candidata, y **ningún otro agente
      obtiene la misma** mientras la reclamación siga viva.
- [ ] Sin tarjetas candidatas, la respuesta lo indica sin error (`204` o lista vacía,
      decidido en la spec).
- [ ] El flujo pedir → reclamar → comentar → mover queda registrado como eventos
      atribuidos al agente.
- [ ] Marcar "necesita revisión humana" deja la tarjeta visible para la persona con el
      motivo escrito en el hilo.
- [ ] Todo el flujo funciona con una sola cabecera `Authorization`, sin cookies.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- Estos endpoints son **azúcar sobre el dominio existente**, no un dominio paralelo: por
  debajo llaman a los mismos servicios que usa la interfaz.
- Si al escribir la spec aparece lógica que solo tiene sentido para agentes, revisa
  antes si el modelo de TASK-09 se está torciendo.
