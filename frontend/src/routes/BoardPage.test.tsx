import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Board, BoardColumn, Card } from '@/features/board/api'
import { BoardPage } from '@/routes/BoardPage'

const BOARD_ID = 'board-1'
const TODO_ID = 'column-todo'
const DOING_ID = 'column-doing'

const board: Board = {
  id: BOARD_ID,
  name: 'Lanzamiento',
  created_at: '2026-01-01T00:00:00Z',
  role: 'owner',
}

const columns: BoardColumn[] = [
  {
    id: TODO_ID,
    board_id: BOARD_ID,
    name: 'Por hacer',
    wip_limit: null,
    position: 1,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: DOING_ID,
    board_id: BOARD_ID,
    name: 'En curso',
    wip_limit: 1,
    position: 2,
    created_at: '2026-01-01T00:00:00Z',
  },
]

function makeCard(overrides: Partial<Card> = {}): Card {
  return {
    id: 'card-1',
    board_id: BOARD_ID,
    column_id: TODO_ID,
    title: 'Escribir la spec',
    description: null,
    position: 1,
    created_by_actor_id: 'actor-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function page<T>(items: T[]) {
  return { items, total: items.length, page: 1, size: 100 }
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

interface BoardApiStubs {
  cards?: Card[]
  columnsStatus?: number
  /** Response the move endpoint answers with; defaults to echoing the request. */
  moveResponse?: () => Response | Promise<Response>
}

/**
 * Routes by URL instead of a single canned response: BoardPage fires three
 * queries at once, and the move endpoint has to answer differently per test.
 */
function stubBoardApi({ cards = [], columnsStatus = 200, moveResponse }: BoardApiStubs = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = new URL(input instanceof Request ? input.url : String(input))

    if (url.pathname.endsWith('/move')) {
      return Promise.resolve(moveResponse ? moveResponse() : jsonResponse(makeCard()))
    }
    if (url.pathname.endsWith('/columns')) {
      return Promise.resolve(
        columnsStatus === 200
          ? jsonResponse(page(columns))
          : jsonResponse({ detail: 'Error interno.' }, columnsStatus),
      )
    }
    if (url.pathname.endsWith('/cards')) {
      return Promise.resolve(jsonResponse(page(cards)))
    }
    return Promise.resolve(jsonResponse(board))
  })
}

/** Enough Tab presses to walk every drop target the fixture board can offer. */
const MAX_DROP_TARGETS = 8

type MockedFetch = ReturnType<typeof stubBoardApi>

function renderBoardPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/boards/${BOARD_ID}`]}>
        <Routes>
          <Route path="/boards/:boardId" element={<BoardPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function columnList(name: string) {
  return screen.getByRole('grid', { name: `Tarjetas de la columna ${name}` })
}

/**
 * The keyboard path a card actually travels: focus the card, ArrowRight onto its
 * drag handle, Enter to start dragging, Tab through the drop targets until one
 * inside the destination column is focused, Enter to drop. Targets are matched by
 * containment rather than by their accessible name, which react-aria localizes.
 */
async function dragWithKeyboardInto(
  destinationColumnName: string,
  user: ReturnType<typeof userEvent.setup>,
) {
  const destination = columnList(destinationColumnName)
  const card = screen.getAllByRole('row')[0]
  act(() => {
    card.focus()
  })
  await user.keyboard('{ArrowRight}')
  await user.keyboard('{Enter}')

  for (let step = 0; step < MAX_DROP_TARGETS; step += 1) {
    const focused = document.activeElement
    if (focused !== destination && destination.contains(focused)) {
      break
    }
    await user.tab()
  }

  await user.keyboard('{Enter}')
}

/** Starts the keyboard drag and drops on the first target react-aria offers,
 *  which is the dragged card's own slot — dropping it where it already was. */
async function dragWithKeyboardInPlace(user: ReturnType<typeof userEvent.setup>) {
  const card = screen.getAllByRole('row')[0]
  act(() => {
    card.focus()
  })
  await user.keyboard('{ArrowRight}')
  await user.keyboard('{Enter}')
  await user.keyboard('{Enter}')
}

/** Every board request goes through one `fetch` spy; this picks the move out. */
function lastMoveRequest(fetchSpy: MockedFetch): Request | undefined {
  return fetchSpy.mock.calls
    .map(([input]) => input)
    .filter((input): input is Request => input instanceof Request)
    .findLast((request) => request.url.endsWith('/move'))
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('BoardPage', () => {
  it('un tablero ajeno devuelve un error genérico sin mostrar tarjetas', async () => {
    stubBoardApi({ columnsStatus: 404 })
    renderBoardPage()
    expect(await screen.findByText('No se pudo cargar el tablero')).toBeInTheDocument()
    expect(screen.queryByRole('grid')).not.toBeInTheDocument()
  })

  it('impide otro arrastre mientras guarda y reconcilia el movimiento', async () => {
    const user = userEvent.setup()
    let finishMove: (response: Response) => void = () => undefined
    const pendingMove = new Promise<Response>((resolve) => { finishMove = resolve })
    stubBoardApi({ cards: [makeCard()], moveResponse: () => pendingMove })
    renderBoardPage()
    await screen.findByText('Lanzamiento')
    await dragWithKeyboardInto('En curso', user)
    await waitFor(() => {
      expect(within(columnList('En curso')).getByText('Escribir la spec')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Mover la tarjeta Escribir la spec' })).toBeDisabled()
    })
    act(() => { finishMove(jsonResponse({ detail: 'Movimiento rechazado.' }, 409)) })
    expect(await screen.findByText('Movimiento rechazado.')).toBeInTheDocument()
    await waitFor(() => {
      expect(within(columnList('Por hacer')).getByText('Escribir la spec')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Mover la tarjeta Escribir la spec' })).toBeEnabled()
    })
  })

  it('pinta las columnas del tablero con sus tarjetas', async () => {
    stubBoardApi({
      cards: [
        makeCard(),
        makeCard({ id: 'card-2', column_id: DOING_ID, title: 'Implementar el tablero' }),
      ],
    })

    renderBoardPage()

    expect(await screen.findByText('Lanzamiento')).toBeInTheDocument()
    expect(within(columnList('Por hacer')).getByText('Escribir la spec')).toBeInTheDocument()
    expect(
      within(columnList('En curso')).getByText('Implementar el tablero'),
    ).toBeInTheDocument()
  })

  it('un tablero sin tarjetas muestra el estado vacío de cada columna', async () => {
    stubBoardApi({ cards: [] })

    renderBoardPage()

    await screen.findByText('Lanzamiento')
    expect(within(columnList('Por hacer')).getByText('Sin tarjetas')).toBeInTheDocument()
    expect(within(columnList('En curso')).getByText('Sin tarjetas')).toBeInTheDocument()
  })

  it('si la API falla, avisa en vez de dejar la pantalla en blanco', async () => {
    stubBoardApi({ columnsStatus: 500 })

    renderBoardPage()

    expect(await screen.findByText('No se pudo cargar el tablero')).toBeInTheDocument()
    expect(
      screen.getByText('No se pudieron cargar las columnas (HTTP 500).'),
    ).toBeInTheDocument()
  })

  it('mueve una tarjeta a otra columna solo con el teclado', async () => {
    const user = userEvent.setup()
    const fetchSpy = stubBoardApi({ cards: [makeCard()] })

    renderBoardPage()
    await screen.findByText('Lanzamiento')

    await dragWithKeyboardInto('En curso', user)

    const moveRequest = await waitFor(() => {
      const request = lastMoveRequest(fetchSpy)
      expect(request).toBeDefined()
      return request as Request
    })
    expect(moveRequest.url).toContain(`/boards/${BOARD_ID}/cards/card-1/move`)
    await expect(moveRequest.json()).resolves.toEqual({ column_id: DOING_ID, position: 0 })
  })

  it('soltar una tarjeta donde ya estaba no la mueve', async () => {
    const user = userEvent.setup()
    const fetchSpy = stubBoardApi({ cards: [makeCard()] })

    renderBoardPage()
    await screen.findByText('Lanzamiento')

    await dragWithKeyboardInPlace(user)

    expect(lastMoveRequest(fetchSpy)).toBeUndefined()
  })

  it('soltar sobre una columna que ya tiene tarjetas la coloca al final', async () => {
    const user = userEvent.setup()
    const fetchSpy = stubBoardApi({
      cards: [
        makeCard(),
        makeCard({ id: 'card-2', column_id: DOING_ID, title: 'Implementar el tablero' }),
      ],
    })

    renderBoardPage()
    await screen.findByText('Lanzamiento')

    await dragWithKeyboardInto('En curso', user)

    const moveRequest = await waitFor(() => {
      const request = lastMoveRequest(fetchSpy)
      expect(request).toBeDefined()
      return request as Request
    })
    await expect(moveRequest.json()).resolves.toEqual({ column_id: DOING_ID, position: 1 })
  })

  it('si el movimiento falla, la tarjeta vuelve a su columna y se avisa', async () => {
    const user = userEvent.setup()
    const wipMessage =
      'No se pueden añadir más tarjetas a «En curso»: ha alcanzado su límite de 1 tarjetas.'
    stubBoardApi({
      cards: [makeCard()],
      moveResponse: () => jsonResponse({ detail: wipMessage }, 409),
    })

    renderBoardPage()
    await screen.findByText('Lanzamiento')

    await dragWithKeyboardInto('En curso', user)

    expect(await screen.findByText(wipMessage)).toBeInTheDocument()
    await waitFor(() => {
      expect(within(columnList('Por hacer')).getByText('Escribir la spec')).toBeInTheDocument()
    })
    expect(within(columnList('En curso')).getByText('Sin tarjetas')).toBeInTheDocument()
  })

  it('un 404 al mover revierte la tarjeta sin revelar el detalle del recurso', async () => {
    const user = userEvent.setup()
    const resourceDetail = 'La tarjeta solicitada no existe.'
    stubBoardApi({
      cards: [makeCard()],
      moveResponse: () => jsonResponse({ detail: resourceDetail }, 404),
    })

    renderBoardPage()
    await screen.findByText('Lanzamiento')

    await dragWithKeyboardInto('En curso', user)

    expect(await screen.findByText('No se pudo mover la tarjeta.')).toBeInTheDocument()
    expect(screen.queryByText(resourceDetail)).not.toBeInTheDocument()
    await waitFor(() => {
      expect(within(columnList('Por hacer')).getByText('Escribir la spec')).toBeInTheDocument()
    })
    expect(within(columnList('En curso')).getByText('Sin tarjetas')).toBeInTheDocument()
  })
})
