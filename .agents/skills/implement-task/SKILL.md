---
name: implement-task
description: Implementa TASK-NN de kanbai tras el OK a su spec o al pedir implementarla. Verifica y deja En revisión.
---

# Implementar una tarea

1. Reutiliza `AGENTS.md` si está leído o incluido íntegro en el contexto vigente;
   en otro caso, léelo completo. Lee tarea, plan, spec y estado en
   `docs/tasks/STATUS.md`, evitando relecturas sin cambios. Exige En progreso y
   spec aprobada; invocar esta skill para la tarea expresa el OK a la spec
   existente. Si falta o el estado no corresponde, informa y detente.
2. Revisa el diff existente y aplica la spec respetando AGENTS.md y el trabajo
   ajeno. Registra desviaciones; consulta las que cambien decisiones de fondo.
   Actualiza checkboxes solo con evidencia. No amplíes el alcance a capas que
   la tarea no necesita.
3. Añade o ajusta tests de comportamiento: éxito, validación y permisos según el
   alcance. Si cambian modelos, genera, revisa y aplica la migración y comprueba
   autogeneración vacía. Si cambia el contrato, ejecuta `uv run poe openapi` en
   backend y `npm run gen:api` en frontend; ajusta consumidores y verifica tipos.
   Actualiza ejemplos de entorno y documentación afectada según AGENTS.md.
4. Ejecuta `uv run poe check` desde `backend/` y `npm run check` desde `frontend/`,
   más las comprobaciones de aceptación de la spec. Tras corregir un fallo,
   repite lo afectado; no vuelvas a lanzar verificaciones ya válidas sin cambios
   ni dudas pendientes. Conserva salida real y código de salida; muestra el
   resumen y los fallos útiles, sin volcar logs completos de éxitos.
5. Solo con todos los criterios y checks satisfechos, pon la fila En revisión.
   Recalcula Resumen y Última actualización con `date +%Y-%m-%d`; sincroniza plan
   y spec a `Estado: En revisión · Fase: Revisión`. No marques checks pendientes.
   Entrega cambios, evidencia y limitaciones; detente para la code review del
   usuario. Tras aprobarla, el siguiente paso es `/close-task TASK-NN`.

Si un impedimento real evita terminar, registra Bloqueada y motivo en el tablero,
actualiza conteos y fecha, y anota en el plan qué lo desbloquea. No marques
Completada ni hagas commits sin petición. La revisión pendiente no es un bloqueo.
