import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BackendStatusCard } from '@/features/health/components/BackendStatusCard'

function renderWithQuery(ui: ReactElement) {
  // retry: false — otherwise the error state takes seconds to appear.
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

afterEach(() => {
  vi.restoreAllMocks()
})

describe('BackendStatusCard', () => {
  it('muestra el indicador de carga mientras espera al backend', () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))

    renderWithQuery(<BackendStatusCard />)

    expect(screen.getByText(/comprobando el estado del backend/i)).toBeInTheDocument()
  })

  it('muestra la base de datos como disponible cuando la API responde', async () => {
    mockFetch({ status: 'ok', database: 'ok' })

    renderWithQuery(<BackendStatusCard />)

    expect(await screen.findByText('disponible')).toBeInTheDocument()
    expect(screen.getByText('Estado del backend')).toBeInTheDocument()
  })

  it('avisa en español cuando el backend responde 503', async () => {
    mockFetch({ status: 'error', database: 'error' }, 503)

    renderWithQuery(<BackendStatusCard />)

    expect(
      await screen.findByText(/no se puede contactar con el backend/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/503/)).toBeInTheDocument()
  })

  it('avisa cuando la petición falla del todo', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network down'))

    renderWithQuery(<BackendStatusCard />)

    expect(
      await screen.findByText(/no se puede contactar con el backend/i),
    ).toBeInTheDocument()
  })
})
