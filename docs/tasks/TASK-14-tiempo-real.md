# TASK-14 · Tiempo real: eventos del tablero en vivo

**Prioridad:** Media · **Depende de:** TASK-08, TASK-12

## Objetivo

Que la persona **vea** trabajar al agente. Sin esto, la colaboración se nota con retraso
y a base de recargar: el tablero abierto tiene que moverse cuando un agente mueve una
tarjeta al otro lado de la API.

## Alcance

**Entra:**
- Endpoint de eventos en vivo por tablero mediante SSE, autenticado y restringido a
  miembros.
- Reanudación tras corte usando el último evento recibido, sin perder eventos.
- Hook de frontend que consume el flujo e invalida las claves de TanStack Query
  afectadas por cada tipo de evento.
- Indicador visible de conexión perdida y reconexión.
- Tests de backend del flujo y de frontend del hook.

**No entra:**
- Canal bidireccional, presencia o cursores compartidos.
- Notificaciones fuera de la aplicación.

## Criterios de aceptación

- [ ] Mover una tarjeta llamando a la API con la key de un agente actualiza el tablero
      abierto en el navegador en menos de 2 segundos, sin recargar.
- [ ] Al cortar y restablecer la conexión, no se pierde ningún evento intermedio.
- [ ] Un actor que no es miembro del tablero no puede suscribirse (**404**).
- [ ] Cerrar la pestaña libera la conexión en el servidor.
- [ ] `uv run poe check` y `npm run check` en verde.

## Notas técnicas

- SSE antes que WebSocket: el flujo es unidireccional, atraviesa proxies sin
  ceremonias y encaja con el registro de eventos de TASK-12. Si más adelante hace falta
  bidireccionalidad, se revisa entonces.
- Cuidado con el modelo async: la conexión abierta no debe retener una sesión de base de
  datos (`CLAUDE.md` § 4).
