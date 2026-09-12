# TASK-18 · Frontend: crear tablero desde la interfaz

**Prioridad:** Alta · **Depende de:** TASK-04, TASK-07

## Objetivo

Hoy un tablero solo se puede crear llamando a la API a mano: la pantalla de inicio
lista los tableros del actor pero no deja crear ninguno, así que una persona recién
registrada se queda ante un estado vacío sin salida. Esta tarea añade el botón que
cierra ese hueco y convierte la pantalla de inicio en el punto de entrada real al
producto.

## Alcance

**Entra:**
- Botón "Nuevo tablero" en la pantalla de inicio, con el formulario de nombre que
  abre, dentro de la feature `board`.
- `createBoard` en `features/board/api.ts` contra `POST /api/v1/boards`, ya existente
  en el contrato, y su hook de mutación con invalidación de `boardKeys.lists()`.
- Estados de envío, validación en cliente y error de API, en español.
- Tests sobre lo que ve el usuario: alta correcta, envío vacío y fallo de la API.

**No entra:**
- Cualquier cambio en el backend, el contrato o `schema.d.ts`: el endpoint ya existe.
- Renombrar, archivar o borrar tableros, y la gestión de miembros.
- Crear columnas iniciales desde la interfaz: el tablero nace como lo deja el backend.
- Navegar automáticamente al tablero recién creado.

## Criterios de aceptación

- [x] La pantalla de inicio ofrece un control "Nuevo tablero" operable con teclado.
- [x] Enviar un nombre válido crea el tablero y este aparece en la lista sin recargar
      la página.
- [x] Enviar el formulario vacío o con solo espacios **no llama a la API** y muestra un
      aviso en español.
- [x] Si la API falla, se muestra un mensaje en español y el nombre escrito no se
      pierde.
- [x] Mientras la petición está en vuelo el envío queda deshabilitado, sin doble alta.
- [x] El estado vacío ("Todavía no perteneces a ningún tablero") deja de ser un callejón
      sin salida: desde él se puede crear el primer tablero.
- [x] `npm run check` en verde.

## Notas técnicas

- `POST /api/v1/boards` ya existe (TASK-04): recibe `BoardCreate {name}` (1–200
  caracteres) y devuelve `BoardRead` con el actor como `owner`. No hay cambio de
  contrato, así que no se regenera `schema.d.ts`.
- Componentes interactivos con HeroUI, nunca markup propio ni de Bootstrap
  (`AGENTS.md` § 5); el patrón de formulario a seguir es
  `features/auth/components/LoginForm.tsx`, incluida la razón para no usar `isRequired`.
- Componente tonto + hook con la lógica: el componente no llama a la API.
