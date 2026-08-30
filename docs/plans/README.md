# docs/plans

Planificación de las tareas del tablero (`docs/tasks/`). **Dos archivos por tarea**:

- `plan-<código>.md` — plan de alto nivel (objetivo, enfoque, alcance). Lo crea **`work-task`**.
- `spec-<código>.md` — especificación técnica de implementación. La crea **`spec-task`**.

(p. ej. `plan-TASK-03.md` y `spec-TASK-03.md`).

## Ciclo de vida de una tarea (4 comandos, puerta humana entre fases)

```
/work-task  →  [apruebas el plan]  →  /spec-task  →  [das el OK]  →  /implement-task  →  [code review]  →  /close-task
PLANIFICAR                            ESPECIFICAR                    IMPLEMENTAR                            COMPLETAR
En progreso                           En progreso                    En progreso → En revisión             → Completada
```

- **`work-task`** marca `En progreso` y escribe el plan; se detiene a por tu aprobación.
- **`spec-task`** escribe la spec; se detiene a por tu OK.
- **`implement-task`** implementa y verifica el código; deja la tarea `En revisión` para tu code review.
- **`close-task`** aprueba la tarea (`Completada`) y propaga los cambios (desbloqueo de
  dependientes, docs, contrato front↔back, migraciones).

En cualquier fase, si algo se atasca, la tarea pasa a `Bloqueada` con el motivo en
`docs/tasks/STATUS.md` y en el plan. El estado de la cabecera de estos archivos se
mantiene en sincronía con `docs/tasks/STATUS.md`.
