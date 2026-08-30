---
name: spec-task
description: >-
  Segundo paso del ciclo de una tarea: ESPECIFICAR. Tras aprobar el plan
  (docs/plans/plan-TASK-NN.md), escribe la especificación técnica de implementación
  en docs/plans/spec-TASK-NN.md (modelos SQLAlchemy y migración, schemas Pydantic,
  endpoints FastAPI con request/response, tipos y componentes del frontend, casos
  límite, plan de tests). NO implementa código: se detiene para que el usuario dé el
  OK. Tras el OK, el flujo sigue con implement-task. Úsala cuando el usuario apruebe
  el plan de TASK-NN o diga "crea la especificación / spec de TASK-NN".
---

# spec-task — especificación técnica de implementación

Segunda fase del ciclo de vida (después de `work-task`, antes de `implement-task`):

```
/work-task  →  [plan aprobado]  →  **/spec-task**  →  [das el OK]  →  /implement-task  →  …
```

Convierte el plan de alto nivel en un **diseño técnico concreto y accionable**.
**Esta skill solo ESPECIFICA.** No escribe código de la tarea: deja la spec lista y
para a por el OK del usuario.

## Procedimiento

### 1. Cargar contexto
- Recibe el código (p. ej. `TASK-03`). Lee `docs/tasks/TASK-NN-*.md`,
  `docs/plans/plan-TASK-NN.md` y la fila en `docs/tasks/STATUS.md`.
- Precondición: la tarea debe estar en **`En progreso`** y existir su plan (que el
  usuario haya lanzado esta skill implica que aprobó el plan). Si falta el plan o el
  estado no cuadra, avisa y para.
- **Lee el `CLAUDE.md`** de la raíz (arquitectura, capas, convenciones) y mira código
  análogo ya existente: copia el patrón de la feature más parecida en lugar de
  inventar uno nuevo.

### 2. Escribir la spec → `docs/plans/spec-TASK-NN.md`
Diseño detallado, suficiente para implementar sin más decisiones de fondo:

```markdown
# Spec · TASK-NN · <título de la tarea>

**Estado:** En progreso · **Fase:** Especificación · **Creada:** <hoy>
**Plan:** [plan-TASK-NN](plan-TASK-NN.md) · **Tarea:** [TASK-NN](../tasks/TASK-NN-<slug>.md)

## Backend (`backend/src/kanbai/`)
- **Modelos** (`models/`): entidades, columnas (`Mapped[...]`, nullable, default,
  Enum), índices, unicidad, FKs, `owner_id`, `relationship()` y estrategia de carga.
- **Migración** (`migrations/versions/`): qué genera `alembic revision --autogenerate`;
  índices/constraints a revisar a mano; si es destructiva, cómo se rellenan los datos.
- **Schemas** (`schemas/`): `XCreate` / `XUpdate` / `XRead`, validadores, campos
  `Field(...)` con restricciones, qué es read-only.
- **Repositorio / servicio** (`repositories/`, `services/`): consultas y reglas de
  negocio; qué queda fuera del router.
- **Router** (`api/routers/`): rutas bajo `/api/v1/<recurso>`, métodos, `status_code`,
  `response_model`, dependencias (`CurrentUser`, `SessionDep`), filtrado por usuario,
  paginación, códigos de error.

## Frontend (`frontend/src/`)
- **Tipos**: derivados de `src/api/schema.d.ts` (generado del OpenAPI). Si el
  endpoint es nuevo, indica que hay que regenerar con `npm run gen:api`.
- **Capa de datos** (`features/<feature>/api.ts`): funciones de fetch + claves de
  TanStack Query (`queryKey`) e invalidaciones tras mutación.
- **UI** (`features/<feature>/components/`, `routes/`): componentes HeroUI a usar,
  estados de carga/vacío/error, rutas nuevas y entradas de navegación.

## Contrato API
- Endpoint(s), método, request body, response y forma de la paginación
  (`{items, total, page, size}`). El contrato lo manda el backend: primero el
  `response_model`, luego `npm run gen:api`.

## Casos límite y errores
- <validaciones, estados vacíos, permisos, concurrencia, límites de tamaño…>

## Plan de tests
- Backend (`backend/tests/`): casos unitarios y de API (`httpx.AsyncClient` +
  `ASGITransport`), incluyendo los de permisos (404/403 sobre recursos ajenos).
- Frontend (`*.test.tsx`): comportamiento observable con Testing Library.
- Verificación end-to-end si aplica.

## Desviaciones respecto al plan
- <si al detallar cambia algo del plan, anótalo aquí>
```

Mantén la spec **alineada con el contrato**: cualquier campo del `response_model`
debe aparecer en el tipo generado que consume el frontend.

### 3. Reflejar la fase
- En `docs/plans/plan-TASK-NN.md`, actualiza la cabecera: `**Fase:** Especificación`.
- El estado en `STATUS.md` **sigue siendo `En progreso`** (no cambia).

### 4. DETENERTE para el OK
- **No implementes nada.** Resume la spec y dónde está (`docs/plans/spec-TASK-NN.md`).
- Indica el siguiente paso: *«Si das el OK a la especificación, ejecuta
  `/implement-task TASK-NN` para implementar el código.»*

## Si te bloqueas
Si no puedes completar la spec (decisión de diseño que necesita al usuario, info
externa que falta):
- En `STATUS.md`: **Estado** → `Bloqueada`; motivo en **Notas**; recalcula "Resumen"
  y "Última actualización".
- Anota el bloqueo en la spec (sección `## Bloqueo`) y explica qué lo desbloquearía.

## Reglas
- Si el repo es git, no hagas commit salvo que el usuario lo pida.
