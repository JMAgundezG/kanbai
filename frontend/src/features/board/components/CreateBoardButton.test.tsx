import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CreateBoardButton } from '@/features/board/components/CreateBoardButton'

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

function mockFetch(body: unknown, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

const createdBoard = {
  id: '22222222-2222-2222-2222-222222222222',
  name: 'Tablero de producto',
  created_at: '2026-01-01T00:00:00Z',
  role: 'owner',
}

/** openapi-fetch llama a `fetch` con un único `Request`, no con `(url, init)`. */
async function requestBody(fetchSpy: ReturnType<typeof mockFetch>, call = 0): Promise<unknown> {
  const request = fetchSpy.mock.calls[call]?.[0] as Request
  return JSON.parse(await request.clone().text())
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CreateBoardButton', () => {
  it('crea el tablero con el nombre recortado y cierra el diálogo', async () => {
    const user = userEvent.setup()
    const fetchSpy = mockFetch(createdBoard, 201)

    renderWithQuery(<CreateBoardButton />)
    await user.click(screen.getByRole('button', { name: 'Nuevo tablero' }))

    await user.type(await screen.findByLabelText(/nombre/i), '  Tablero de producto  ')
    await user.click(screen.getByRole('button', { name: /crear tablero/i }))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1)
    })
    expect(await requestBody(fetchSpy)).toEqual({ name: 'Tablero de producto' })

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('se abre y se cierra solo con el teclado', async () => {
    const user = userEvent.setup()
    mockFetch(createdBoard, 201)

    renderWithQuery(<CreateBoardButton />)
    await user.tab()
    expect(screen.getByRole('button', { name: 'Nuevo tablero' })).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('no llama a la API si se envía sin nombre y avisa en español', async () => {
    const user = userEvent.setup()
    const fetchSpy = mockFetch(createdBoard, 201)

    renderWithQuery(<CreateBoardButton />)
    await user.click(screen.getByRole('button', { name: 'Nuevo tablero' }))
    await user.type(await screen.findByLabelText(/nombre/i), '   ')
    await user.click(screen.getByRole('button', { name: /crear tablero/i }))

    expect(await screen.findByText('Escribe un nombre para el tablero.')).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('si la API falla muestra el error en español y conserva lo escrito', async () => {
    const user = userEvent.setup()
    mockFetch({ detail: 'Vuelve a intentarlo más tarde.' }, 500)

    renderWithQuery(<CreateBoardButton />)
    await user.click(screen.getByRole('button', { name: 'Nuevo tablero' }))

    const field = await screen.findByLabelText(/nombre/i)
    await user.type(field, 'Tablero de producto')
    await user.click(screen.getByRole('button', { name: /crear tablero/i }))

    expect(await screen.findByText('Vuelve a intentarlo más tarde.')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(field).toHaveValue('Tablero de producto')
  })

  it('un nombre rechazado por el backend se explica en español, sin el detalle de Pydantic', async () => {
    const user = userEvent.setup()
    mockFetch({ detail: [{ loc: ['body', 'name'], msg: 'String should have at most 200 characters', type: 'string_too_long' }] }, 422)

    renderWithQuery(<CreateBoardButton />)
    await user.click(screen.getByRole('button', { name: 'Nuevo tablero' }))
    await user.type(await screen.findByLabelText(/nombre/i), 'Tablero de producto')
    await user.click(screen.getByRole('button', { name: /crear tablero/i }))

    expect(
      await screen.findByText(
        'El nombre del tablero no es válido: debe tener entre 1 y 200 caracteres.',
      ),
    ).toBeInTheDocument()
  })
})
