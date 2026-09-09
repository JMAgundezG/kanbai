---
name: spec-task
description: Especifica TASK-NN de kanbai tras aprobar su plan, o al pedir su spec. Espera el OK antes de implementar.
---

# Especificar una tarea

1. Reutiliza `AGENTS.md` si está leído o incluido íntegro en el contexto vigente;
   en otro caso, léelo completo. Lee la tarea, `docs/plans/plan-TASK-NN.md` y su
   estado actual en `docs/tasks/STATUS.md`. Exige plan aprobado y En progreso;
   invocar esta skill para la tarea expresa aprobación del plan existente. Si
   falta el plan o el estado no corresponde, informa y detente.
2. Inspecciona solo el código y cambios relevantes, usando los patrones existentes.
   Crea `docs/plans/spec-TASK-NN.md`, enlazando plan y tarea, con cabecera
   `Estado: En progreso · Fase: Especificación · Creada: <hoy>`.
   Concreta archivos, decisiones, casos límite, errores y pruebas observables.
   Detalla únicamente lo afectado:
   - Datos: columnas, relaciones, restricciones, índices y migración; tratamiento
     de datos existentes y revisión de lo autogenerado.
   - API: schemas y validación, reglas por capa, rutas, métodos, request/response,
     estados HTTP, autorización, 404 para recursos ajenos y paginación.
   - Frontend: tipos generados, consultas, invalidación, componentes HeroUI, rutas
     y estados de carga, vacío y error.
   - Infraestructura: configuración, arranque, variables y verificación.
   No rellenes apartados vacíos: indica una sola vez lo que no aplica. Referencia
   el objetivo y criterios del plan sin volver a copiarlos. Justifica dependencias
   nuevas y documenta desviaciones; consulta cambios de fondo respecto al plan.
3. Si cambia el contrato, especifica `uv run poe openapi` y `npm run gen:api`,
   ajuste del consumidor y migración de cambios incompatibles. Define tests de
   éxito, validación y permisos según el alcance, y ambos checks de AGENTS.md.
   No implementes ni ejecutes suites en esta fase.
4. Pon la cabecera del plan en Fase Especificación; conserva En progreso en el
   tablero y enlaza la spec pendiente del OK en Notas. Entrega el enlace y las
   decisiones principales. Detente para el OK; después el usuario puede ejecutar
   `/implement-task TASK-NN`. No hagas commits sin petición.

Relee solo lo cambiado o ausente del contexto. Si falta algo esencial que impide
especificar, registra Bloqueada y motivo en el tablero; recalcula Resumen y fecha,
y anota en plan y spec qué lo desbloquea. El OK pendiente no es un bloqueo.
