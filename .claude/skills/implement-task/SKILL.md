---
name: implement-task
description: >-
  Tercer paso del ciclo de una tarea: IMPLEMENTAR. Tras dar el OK a la especificación
  (docs/plans/spec-TASK-NN.md), escribe el código siguiendo la spec y el CLAUDE.md,
  lo verifica (uv run poe check en backend/, npm run check en frontend/) y deja la
  tarea en "En revisión" en docs/tasks/STATUS.md, lista para que el usuario haga la
  code review. Tras la review aprobada, el flujo sigue con close-task. Úsala cuando
  el usuario dé el OK a la spec de TASK-NN o diga "implementa TASK-NN".
---

# implement-task — implementar el código de la tarea

Tercera fase del ciclo de vida (después de `spec-task`, antes de `close-task`):

```
… /spec-task  →  [spec con OK]  →  **/implement-task**  →  [tu code review]  →  /close-task
                                   IMPLEMENTAR (→ En revisión)
```

Escribe el código real de la tarea según la especificación aprobada y deja la tarea
**lista para la code review** del usuario.

## Procedimiento

### 1. Cargar contexto
- Recibe el código (p. ej. `TASK-03`). Lee `docs/tasks/TASK-NN-*.md`,
  `docs/plans/plan-TASK-NN.md`, `docs/plans/spec-TASK-NN.md` y la fila en
  `docs/tasks/STATUS.md`.
- Precondición: existe la spec y la tarea está en **`En progreso`** (lanzar esta
  skill implica que el usuario dio el OK a la spec). Si falta la spec o el estado no
  cuadra, avisa y para.
- **Lee el `CLAUDE.md`** antes de tocar código y sigue sus convenciones.

### 2. Implementar siguiendo la spec
- Sigue la especificación al pie; si necesitas desviarte, anótalo en la sección
  "Desviaciones" de la spec y, si es de fondo, consulta al usuario.
- Recuerda las reglas del repo:
  - Una feature suele tocar **backend y frontend**. El contrato se **genera**, no se
    copia a mano: cambias el `response_model` → `npm run gen:api` en `frontend/`.
  - Backend por capas: `router` (HTTP) → `service` (reglas) → `repository` (consultas)
    → `model`. Nada de consultas SQL en el router.
  - Endpoints bajo `/api/v1/<recurso>`; siempre autenticación explícita y filtrado por
    el usuario dueño del recurso; listados paginados.
  - Si tocas modelos: `alembic revision --autogenerate -m "..."` y **revisa la
    migración generada** antes de aplicarla.
  - Textos de cara al usuario en **español**; identificadores, ramas y comentarios en
    **inglés**.
- Marca el progreso en los checkboxes del plan a medida que avanzas.

### 3. Verificar de verdad
- Backend, desde `backend/`: `uv run poe check` (ruff + mypy + pytest). Añade o
  actualiza tests en `backend/tests/` para lo que has implementado.
- Frontend, desde `frontend/`: `npm run check` (eslint + tsc + vitest).
- Si cambió el contrato: `npm run gen:api` y confirma que `tsc` sigue limpio.
- End-to-end cuando aplique: levanta la API (`uv run poe dev`) y golpéala de verdad.
- **No declares "hecho" sin verificar.** Pega el resultado real de los comandos.

### 4. Dejar la tarea en "En revisión"
- Obtén la fecha de hoy con `date +%Y-%m-%d`.
- En `STATUS.md`: **Estado** de la fila → **`En revisión`**. Recalcula "Resumen" y
  actualiza "Última actualización". (NO `Completada`: eso lo decide el usuario tras
  su review, vía `close-task`.)
- Actualiza cabeceras de `plan-TASK-NN.md` y `spec-TASK-NN.md`:
  `**Fase:** Revisión` / `**Estado:** En revisión`; deja hechos los checkboxes.

### 5. DETENERTE para la code review
- Resume al usuario qué se implementó, los archivos tocados y el resultado de la
  verificación.
- Indica el siguiente paso: *«Revisa el código (por ejemplo con `/code-review`). Si
  está bien, ejecuta `/close-task TASK-NN` para aprobar la tarea y pasarla a
  Completada.»*

## Si te bloqueas
Si no puedes terminar (tests que no pasan por causa externa, dependencia ausente,
decisión del usuario):
- En `STATUS.md`: **Estado** → `Bloqueada`; motivo en **Notas**; recalcula "Resumen"
  y "Última actualización".
- Anota el bloqueo en el plan (`## Bloqueo`) con qué lo desbloquearía y explícalo.

## Reglas
- Si el repo es git, no hagas commit salvo que el usuario lo pida.
