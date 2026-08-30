---
name: work-task
description: >-
  Primer paso del ciclo de una tarea: PLANIFICAR. Localiza docs/tasks/TASK-NN-*.md,
  la marca "En progreso" en docs/tasks/STATUS.md y escribe el plan en
  docs/plans/plan-TASK-NN.md. NO implementa código: se detiene para que el usuario
  apruebe el plan. Tras la aprobación, el flujo sigue con la skill spec-task. Úsala
  cuando el usuario diga "trabaja/empieza/planifica la tarea TASK-NN" o pida arrancar
  la siguiente tarea del tablero.
---

# work-task — coger una tarea y planificarla

Primera fase del ciclo de vida de una tarea. El ciclo completo son 4 comandos con
una puerta de aprobación humana entre cada fase:

```
/work-task  →  [apruebas el plan]  →  /spec-task  →  [das el OK]  →  /implement-task  →  [code review]  →  /close-task
PLANIFICAR                            ESPECIFICAR                    IMPLEMENTAR                            COMPLETAR
```

**Esta skill solo PLANIFICA.** No escribe código de la tarea: deja el plan listo y
para a por la aprobación del usuario.

El tablero vive en `docs/tasks/STATUS.md` (tabla
`ID | Tarea | Prioridad | Depende de | Estado | Responsable | Notas` + bloque
"Resumen"). Estados válidos: `Pendiente · En progreso · En revisión · Bloqueada · Completada`.

## Procedimiento

### 1. Identificar la tarea
- Si el usuario da un código (p. ej. `TASK-03`), úsalo. Si no, lee
  `docs/tasks/STATUS.md` y propón la **siguiente tarea elegible**: la primera
  `Pendiente` según el "Orden sugerido" cuya columna "Depende de" esté **toda en
  `Completada`**. No arranques una tarea con dependencias sin completar.
- **Lee completo** `docs/tasks/TASK-NN-*.md` (objetivo, alcance, criterios de
  aceptación, dependencias, notas). Es tu fuente de la verdad.
- Lee el `CLAUDE.md` de la raíz: stack, convenciones y comandos del proyecto.

### 2. Comprobar precondiciones
- En `STATUS.md`, confirma que cada dependencia de "Depende de" está `Completada`.
  Si alguna no lo está, **no empieces**: dilo y para (o pregunta si forzarlo).
- Mira el estado actual de la fila. Si ya es `En progreso`/`En revisión`/`Completada`,
  avisa antes de continuar.

### 3. Marcar "En progreso" en STATUS.md
- Obtén la fecha de hoy con `date +%Y-%m-%d`.
- En la fila: **Estado** → `En progreso`; **Responsable** → `Claude` (o quien indique).
- Recalcula el bloque **"Resumen"** y actualiza **"Última actualización: <hoy>"**.
- No toques otras filas.

### 4. Escribir el plan → `docs/plans/plan-TASK-NN.md`
- Crea `docs/plans/` si no existe. Nombre exacto: `plan-<código>.md` →
  `docs/plans/plan-TASK-03.md`.
- El plan es de **alto nivel** (el diseño técnico detallado va luego en la spec).
  Plantilla:

  ```markdown
  # Plan · TASK-NN · <título de la tarea>

  **Estado:** En progreso · **Fase:** Planificación · **Iniciado:** <hoy> · **Responsable:** Claude
  **Tarea:** [TASK-NN](../tasks/TASK-NN-<slug>.md)

  ## Objetivo
  <objetivo de la tarea, en tus palabras>

  ## Enfoque
  <estrategia general; alternativas consideradas y por qué esta>

  ## Alcance
  - Backend (`backend/src/kanbai/`): qué se toca (models / schemas / repositories /
    services / routers / migrations / tests)
  - Frontend (`frontend/src/`): qué se toca (features / hooks / componentes / rutas)
  - Contrato: ¿cambia el OpenAPI? Entonces hay que regenerar
    `frontend/src/api/schema.d.ts` (`npm run gen:api`).
  - (Una feature suele tocar AMBOS lados.)

  ## Criterios de aceptación
  <copiados de la tarea, como checklist>
  - [ ] …

  ## Plan de verificación
  - Backend: `uv run poe check` desde `backend/` (ruff + mypy + pytest)
  - Frontend: `npm run check` desde `frontend/` (eslint + tsc + vitest)
  - End-to-end cuando aplique: API real levantada con `uv run poe dev`

  ## Riesgos / decisiones abiertas
  - …
  ```

### 5. DETENERTE para la aprobación del plan
- **No implementes nada.** Presenta al usuario un resumen del plan y dónde está
  (`docs/plans/plan-TASK-NN.md`).
- Indícale el siguiente paso: *«Si apruebas el plan, ejecuta `/spec-task TASK-NN`
  para crear la especificación de implementación.»*

## Si te bloqueas al planificar
Si no puedes planificar (falta información clave, decisión del usuario, dependencia
real ausente):
- En `STATUS.md`: **Estado** → `Bloqueada`; motivo breve en **Notas**.
- Recalcula "Resumen" y actualiza "Última actualización".
- En el plan, añade `## Bloqueo` con el motivo y **qué lo desbloquearía**.
- Explica al usuario el bloqueo y la acción necesaria.

## Reglas para editar STATUS.md
- Tras cualquier cambio de estado: recalcula "Resumen" y actualiza
  "Última actualización" a hoy. Cambia solo la fila en curso.
- Si el repo es git, no hagas commit salvo que el usuario lo pida.
