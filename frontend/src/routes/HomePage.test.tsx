import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Board } from '@/features/board/api'
import { HomePage } from '@/routes/HomePage'

const newBoard: Board = {
  id: 'board-1',
  name: 'Lanzamiento',
  created_at: '2026-01-01T00:00:00Z',
  role: 'owner',
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function page<T>(items: T[]) {
  return { items, total: items.length, page: 1, size: 100 }
}

/**
 * El listado de tableros empieza vacío y solo devuelve el tablero nuevo **después**
 * del POST: así el test distingue de verdad si la lista se ha vuelto a pedir tras
 * crearlo, en lugar de dar por buena una respuesta fija.
 */
function stubHomeApi() {
  let created = false

  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const request = input instanceof Request ? input : new Request(String(input))
    const url = new URL(request.url)

    if (url.pathname.endsWith('/health/ready')) {
      return Promise.resolve(jsonResponse({ status: 'ok', database: 'ok' }))
    }
    if (request.method === 'POST') {
      created = true
      return Promise.resolve(jsonResponse(newBoard, 201))
    }
    return Promise.resolve(jsonResponse(page(created ? [newBoard] : [])))
  })
}

function renderHomePage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('HomePage', () => {
  it('el tablero creado aparece en la lista sin recargar la página', async () => {
    const user = userEvent.setup()
    stubHomeApi()

    renderHomePage()
    expect(await screen.findByText(/todavía no perteneces a ningún tablero/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Nuevo tablero' }))
    await user.type(await screen.findByLabelText(/nombre/i), 'Lanzamiento')
    await user.click(screen.getByRole('button', { name: /crear tablero/i }))

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Lanzamiento' })).toHaveAttribute(
        'href',
        '/boards/board-1',
      )
    })
  })
})
