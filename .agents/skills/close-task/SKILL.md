---
name: close-task
description: Cierra TASK-NN de kanbai tras aprobar su code review o pedir su cierre. Propaga estado, dependientes y documentación.
---

# Cerrar una tarea revisada

1. Reutiliza `AGENTS.md` si está leído o incluido íntegro en el contexto vigente;
   en otro caso, léelo completo. Lee tarea, plan, spec y estado actual en
   `docs/tasks/STATUS.md`; evita relecturas sin cambios. Exige En revisión y
   aprobación del usuario. Si el estado no corresponde, informa y no cierres.
2. Confirma todos los criterios de aceptación. Ejecuta la verificación final:
   `uv run poe check` en `backend/` y `npm run check` en `frontend/`. Conserva
   salida real y código de salida; muestra un extracto útil. Si falla, no cierres.
3. Propaga los efectos aplicables, sin copiar especificaciones enteras:
   - Actualiza `docs/features/*`, README y AGENTS.md por los cambios de la tarea.
   - Si cambió el contrato, confirma OpenAPI y tipos generados sincronizados y
     tsc limpio; regenera con los comandos de AGENTS.md si están desalineados.
   - Si cambiaron modelos, confirma migración presente, aplicada y autogeneración
     sin operaciones pendientes. No omitas evidencia ausente.
   Si estos ajustes cambian lo ya probado, repite las comprobaciones afectadas.
4. Con todo satisfecho, pon solo su fila Completada y obtén hoy con
   `date +%Y-%m-%d`. Revisa las dependientes: déjalas Pendiente y anota
   «desbloqueada por TASK-NN» solo si todas sus dependencias están Completada y
   no queda otro motivo de bloqueo. No alteres tareas iniciadas o terminadas.
   Recalcula Resumen y Última actualización tras los cambios de estado.
5. Sincroniza plan y spec con `Estado: Completada · Fase: Cerrada · Cerrado: <hoy>`
   y checkboxes sustentados. Informa brevemente del cierre, dependientes
   desbloqueadas, documentos y resultados reales. No hagas commits sin petición.

Ante un impedimento real, conserva la tarea sin cerrar y registra Bloqueada con
motivo, Resumen y fecha actualizados, y el desbloqueo necesario en el plan.
