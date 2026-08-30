# TASK-04 · Tableros y membresía

**Prioridad:** Alta · **Depende de:** TASK-03

## Objetivo

Dar a los actores un espacio de trabajo: el tablero, con sus miembros. Es la unidad de
autorización de todo el producto — a partir de aquí, "puedes ver esto" significa "eres
miembro de su tablero".

## Alcance

**Entra:**
- Modelos `Board` y `BoardMember` (actor + rol `owner` | `member`).
- CRUD de tableros bajo `/api/v1/boards`, con listado paginado.
- Gestión de miembros: añadir, listar y quitar, **admitiendo actores de cualquier tipo**.
- Filtrado por pertenencia **en la consulta SQL**, no en Python.
- Migración revisada y tests (feliz, validación, acceso ajeno).

**No entra:**
- Columnas y tarjetas (TASK-05, TASK-06).
- Invitaciones por email o alta de personas nuevas.
- Permisos por columna o por tarjeta.

## Criterios de aceptación

- [ ] Un actor crea un tablero y queda como `owner`.
- [ ] `GET /boards` devuelve solo los tableros donde el actor es miembro, con forma
      `{items, total, page, size}` y máximo de `limit` aplicado.
- [ ] Leer, modificar o borrar un tablero ajeno devuelve **404**, no 403.
- [ ] Un `owner` puede añadir como miembro a un agente exactamente igual que a una
      persona.
- [ ] Quitarse a uno mismo siendo el único `owner` está impedido con un error claro.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- La membresía indiferente al tipo de actor es lo que permite que un agente sea miembro
  de pleno derecho; no añadas una tabla aparte para agentes.
- El filtro de pertenencia conviene encapsularlo en el repositorio para reutilizarlo en
  columnas, tarjetas, comentarios y eventos.
