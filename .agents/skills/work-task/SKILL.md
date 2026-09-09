---
name: work-task
description: Planifica TASK-NN o la siguiente tarea elegible de kanbai. Crea el plan y espera aprobación; no implementa.
---

# Planificar una tarea

1. Lee `AGENTS.md` completo si no está ya leído o incluido íntegro en el contexto
   vigente. Reutiliza lo conocido; consulta cambios si el archivo fue modificado.
   Lee `docs/tasks/STATUS.md` y la tarea completa `docs/tasks/TASK-NN-*.md`.
   Si no hay ID, usa el Orden sugerido para proponer la primera Pendiente con todas
   sus dependencias Completada. Si el usuario pidió arrancar la siguiente, arráncala.
2. Confirma las dependencias en el tablero. Si falta alguna, no arranques; informa
   del impedimento. Si la tarea ya está iniciada, en revisión o completada, avisa
   y respeta su fase; no sobrescribas trabajo existente ni reinicies su estado.
3. Obtén hoy con `date +%Y-%m-%d`. Pon solo su fila En progreso, responsable Codex
   (salvo indicación del usuario); recalcula Resumen y Última actualización.
4. Inspecciona los archivos y cambios sin commit relevantes. Crea
   `docs/plans/plan-TASK-NN.md` con título, enlace a la tarea y cabecera
   `Estado: En progreso · Fase: Planificación · Iniciado: <hoy> · Responsable: Codex`.
   Incluye objetivo, enfoque, alcance, criterios de aceptación copiados como
   checklist, verificación y riesgos reales. Indica si cambia el contrato.
   Planifica ambos checks de AGENTS.md y la verificación específica necesaria.
   Mantén el diseño a alto nivel; los comandos de CI, campos y componentes van
   en la spec. No ejecutes suites en esta fase.
5. Entrega el enlace al plan y un resumen breve. Detente para su aprobación;
   el siguiente paso del usuario es `/spec-task TASK-NN`. No crees la spec,
   implementes ni hagas commits sin petición.

Si un impedimento real bloquea la planificación, registra Bloqueada y el motivo en
la fila, recalcula Resumen y fecha, y anota en el plan qué lo desbloquea. Esperar la
aprobación normal del plan no es un bloqueo. Evita releer archivos sin cambios o
copiar las reglas de AGENTS.md en el entregable.
