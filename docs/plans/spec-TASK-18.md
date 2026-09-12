# Spec · TASK-18 · Frontend: crear tablero desde la interfaz

**Estado:** En revisión · **Fase:** Code review pendiente
**Tarea:** [TASK-18](../tasks/TASK-18-frontend-crear-tablero.md) ·
**Plan:** [plan-TASK-18](plan-TASK-18.md)

## Backend (`backend/src/kanbai/`)

**Sin cambios.** Ni modelos, ni schemas, ni routers, ni migraciones. `openapi.json` no
se regenera porque el contrato no se toca.

## Contrato consumido

`POST /api/v1/boards` (TASK-04), ya presente en `src/api/schema.d.ts`:

| | |
|---|---|
| Petición | `BoardCreate` = `{ name: string }`, `minLength 1`, `maxLength 200` |
| `201` | `BoardRead` = `{ id, name, created_at, role }`, `role` = `"owner"` |
| `422` | `HTTPValidationError` = `{ detail: [{ loc, msg, type }] }` |

Ojo con el `422`: su `detail` es una **lista**, no una cadena, así que
`extractErrorDetail()` —que solo devuelve cadenas— no sirve para él y devolverá
`undefined`. El mensaje que ve el usuario en ese caso lo pone el cliente, en español, y
nunca se compone con el `msg` de Pydantic (viene en inglés y filtra nombres de campo).

## Frontend (`frontend/src/`)

### `features/board/api.ts` (editado)

Se añade el tipo y la función; nada más cambia en el archivo.

```ts
export type BoardCreate = components['schemas']['BoardCreate']

/** El backend limita el nombre a 200 caracteres (BoardCreate.maxLength). */
export const BOARD_NAME_MAX_LENGTH = 200

export async function createBoard(board: BoardCreate): Promise<Board>
```

- `apiClient.POST('/api/v1/boards', { body: board })`.
- Con `data` → lo devuelve.
- `422` → `throw new Error('El nombre del tablero no es válido: debe tener entre 1 y 200 caracteres.')`.
- Cualquier otro fallo → `throw new Error(extractErrorDetail(error) ?? 'No se pudo crear el tablero.')`.

### `features/board/hooks.ts` (editado)

```ts
export function useCreateBoard()
```

`useMutation({ mutationFn: createBoard })` con
`onSuccess: () => queryClient.invalidateQueries({ queryKey: boardKeys.lists() })`.
No escribe el tablero en la caché a mano (ver el plan).

### `features/board/components/CreateBoardButton.tsx` (nuevo)

Botón + modal de HeroUI. Componente de presentación: la mutación la trae
`useCreateBoard`, no hay `fetch` aquí.

```tsx
export function CreateBoardButton(): ReactElement
```

Estructura:

```tsx
const state = useOverlayState({ onOpenChange: /* al cerrar, limpia el formulario */ })
…
<Modal state={state}>
  {/* Primer hijo = disparador: `Modal` es un DialogTrigger de React Aria, que
      abre el diálogo al pulsarlo sin `onPress` propio. */}
  <Button>Nuevo tablero</Button>
  <Modal.Backdrop>
    <Modal.Container size="sm">
      <Modal.Dialog>
        <Modal.Header><Modal.Heading>Nuevo tablero</Modal.Heading></Modal.Header>
        <Form onSubmit={handleSubmit}>
          <Modal.Body>
            <TextField value={name} onChange={setName} … >
              <Label>Nombre</Label>
              <Input maxLength={BOARD_NAME_MAX_LENGTH} />
            </TextField>
            {errorMessage ? <Alert status="danger">…</Alert> : null}
          </Modal.Body>
          <Modal.Footer>
            <Button variant="ghost" onPress={handleClose}>Cancelar</Button>
            <Button type="submit" isDisabled={isPending}>Crear tablero</Button>
          </Modal.Footer>
        </Form>
      </Modal.Dialog>
    </Modal.Container>
  </Modal.Backdrop>
</Modal>
```

Reglas de comportamiento:

- Estado local: `name` y `validationError`. Nada de estado de servidor duplicado.
- **Sin `isRequired`** (motivo en `LoginForm.tsx`): si `name.trim()` está vacío se
  pone `validationError` y **no se llama a la API**.
- Se envía `name.trim()`.
- Mientras `isPending`, el campo y ambos botones quedan deshabilitados: no hay doble
  alta con doble clic o doble Intro.
- `onSuccess`: se limpia el campo y se cierra el modal.
- En error **el modal sigue abierto y el nombre escrito se conserva**, con el mensaje
  en un `Alert status="danger"`.
- Cancelar o cerrar limpia campo, error y el estado de la mutación (`reset()`), para
  que reabrir no muestre el error anterior. La limpieza cuelga del `onOpenChange` del
  `useOverlayState`, no del botón "Cancelar": así también se limpia al cerrar con
  Escape o pulsando fuera.

### `routes/HomePage.tsx` (editado)

- Se coloca `<CreateBoardButton />` junto al encabezado "Tus tableros", en una fila
  `flex items-center justify-between`.
- Se borra el comentario de cabecera que decía que ninguna tarea cubre crear tableros
  y que la pantalla es de solo lectura: deja de ser cierto.
- El `EmptyState` pasa a decir que se puede crear el primero; el botón del encabezado
  ya está a la vista, así que no se duplica dentro del estado vacío.

### Estilos

Nada nuevo: HeroUI para los componentes, Tailwind para el espaciado, la rejilla de
Bootstrap sigue siendo la de `HomePage`. Ni una clase de Bootstrap fuera de `.row` /
`.col-*`.

## Casos límite y errores

| Caso | Comportamiento |
|------|----------------|
| Nombre vacío o solo espacios | Aviso en español; **no** se llama a la API |
| Nombre con espacios alrededor | Se envía recortado |
| Nombre de más de 200 caracteres | `maxLength` en el `Input` lo impide al teclear; si aun así llega un `422`, mensaje propio en español |
| La API falla (500, red caída) | `Alert` en español, modal abierto, nombre conservado |
| Sesión caducada (401) | `apiClient` ya emite el evento de no autorizado (`lib/authEvents.ts`) y el armazón lleva al acceso; aquí no se trata aparte |
| Doble envío | Botón y campo deshabilitados mientras `isPending` |
| Cerrar y reabrir tras un error | Formulario limpio, sin el error anterior |

## Plan de tests

`features/board/components/CreateBoardButton.test.tsx`, con el patrón ya usado en
`LoginForm.test.tsx` (`QueryClientProvider` propio + `vi.spyOn(globalThis, 'fetch')`),
probando lo que ve el usuario (roles y texto), no la implementación:

1. **Alta correcta**: abrir el modal, escribir "Tablero de producto", enviar →
   `fetch` recibe `POST /api/v1/boards` con `{"name":"Tablero de producto"}` y el
   modal se cierra.
2. **Envío vacío**: abrir y enviar sin escribir → aparece el aviso en español y
   `fetch` **no** se ha llamado.
3. **Fallo de la API**: `500` → mensaje en español visible y el nombre sigue en el
   campo.
4. **Recorte**: se envía `name` sin espacios alrededor (se comprueba en el cuerpo de
   la petición del caso 1, escribiendo el nombre con espacios).
5. **`422`**: el mensaje visible es el propio, nunca el `msg` de Pydantic.
6. **Teclado**: `Tab` lleva el foco al botón, `Intro` abre el diálogo y `Escape` lo
   cierra, sin tocar el ratón.

`routes/HomePage.test.tsx` (nuevo) cubre el criterio de aceptación de punta a punta:
con el listado devolviendo vacío hasta el `POST` y el tablero después, se comprueba
que tras crear aparece el enlace al tablero **sin recargar** — es decir, que la
invalidación de `boardKeys.lists()` hace su trabajo.

La puerta es `npm run check` desde `frontend/`.

## Desviaciones respecto al plan

- El helper que lee el cuerpo de la petición en los tests toma el `Request`, no un
  `(url, init)`: `openapi-fetch` llama a `fetch` con un único `Request`.
- El botón "Cancelar" usa `onPress={() => { state.close() }}` en vez de
  `onPress={state.close}`: la regla `@typescript-eslint/unbound-method` rechaza pasar
  el método suelto.
- Se añade el test de `HomePage` descrito arriba, que el plan no preveía: sin él
  ningún test cubría el criterio "aparece en la lista sin recargar", que era el
  principal de la tarea.
