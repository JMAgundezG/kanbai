# TASK-15 · Frontend: detalle de tarjeta

**Prioridad:** Media · **Depende de:** TASK-08, TASK-11, TASK-12

## Objetivo

La vista donde de verdad ocurre la colaboración: abrir una tarjeta y ver su
conversación, su historia y quién la tiene reclamada — distinguiendo de un vistazo lo
que ha escrito una persona de lo que ha escrito un agente.

## Alcance

**Entra:**
- Panel o modal de HeroUI con título y descripción editables.
- Hilo de comentarios, con envío y aparición sin recargar.
- Línea de actividad construida desde los eventos.
- Responsable y estado de la reclamación, con acción de liberar para las personas.
- **Distintivo visual claro** entre autor persona y autor agente.
- Estados de carga, vacío y error; tests por roles y texto.

**No entra:**
- Edición enriquecida, adjuntos y menciones.
- Gestión de agentes (TASK-16).

## Criterios de aceptación

- [ ] Se distingue sin esfuerzo si un comentario o una acción los hizo una persona o un
      agente.
- [ ] Publicar un comentario lo muestra sin recargar y sin duplicarlo.
- [ ] La línea de actividad refleja movimientos, asignaciones y reclamaciones en orden.
- [ ] Una persona puede liberar la reclamación de un agente desde esta vista.
- [ ] El componente es accesible con teclado y cierra correctamente el foco.
- [ ] `npm run check` en verde.

## Notas técnicas

- El cuerpo del comentario llega sin interpretar (TASK-11): si se renderiza markdown, el
  saneado es responsabilidad de esta tarea.
- Componentes tontos + hooks con la lógica; nada de fetch dentro del componente.
