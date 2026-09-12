# Plan · TASK-18 · Frontend: crear tablero desde la interfaz

**Estado:** En revisión · **Fase:** Code review pendiente
**Tarea:** [TASK-18](../tasks/TASK-18-frontend-crear-tablero.md)

## Objetivo

Añadir a la pantalla de inicio el botón que crea un tablero, para que dejar de
depender de llamadas a la API a mano y que el estado vacío ("Todavía no perteneces a
ningún tablero") tenga salida.

## Enfoque

Trabajo **exclusivamente de frontend**. `POST /api/v1/boards` existe desde TASK-04 y
ya está en `backend/openapi.json` y en `src/api/schema.d.ts`: recibe
`BoardCreate {name}` (1–200 caracteres) y devuelve `BoardRead` con el actor como
`owner`. No hay migración, ni cambio de contrato, ni regeneración de tipos; si algo de
eso hiciera falta, la tarea estaría mal planteada.

La pieza nueva vive en la feature `board`, que ya existe (`api.ts`, `hooks.ts`,
`components/`), siguiendo el reparto del repo: la llamada en `api.ts`, la mutación y
la invalidación de caché en `hooks.ts`, y un componente de presentación que no llama
a la API. `HomePage` se limita a colocarlo.

**Modal frente a formulario en línea.** Se elige **modal de HeroUI**
(`Modal` + `useOverlayState`, ya en `@heroui/react@3.2.4`): AGENTS.md § 5 obliga a
usar HeroUI para los componentes interactivos —modales incluidos— y HeroUI se apoya en
React Aria, que ya da el foco atrapado, el cierre con Escape y el `aria-labelledby`
del diálogo sin código propio. Un formulario en línea evitaría el diálogo, pero
dejaría el foco y el anuncio al lector de pantalla en nuestras manos para ahorrar muy
poco. El formulario de dentro copia el patrón ya probado de
`features/auth/components/LoginForm.tsx`.

**Validación.** Igual que en `LoginForm`, sin `isRequired`: la validación nativa del
navegador habla en el idioma del sistema operativo, no en español. El nombre se
comprueba a mano (vacío o solo espacios → aviso propio, sin llamar a la API) y se
envía recortado con `trim()`.

**Caché.** Tras crear, se invalida `boardKeys.lists()` para que la lista se refresque.
No se escribe el tablero en la caché a mano: el listado está paginado y ordenado por
el backend, y colarle un elemento por nuestra cuenta es arriesgarse a mostrar un orden
que no es el real.

## Alcance

Entra y no entra: lo fijado en [TASK-18](../tasks/TASK-18-frontend-crear-tablero.md).
En particular **no** se navega al tablero recién creado: la lista es la confirmación
visible, y navegar sería una decisión de producto que la tarea no pide.

## Criterios de aceptación

Los de la tarea, sin cambios.

## Plan de verificación

- `npm run check` desde `frontend/` (eslint + `tsc -b --noEmit` + Vitest).
- Tests nuevos del componente: alta correcta (aparece en la lista), envío vacío (no
  llama a `fetch`) y fallo de la API (mensaje en español, el nombre no se pierde).
- No se toca `backend/`, así que `uv run poe check` no es parte de esta tarea; se
  comprueba que `git status` no muestra ningún archivo bajo `backend/`.

## Riesgos / decisiones abiertas

- **El modal de HeroUI v3 en jsdom.** La API compuesta (`Modal.Backdrop` →
  `Modal.Container` → `Modal.Dialog`) renderiza en un portal. Si los tests no
  alcanzaran el diálogo, la salida es probar el formulario por separado del modal, no
  reimplementar el diálogo a mano.
- **Nombres duplicados.** El backend acepta dos tableros con el mismo nombre; no se
  añade una comprobación en el cliente que el dominio no exige.
