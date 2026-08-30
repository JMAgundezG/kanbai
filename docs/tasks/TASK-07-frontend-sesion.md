# TASK-07 · Frontend: sesión y armazón de la aplicación

**Prioridad:** Alta · **Depende de:** TASK-02, TASK-03

## Objetivo

Que una persona pueda entrar en kanbai y moverse por la aplicación: pantalla de acceso,
rutas protegidas y el armazón visual común sobre el que se montarán el tablero y el
resto de vistas.

## Alcance

**Entra:**
- Pantalla de acceso con componentes HeroUI y validación de formulario.
- Cliente de API con envío de credenciales y manejo centralizado del `401`.
- Rutas protegidas con React Router y redirección a la pantalla de acceso.
- Armazón: barra superior con el actor actual y salir; contenedor con la rejilla de
  Bootstrap.
- Estados de carga y error contemplados en todas las vistas de la tarea.
- Tests de Testing Library: acceso correcto, credenciales inválidas, redirección.

**No entra:**
- Vista del tablero (TASK-08) y detalle de tarjeta (TASK-15).
- Gestión de agentes (TASK-16), registro de usuarios, perfil.

## Criterios de aceptación

- [ ] Un acceso correcto navega a la vista principal y la sesión sobrevive a recargar.
- [ ] Credenciales inválidas muestran el mensaje de error **en español**, sin pantalla
      en blanco.
- [ ] Entrar a una ruta protegida sin sesión redirige al acceso.
- [ ] Todos los tipos de datos de la API vienen de `src/api/schema.d.ts`: **no hay
      ninguna `interface` escrita a mano** que refleje una respuesta.
- [ ] `npm run check` en verde.

## Notas técnicas

- Los componentes interactivos son de HeroUI, sin markup de Bootstrap (`CLAUDE.md` § 5).
- El estado de sesión se consulta con TanStack Query (`['auth','me']`), no se duplica en
  `useState`.
