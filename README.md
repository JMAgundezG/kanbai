# kanbai

Un tablero kanban donde **agentes y personas trabajan en conjunto**.

No es un gestor de proyectos con un bot pegado encima. Es un tablero pensado desde el
primer modelo de datos para que un agente automático y una persona sean el **mismo tipo
de participante**: los dos son miembros del tablero, los dos mueven tarjetas, los dos
comentan, y de los dos queda registro de qué hicieron y cuándo.

## La idea

El trabajo asistido por agentes suele romperse por los mismos tres sitios:

1. **No se sabe quién hizo qué.** Un agente cambia algo y nadie puede reconstruir por
   qué. → Todo cambio genera un **evento** firmado por su actor.
2. **Dos agentes hacen lo mismo.** Sin coordinación, el trabajo se duplica o se pisa.
   → Una tarjeta se **reclama** con un plazo; mientras esté reclamada, es de quien la
   reclamó.
3. **La persona no puede intervenir a tiempo.** → El tablero es el punto de encuentro:
   la persona ve moverse las tarjetas en vivo, lee el hilo de la tarjeta, y puede
   liberar, reasignar o responder sin salir de la interfaz.

## Conceptos del dominio

| Concepto | Qué es |
|----------|--------|
| **Actor** | Todo el que participa. Es **persona** o **agente**. Es quien firma cada acción. |
| **Persona** | Actor humano. Entra con email y contraseña y usa la interfaz web. |
| **Agente** | Actor automático. Entra con una API key y usa la API. Lo da de alta una persona. |
| **Tablero** | Espacio de trabajo con sus miembros. Un miembro puede ser persona o agente. |
| **Columna** | Fase del flujo dentro de un tablero, ordenada, con límite WIP opcional. |
| **Tarjeta** | La unidad de trabajo: vive en una columna, tiene posición, autor y responsable. |
| **Reclamación** | Bloqueo temporal de una tarjeta por un actor, con vencimiento. Evita el trabajo duplicado. |
| **Comentario** | El hilo de la tarjeta. Es el canal donde una persona y un agente se hablan. |
| **Evento** | Registro inmutable de una acción: qué pasó, sobre qué y quién lo hizo. |

## Invariantes

Estas reglas no se negocian por conveniencia de implementación:

- **Un actor es persona o agente, y el dominio no ramifica por ello.** Si un endpoint
  necesita un `if actor.kind == "agent"` para funcionar, el modelo está mal.
- **Toda escritura queda atribuida a un actor y registrada como evento.**
- **Un agente no tiene más permisos que la persona que lo dio de alta.**
- **Pedir un recurso del que no eres miembro devuelve 404**, nunca 403: no se confirma
  que exista.

## Estado del proyecto

En construcción. El tablero de trabajo vive en
[`docs/tasks/STATUS.md`](docs/tasks/STATUS.md); cada tarea tiene su archivo en
[`docs/tasks/`](docs/tasks/) y su plan y especificación en
[`docs/plans/`](docs/plans/).

## Cómo se trabaja aquí

Todo cambio de funcionalidad pasa por un ciclo de cuatro fases con aprobación humana
entre cada una (planificar → especificar → implementar → completar). El stack, la
estructura y las reglas de código están en [`CLAUDE.md`](CLAUDE.md). **Léelo antes de
tocar nada.**

## Stack

Backend Python 3.14 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL · Alembic, gestionado
con `uv`. Frontend React 19 · TypeScript · Vite · HeroUI v3 sobre Tailwind v4 · TanStack
Query, con los tipos de la API generados desde el OpenAPI del backend.
