# Estado del tablero — kanbai

**Última actualización: 2026-08-30**

Estados válidos: `Pendiente · En progreso · En revisión · Bloqueada · Completada`.
Una tarea por archivo en `docs/tasks/TASK-NN-<slug>.md` (plantilla:
[`_plantilla-tarea.md`](_plantilla-tarea.md)).

| ID | Tarea | Prioridad | Depende de | Estado | Responsable | Notas |
|----|-------|-----------|------------|--------|-------------|-------|
| TASK-01 | [Scaffold del backend (uv + FastAPI)](TASK-01-scaffold-backend.md) | Alta | — | Completada | Claude | Base de todo lo demás · [plan](../plans/plan-TASK-01.md) · [spec](../plans/spec-TASK-01.md) · [feature](../features/health.md) |
| TASK-02 | [Scaffold del frontend (Vite + React + HeroUI)](TASK-02-scaffold-frontend.md) | Alta | TASK-01 | Completada | Claude | [plan](../plans/plan-TASK-02.md) · [spec](../plans/spec-TASK-02.md) · [feature](../features/estilos-frontend.md) |
| TASK-03 | [Actores y autenticación de personas](TASK-03-actores-y-sesion.md) | Alta | TASK-01 | Completada | Claude | El actor (persona\|agente) es la pieza central del dominio · [plan](../plans/plan-TASK-03.md) · [spec](../plans/spec-TASK-03.md) · [feature](../features/actores-y-autenticacion.md) |
| TASK-04 | [Tableros y membresía](TASK-04-tableros-y-membresia.md) | Alta | TASK-03 | Pendiente | — | Unidad de autorización de todo el producto · desbloqueada por TASK-03 |
| TASK-05 | [Columnas del tablero](TASK-05-columnas.md) | Alta | TASK-04 | Pendiente | — | Define el esquema de posiciones que reutiliza TASK-06 |
| TASK-06 | [Tarjetas: CRUD y movimiento](TASK-06-tarjetas.md) | Alta | TASK-05 | Pendiente | — | Movimiento atómico; test de concurrencia obligatorio |
| TASK-07 | [Frontend: sesión y armazón](TASK-07-frontend-sesion.md) | Alta | TASK-02, TASK-03 | Pendiente | — | Acceso, rutas protegidas y layout común · desbloqueada por TASK-03 |
| TASK-08 | [Frontend: tablero con arrastrar y soltar](TASK-08-frontend-tablero.md) | Alta | TASK-06, TASK-07 | Pendiente | — | Arrastrar accesible, también con teclado |
| TASK-09 | [Agentes como actores: alta y API keys](TASK-09-agentes-y-api-keys.md) | Alta | TASK-03 | Pendiente | — | **La tarea que hace distinto a kanbai**; ningún dominio paralelo · desbloqueada por TASK-03 |
| TASK-10 | [Asignación y reclamación de tarjetas](TASK-10-asignacion-y-reclamacion.md) | Alta | TASK-06, TASK-09 | Pendiente | — | Evita el trabajo duplicado entre agentes; reclamación con vencimiento |
| TASK-11 | [Comentarios en tarjetas](TASK-11-comentarios.md) | Alta | TASK-06 | Pendiente | — | El canal de conversación persona↔agente |
| TASK-12 | [Registro de actividad (eventos)](TASK-12-registro-de-actividad.md) | Alta | TASK-06, TASK-09 | Pendiente | — | Trazabilidad; alimenta el tiempo real de TASK-14 |
| TASK-13 | [API de agentes: cola de trabajo](TASK-13-api-de-agentes.md) | Alta | TASK-10, TASK-11, TASK-12 | Pendiente | — | Cierra el bucle: pedir → reclamar → comentar → mover |
| TASK-14 | [Tiempo real: eventos en vivo](TASK-14-tiempo-real.md) | Media | TASK-08, TASK-12 | Pendiente | — | SSE; que se vea trabajar al agente sin recargar |
| TASK-15 | [Frontend: detalle de tarjeta](TASK-15-frontend-detalle-tarjeta.md) | Media | TASK-08, TASK-11, TASK-12 | Pendiente | — | Hilo, actividad y distintivo persona/agente |
| TASK-16 | [Frontend: gestión de agentes](TASK-16-frontend-gestion-agentes.md) | Media | TASK-07, TASK-09 | Pendiente | — | Alta, API key visible una sola vez, revocación |
| TASK-17 | [Integración continua y entorno](TASK-17-ci-y-entorno.md) | Media | TASK-01, TASK-02 | Pendiente | — | **Desbloqueada** por TASK-01 y TASK-02: ya se puede arrancar |

## Resumen

| Estado | Nº |
|--------|----|
| Pendiente | 14 |
| En progreso | 0 |
| En revisión | 0 |
| Bloqueada | 0 |
| Completada | 3 |
| **Total** | **17** |

## Orden sugerido

**Fase 0 — cimientos**
1. TASK-01 — scaffold del backend
2. TASK-02 — scaffold del frontend
3. TASK-17 — integración continua y entorno *(en cuanto 01 y 02 estén cerradas)*

**Fase 1 — el tablero funciona con personas**
4. TASK-03 — actores y sesión
5. TASK-04 — tableros y membresía
6. TASK-05 — columnas
7. TASK-06 — tarjetas
8. TASK-07 — frontend: sesión y armazón
9. TASK-08 — frontend: tablero con arrastrar y soltar

**Fase 2 — entran los agentes**
10. TASK-09 — agentes y API keys
11. TASK-10 — asignación y reclamación
12. TASK-11 — comentarios
13. TASK-12 — registro de actividad
14. TASK-13 — API de agentes

**Fase 3 — la colaboración se ve**
15. TASK-14 — tiempo real
16. TASK-15 — detalle de tarjeta
17. TASK-16 — gestión de agentes

Las tareas de prioridad **Alta** (TASK-01 a TASK-13) son el corte mínimo para que
kanbai sea lo que dice ser: un tablero donde un agente y una persona trabajan sobre las
mismas tarjetas. Las de prioridad **Media** completan la experiencia y el entorno.
