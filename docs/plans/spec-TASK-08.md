# Spec · TASK-08 · Frontend: vista del tablero con arrastrar y soltar

**Estado:** Completada · **Fase:** Cerrada · **Cerrado:** 2026-09-09
**Plan:** [plan-TASK-08](plan-TASK-08.md) · **Tarea:** [TASK-08](../tasks/TASK-08-frontend-tablero.md)

## Backend (`backend/src/kanbai/`)

Sin cambios. Se consumen los endpoints ya existentes de TASK-04/05/06:

- `GET /api/v1/boards` — `200 Page[BoardRead]` (tableros del actor).
- `GET /api/v1/boards/{board_id}` — `200 BoardRead` / `404`.
- `GET /api/v1/boards/{board_id}/columns` — `200 Page[ColumnRead]`, orden por
  `position`.
- `GET /api/v1/boards/{board_id}/cards` — `200 Page[CardRead]`, orden por
  `(posición de columna, posición de tarjeta)`.
- `POST /api/v1/boards/{board_id}/cards/{card_id}/move` — body
  `CardMove {column_id, position}` (posición = índice deseado, base 0) →
  `200 CardRead` / `404` / `409` (límite WIP) / `422`.

Único paso de backend: `npm run gen:api` desde `frontend/`, porque hasta ahora nadie
había consumido estos tres recursos desde el frontend (mismo criterio que TASK-04/05/06
dejaron anotado en `docs/features/*`).

## Contrato consumido

```
BoardRead   {id, name, created_at, role: "owner" | "member"}
ColumnRead  {id, board_id, name, wip_limit: number | null, position, created_at}
CardRead    {id, board_id, column_id, title, description: string | null, position,
             created_by_actor_id, created_at, updated_at}
CardMove    {column_id, position: integer >= 0}
Page[T]     {items: T[], total, page, size}
```

Todos los tipos se importan de `components['schemas']` en `src/api/schema.d.ts` tras
`npm run gen:api`. Ninguna interfaz a mano.

Paginación: el tablero de kanbai no pagina columnas ni tarjetas en pantalla (se ve el
tablero completo). Se pide `size=100` (el máximo que acepta `PaginationParams`) en una
sola página para columnas y tarjetas; un tablero con más de 100 columnas o de 100
tarjetas en total queda fuera de alcance de esta tarea (no hay ningún tablero de
prueba ni caso de uso actual que lo alcance; se anota como límite conocido). Igual
para el listado de tableros de `HomePage`.

## Dependencia nueva: `react-aria-components`

Ya está presente en `frontend/node_modules` como dependencia transitiva de
`@heroui/react` (peer dependency, versión `1.20.0`, confirmado en
`node_modules/react-aria-components/package.json`). Esta tarea la declara como
dependencia **directa** en `package.json` (`^1.20.0`) porque el código de la
aplicación importa de ella directamente (`GridList`, `GridListItem`, `useDragAndDrop`)
— depender en el código de un paquete no declarado y presente solo por transitividad
es fragil: dejaría de estar garantizado si `@heroui/react` cambia su propio rango de
peer dependencies en una versión futura. Ninguna dependencia nueva de verdad: incluida
por AGENTS.md § 7 porque toca `package.json`, no porque añada peso real al bundle.

## Frontend (`frontend/src/`)

### `features/board/api.ts` (nuevo)

```ts
export type Board = components['schemas']['BoardRead']
export type BoardColumn = components['schemas']['ColumnRead']
export type Card = components['schemas']['CardRead']
export type CardMove = components['schemas']['CardMove']

export const boardKeys = {
  all: ['boards'] as const,
  lists: () => [...boardKeys.all, 'list'] as const,
  detail: (boardId: string) => [...boardKeys.all, 'detail', boardId] as const,
  columns: (boardId: string) => [...boardKeys.detail(boardId), 'columns'] as const,
  cards: (boardId: string) => [...boardKeys.detail(boardId), 'cards'] as const,
}

const MAX_PAGE_SIZE = 100

export async function fetchBoards(): Promise<Board[]>
export async function fetchBoard(boardId: string): Promise<Board>
export async function fetchBoardColumns(boardId: string): Promise<BoardColumn[]>
export async function fetchBoardCards(boardId: string): Promise<Card[]>
export async function moveCard(
  boardId: string,
  cardId: string,
  move: CardMove,
): Promise<Card>
```

Cada fetcher sigue el patrón de `features/health/api.ts` /
`features/auth/api.ts`: `apiClient.GET(...)`, comprobar `!data || !response.ok` y
lanzar `Error` con mensaje en español (`No se pudieron cargar los tableros.` /
`No se pudo cargar el tablero.` / `No se pudieron cargar las columnas.` /
`No se pudieron cargar las tarjetas.`); un `404` en `fetchBoard` / `fetchBoardColumns`
/ `fetchBoardCards` es un fallo real aquí (a diferencia de `/auth/me`): no hay ningún
estado "tablero ausente" válido para esta pantalla, así que cae en el mismo `Error`
genérico, que `BoardPage` muestra como el estado de error de la vista (no hay
distinción especial "tablero ajeno" pedida por los criterios de aceptación).

`moveCard` extrae `detail` del cuerpo de error igual que `login` en `features/auth/api.ts`
(mensaje del backend, ya en español) para los casos `404`/`409`/`422`; con `detail`
ausente, mensaje de reserva `No se pudo mover la tarjeta.`.

### `features/board/hooks.ts` (nuevo)

```ts
export function useBoards()
export function useBoard(boardId: string)
export function useBoardColumns(boardId: string)
export function useBoardCards(boardId: string)
export function useMoveCard(boardId: string)
```

- `useBoards`, `useBoard`, `useBoardColumns`, `useBoardCards`: `useQuery` estándar,
  `queryKey` de `boardKeys`, `enabled: Boolean(boardId)` donde aplique.
- `useMoveCard(boardId)` — la mutación optimista, el corazón de la tarea:

```ts
export function useMoveCard(boardId: string) {
  const queryClient = useQueryClient()
  const cardsKey = boardKeys.cards(boardId)

  return useMutation({
    mutationFn: ({ cardId, move }: { cardId: string; move: CardMove }) =>
      moveCard(boardId, cardId, move),

    // targetIndex: índice ya calculado (dentro de la columna destino) por quien
    // dispara la mutación — el propio hook de arrastrar y soltar lo conoce mejor
    // que un recálculo aquí a partir de la caché.
    onMutate: async ({ cardId, move }) => {
      await queryClient.cancelQueries({ queryKey: cardsKey })
      const previousCards = queryClient.getQueryData<Card[]>(cardsKey)

      if (previousCards) {
        queryClient.setQueryData<Card[]>(
          cardsKey,
          moveCardOptimistically(previousCards, cardId, move.column_id, move.position),
        )
      }

      return { previousCards }
    },

    onError: (_error, _variables, context) => {
      if (context?.previousCards) {
        queryClient.setQueryData(cardsKey, context.previousCards)
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: cardsKey })
    },
  })
}
```

`moveCardOptimistically` (función pura, exportada desde `hooks.ts` o un `lib.ts` de la
propia feature, con su propio test unitario) recoloca la tarjeta dentro del array
plano de `Card[]` que devuelve la API: la quita de su posición actual, le cambia
`column_id`, y la reinserta en el índice global correspondiente al `targetIndex`
dentro de las tarjetas de `targetColumnId` (o al final de esa columna si
`targetIndex` es mayor que el número de tarjetas que tiene). Solo reordena el array
para que la UI pinte la tarjeta en el sitio correcto al instante — no recalcula
`position` (el flotante real lo decide el backend; `onSettled` refresca con
`invalidateQueries` y sustituye cualquier valor provisional por el real, tanto en
éxito como en error).

`onError` no muestra el aviso directamente: deja que el componente lea
`moveCardMutation.error` (mensaje en español ya extraído por `api.ts`) y pinte un
`Alert` de HeroUI. `mutation.error` se resetea solo con la siguiente llamada a
`mutate`, que es exactamente cuándo debe desaparecer el aviso anterior.

### `features/board/components/BoardCard.tsx` (nuevo)

Tonta: recibe `card: Card` por props, pinta título (y descripción si existe,
recortada) dentro de un `Card` de HeroUI. No importa `hooks.ts` ni `api.ts` — no llama
a la API, como exige la tarea.

### `features/board/components/BoardColumnList.tsx` (nuevo, el componente con la lógica de arrastrar y soltar)

Recibe por props: la columna (`BoardColumn`), sus tarjetas ya filtradas y ordenadas
(`Card[]`), y `onMoveCard(cardId: string, targetIndex: number): void` (lo llama con la
columna de destino ya fijada al id de esta propia columna — la función se construye
en `BoardPage` cerrando sobre `boardId` y la mutación).

```tsx
function BoardColumnList({ column, cards, onMoveCard }: Props) {
  const { dragAndDropHooks } = useDragAndDrop({
    getItems: (keys) =>
      [...keys].map((key) => ({ 'text/plain': String(key) })),

    // Arrastre dentro de la misma columna: reordenar.
    onReorder(event) {
      const index = targetIndexFor(cards, event.target)
      const [cardId] = event.keys
      onMoveCard(String(cardId), index)
    },

    // Arrastre desde otra columna, soltado entre tarjetas (o tras la última).
    async onInsert(event) {
      const index = targetIndexFor(cards, event.target)
      const cardId = await readCardId(event.items)
      onMoveCard(cardId, index)
    },

    // Arrastre desde otra columna, soltado en una columna sin tarjetas.
    async onRootDrop(event) {
      const cardId = await readCardId(event.items)
      onMoveCard(cardId, 0)
    },

    getDropOperation: () => 'move',
  })

  return (
    <GridList
      aria-label={`Tarjetas de la columna ${column.name}`}
      items={cards}
      dragAndDropHooks={dragAndDropHooks}
      renderEmptyState={() => <EmptyColumnState />}
      className="flex min-h-24 flex-col gap-2"
    >
      {(card) => (
        <GridListItem key={card.id} textValue={card.title}>
          <BoardCard card={card} />
        </GridListItem>
      )}
    </GridList>
  )
}
```

- `targetIndexFor(cards, target: ItemDropTarget)` — helper puro: busca el índice de
  `target.key` en `cards` y suma 0/1 según `target.dropPosition` (`'before'` /
  `'after'`).
- `readCardId(items: DropItem[])` — helper async: `items[0].kind === 'text'` (invariante
  de esta app, siempre lo es) → `await items[0].getText('text/plain')`.
- **Cada columna llama a su propia `useDragAndDrop`** en vez de compartir una única
  instancia entre columnas — la decisión central de esta spec. `onReorder` solo se
  dispara cuando el arrastre empieza y termina en el mismo `GridList`; un arrastre
  entre columnas distintas (dos instancias de `useDragAndDrop` distintas) llega como
  `onInsert` (soltado entre tarjetas) o `onRootDrop` (columna vacía) a la columna que
  lo recibe, que ya sabe quién es (`column.id`, cerrado en el closure de
  `onMoveCard`) sin necesitar ningún id de columna viajando por el propio evento.
  Cada `GridList` sigue aceptando arrastres que se originan en cualquier otra columna
  porque ninguna restringe `acceptedDragTypes`.
- **Teclado, gratis**: al enfocar una tarjeta dentro de un `GridList` con
  `dragAndDropHooks`, Intro/Espacio entra en "modo arrastre"; Tab/flechas mueven el
  objetivo de soltado (incluida otra columna); Intro/Espacio confirma soltar; Escape
  cancela. Nada de esto es código propio — es el comportamiento de
  `react-aria-components`, que es exactamente por lo que la tarea prefiere esta
  librería.
- `EmptyColumnState` — HeroUI `EmptyState` con un texto («Sin tarjetas») dentro del
  `renderEmptyState` del propio `GridList`: la zona sigue siendo un destino de
  soltado válido (`onRootDrop`) aunque esté vacía.

### `routes/BoardPage.tsx` (nuevo)

```tsx
export function BoardPage() {
  const { boardId } = useParams<{ boardId: string }>()
  // boardId siempre presente: la ruta lo declara como segmento obligatorio.
  const board = useBoard(boardId!)
  const columns = useBoardColumns(boardId!)
  const cards = useBoardCards(boardId!)
  const moveCardMutation = useMoveCard(boardId!)

  // Combina los tres useQuery: isPending si cualquiera está cargando su primera
  // vez, isError si cualquiera falló. Mismo patrón que ProtectedRoute: los tres
  // estados (carga/vacío/error) son explícitos, ninguno implícito.
  ...

  function handleMoveCard(columnId: string, cardId: string, targetIndex: number) {
    moveCardMutation.mutate({ cardId, move: { column_id: columnId, position: targetIndex } })
  }

  return (
    <div>
      <h2>{board.data?.name}</h2>
      {moveCardMutation.isError && (
        <Alert status="danger">
          <Alert.Title>No se pudo mover la tarjeta</Alert.Title>
          <Alert.Description>{moveCardMutation.error.message}</Alert.Description>
        </Alert>
      )}
      {columns.data?.length === 0 ? (
        <EmptyBoardState />
      ) : (
        <div className="row g-4">
          {columns.data?.map((column) => (
            <div key={column.id} className="col-12 col-md">
              <h3>{column.name}</h3>
              <BoardColumnList
                column={column}
                cards={cardsByColumn.get(column.id) ?? []}
                onMoveCard={(cardId, targetIndex) =>
                  handleMoveCard(column.id, cardId, targetIndex)
                }
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

`cardsByColumn` — `useMemo` que agrupa `cards.data` (array plano ordenado por la API)
por `column_id`, conservando el orden relativo que trae el backend (que ya es el
orden por `position`); es la fuente de la que lee cada `BoardColumnList`, y también la
que reescribe `moveCardOptimistically` dentro de la mutación, así que optimista y real
pintan exactamente igual.

`.row g-4` / `.col-12 col-md` — rejilla de Bootstrap (única pieza de Bootstrap usada,
por `estilos-frontend.md`): cada columna ocupa el ancho completo en móvil y se reparte
a partes iguales en pantallas medianas o mayores, sin límite fijo de columnas.

Un tablero sin columnas (caso extremo, no debería darse — TASK-05 siembra siempre
tres) muestra el mismo `EmptyBoardState` que un tablero sin ninguna tarjeta en
ninguna columna; el criterio de aceptación pide "tablero sin tarjetas", que es el
caso normal cuando el tablero tiene columnas pero todas vacías — ahí cada columna
individual ya muestra su propio `EmptyColumnState` (más útil que un único mensaje
genérico, porque columnas con nombre real siguen siendo la referencia visual).

### `routes/HomePage.tsx` (editado)

Pasa de la tarjeta de estado del backend a listar los tableros del actor
(`useBoards`), con los tres estados explícitos (carga: `Spinner`; error: `Alert`;
vacío: `EmptyState` de HeroUI, «Todavía no perteneces a ningún tablero.»). Cada
tablero es un enlace (`Link` de `react-router`) a `/boards/:boardId`. Sin crear
tableros desde aquí (fuera de alcance, ver plan).

`BackendStatusCard` (TASK-02) se conserva, más pequeña, como diagnóstico secundario
bajo la lista de tableros — sigue siendo útil y ningún criterio pide quitarla.

### `App.tsx` (editado)

```tsx
{
  path: '/',
  element: <ProtectedRoute />,
  children: [
    {
      element: <AppLayout />,
      children: [
        { index: true, element: <HomePage /> },
        { path: 'boards/:boardId', element: <BoardPage /> },
      ],
    },
  ],
}
```

## Casos límite y errores

- **Tablero ajeno o inexistente** (`/boards/{id}` con un id que no es del actor):
  `fetchBoard` lanza (404 tratado como error real, ver arriba) → `BoardPage` muestra
  el estado de error, sin filtrar si es "no existe" o "no eres miembro" (mismo
  principio 404-sin-confirmar de AGENTS.md § 4, ya aplicado por el backend).
- **Movimiento rechazado por límite WIP** (`409`): la tarjeta vuelve a su columna
  original (rollback de `onMutate`) y el mensaje del backend
  (`No se pueden añadir más tarjetas a «…»: ha alcanzado su límite de N tarjetas.`) se
  ve tal cual en el `Alert`.
- **Movimiento contra una tarjeta borrada por otra persona** (`404` de `/move`):
  mismo rollback; mensaje de reserva en español.
- **Doble arrastre rápido**: el tablero bloquea síncronamente un segundo movimiento
  mientras el primero está pendiente. `isDisabled` deshabilita el arrastre y la
  mutación espera la invalidación de tarjetas antes de volver a habilitarlo.
  TanStack Query no serializa mutaciones por instancia automáticamente; esta
  protección evita que dos snapshots optimistas se sobrescriban al revertir.
- **Tarjeta soltada en la misma posición de la que salió**: el backend igualmente
  recalcula `position` (posible recompactación); `onSettled` invalida y refresca, sin
  tratamiento especial.
- **`targetIndex` fuera de rango** (columna con menos tarjetas de las que la UI creía,
  por un cambio concurrente): el backend ajusta al final de la columna (documentado
  en `tarjetas.md`); la reconciliación de `onSettled` corrige cualquier posición
  optimista que se hubiera quedado corta.
- **Tablero, columna o tarjeta sin datos aún (`isPending` de cualquiera de los tres
  `useQuery` de `BoardPage`)**: `Spinner` centrado, sin pintar columnas a medias.

## Plan de tests

`frontend/src/**/*.test.tsx` con Testing Library, mock de `globalThis.fetch` (patrón
de `BackendStatusCard.test.tsx` / `LoginForm.test.tsx`), y tests unitarios puros para
la lógica sin DOM:

- `features/board/hooks.test.ts` (o `lib.test.ts` si `moveCardOptimistically` se
  extrae a un módulo propio): recoloca correctamente una tarjeta movida a otra
  columna en un índice concreto, al final de una columna vacía, y dentro de la misma
  columna.
- `features/board/components/BoardCard.test.tsx`: pinta título y descripción; sin
  descripción no revienta.
- `routes/BoardPage.test.tsx`:
  - Camino feliz: `fetch` responde tablero + columnas + tarjetas → se ven los nombres
    de columna y los títulos de tarjeta (roles/texto, no snapshots).
  - Vacío: tarjetas `[]` → se ve el texto del estado vacío de cada columna.
  - Error: `fetch` de columnas responde `500` → se ve el `Alert` de error, no una
    pantalla en blanco.
  - Movimiento por teclado: con `user-event`, foco en una tarjeta, `{Enter}` (entra en
    modo arrastre), navegar con flechas/Tab al destino, `{Enter}` (soltar) — se
    comprueba que `fetch` recibe la llamada `POST .../move` con el `column_id`
    esperado. Sigue el patrón de interacción por teclado que ya usa
    `react-aria-components` en sus propios tests, adaptado a Testing Library.
  - Reversión: `fetch` de `/move` responde `409` con `detail` → tras el intento de
    mover, la tarjeta vuelve a aparecer en su columna original y se ve el `Alert` con
    el mensaje del backend.
- Verificación end-to-end manual (fuera de Vitest, obligatoria por el encargo):
  backend real levantado, tablero/columnas/tarjetas de prueba creados contra la API
  real, navegador Chrome headless conducido por el protocolo DevTools desde un script
  de Node — arrastrar entre columnas persiste tras recargar, la misma operación solo
  con teclado, reversión visual ante un fallo forzado de la API, tablero sin tarjetas
  con estado vacío, rejilla de Bootstrap sin romper HeroUI.

## Desviaciones respecto al plan

1. **El arrastre por teclado necesita un asa explícita, no sale gratis.** La spec daba
   por hecho que enfocar una tarjeta dentro de un `GridList` con `dragAndDropHooks` y
   pulsar Intro bastaba. No es así: `react-aria-components` construye cada
   `GridListItem` con `hasDragButton: true`
   (`dist/private/GridList.mjs`), y `useDrag` solo instala los manejadores de teclado
   sobre la propia fila **cuando no hay botón de arrastre**. Con ese valor fijado, el
   único punto de entrada por teclado es el slot `drag`, que la aplicación tiene que
   rellenar. `BoardColumnList` renderiza ahora un `Button slot="drag"` dentro de cada
   `GridListItem`. El recorrido por teclado queda: foco en la tarjeta → `→` hasta el
   asa → `Intro` para empezar → `Tab` entre destinos → `Intro` para soltar.
   `react-aria` le pone `pointer-events: none` al asa, así que el arrastre con ratón
   sigue empezando en la fila, igual que antes.

2. **`I18nProvider locale="es-ES"` en `App.tsx`.** Las descripciones y los avisos de
   `aria-live` del arrastre los genera `react-aria` con sus propias traducciones, y
   sin locale explícito sigue la del navegador: una interfaz en español anunciando
   *«Press Enter to start dragging»* a un lector de pantalla. Con el proveedor, el
   recorrido completo se anuncia en español (comprobado en navegador: «Pulse Intro
   para empezar a arrastrar», «Se ha empezado a arrastrar…», «Colocación
   finalizada»). El `aria-label` del asa se fija además a mano
   (`Mover la tarjeta …`) para no depender de la traducción de la librería.

3. **Ajustes salidos de la code review** (`BoardColumnList.tsx`):
   - `indexForDrop` devolvía `otherCards.length` cuando no encontraba la tarjeta
     destino, y el destino *no encontrado* es justamente el hueco de la propia
     tarjeta arrastrada (se filtra de `otherCards`): soltar una tarjeta donde ya
     estaba la mandaba al final de su columna. Ahora devuelve `null` y el
     movimiento no se emite.
   - `onRootDrop` colocaba en el índice 0 dando por hecho que la raíz de una
     columna solo es destino cuando está vacía. No es cierto: también lo es en una
     columna con tarjetas, y es el **primer** destino al que llega un arrastre por
     teclado. Ahora coloca al final (`cards.length`).
   - `acceptedDragTypes` valía `all` y `getDropOperation` devolvía siempre `move`,
     así que un texto arrastrado desde otra pestaña se leía como id de tarjeta y
     acababa en un 422. El tipo de arrastre pasa a ser propio
     (`application/vnd.kanbai.card-id`) y `getDropOperation` devuelve `cancel`
     para cualquier otro.

## Revisión y cierre · 2026-09-08

Se corrigió la concurrencia de movimientos: el arrastre se deshabilita hasta que
terminan la escritura y la reconciliación. Una guarda síncrona evita dos disparos
antes del siguiente render. Regresión con respuesta aplazada y rechazo 409;
también se comprueba la presentación genérica de un 404.

Verificación final ejecutada: `uv run poe check` (111 passed; Ruff, formato y
Mypy correctos), `npm run check` (32 passed en 8 archivos; ESLint y TypeScript
correctos) y `npm run build` (correcto, aviso de chunk superior a 500 kB).
En navegador con API/PostgreSQL reales: movimiento con ratón y recarga; movimiento
por teclado y recarga; rechazo WIP con reversión y aviso; tablero vacío; rejilla y
HeroUI inspeccionados visualmente. Sin cambios de modelos ni contrato: no aplica
migración ni regeneración de tipos por esta revisión.

TASK-14 y TASK-15 siguen pendientes de sus otras dependencias; no queda ninguna
tarea adicional lista para empezar por este cierre.
