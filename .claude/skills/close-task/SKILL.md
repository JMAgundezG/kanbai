---
name: close-task
description: >-
  Cuarto y último paso del ciclo de una tarea: COMPLETAR. Tras la code review del
  usuario, aprueba la tarea pasándola de "En revisión" a "Completada" en
  docs/tasks/STATUS.md y propaga todos los cambios derivados — recuenta el bloque
  Resumen, desbloquea las tareas dependientes que queden listas, actualiza la
  documentación y el contrato front↔back afectados, y finaliza el plan y la spec.
  Úsala cuando el usuario apruebe una tarea ya revisada o diga
  "cierra/completa/aprueba/marca como terminada TASK-NN".
---

# close-task — aprobar una tarea revisada y propagar los cambios

Cuarta y última fase del ciclo de vida (después de la code review):

```
… /implement-task  →  [tu code review]  →  **/close-task**
                                            En revisión → Completada  (+ propagación)
```

Es el paso de **aprobación manual** que cierra lo que dejó `implement-task` en
`En revisión` una vez el usuario ha revisado el código. No solo cambia una celda:
deja el tablero y los documentos coherentes con la tarea ya terminada.

## Procedimiento

### 1. Identificar y leer
- Recibe el código (p. ej. `TASK-03`). Lee `docs/tasks/TASK-NN-*.md`,
  `docs/plans/plan-TASK-NN.md` y la fila correspondiente en `docs/tasks/STATUS.md`.

### 2. Verificar que es aprobable
- La fila debe estar en **`En revisión`** (es decir: `implement-task` ya implementó
  el código y el usuario lo ha revisado). Si está en otro estado, **para y avisa**
  (si está `Bloqueada` o `En progreso`, aún no toca cerrar; dilo).
- Confirma que los **criterios de aceptación** del archivo de la tarea están
  cumplidos. Corre la verificación final: `uv run poe check` desde `backend/` y
  `npm run check` desde `frontend/`. Si algo falla, **no cierres**: repórtalo.

### 3. Marcar "Completada" en STATUS.md
- Obtén la fecha de hoy con `date +%Y-%m-%d`.
- Estado de la fila → **`Completada`**.
- Recalcula el bloque **"Resumen"** y actualiza **"Última actualización: <hoy>"**.

### 4. Propagar todos los cambios derivados
Recorre cada efecto y aplícalo (o di explícitamente que no aplica):

- **Desbloqueo de dependientes.** Para cada tarea cuya columna "Depende de"
  incluya esta tarea: si TODAS sus dependencias están ya `Completada` y la tarea
  está `Bloqueada` o `Pendiente`, déjala lista para empezar (`Pendiente`) y anota
  en Notas "desbloqueada por TASK-NN". Vuelve a recalcular el Resumen si cambian.
- **Documentación.** Si la tarea introdujo o cambió modelos, endpoints, campos,
  enums o flujos, actualiza lo afectado: `docs/features/*`, `README.md` y el
  `CLAUDE.md` si cambian convenciones, comandos o arquitectura.
- **Contrato front ↔ back.** Si cambió algún `response_model`, confirma que
  `frontend/src/api/schema.d.ts` está regenerado (`npm run gen:api`) y que `tsc`
  pasa limpio.
- **Migraciones.** Si tocó modelos, confirma que la migración existe, aplica
  (`alembic upgrade head`) y que `alembic revision --autogenerate` ya no detecta
  diferencias pendientes.
- **Plan y spec.** En `docs/plans/plan-TASK-NN.md` y `docs/plans/spec-TASK-NN.md` pon
  la cabecera `**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** <hoy>` y deja
  todos los checkboxes hechos.

### 5. Reportar
Resume al usuario: estado nuevo, tareas que han quedado desbloqueadas, documentos y
archivos tocados durante la propagación, y resultado de la verificación final.

## Reglas
- Cambia el estado solo de la tarea que se cierra (y, en la propagación, las
  dependientes que de verdad queden listas). Recalcula el "Resumen" tras cada cambio.
- Si el repo es git, no hagas commit salvo que el usuario lo pida.
