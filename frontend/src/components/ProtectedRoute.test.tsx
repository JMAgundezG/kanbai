import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ProtectedRoute } from '@/components/ProtectedRoute'

function mockFetch(body: unknown, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function renderProtected() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/acceso" element={<p>Pantalla de acceso</p>} />
          <Route path="/" element={<ProtectedRoute />}>
            <Route index element={<p>Contenido protegido</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ProtectedRoute', () => {
  it('sin sesión, redirige a la pantalla de acceso', async () => {
    mockFetch({ detail: 'No has iniciado sesión.' }, 401)

    renderProtected()

    expect(await screen.findByText('Pantalla de acceso')).toBeInTheDocument()
  })

  it('con sesión activa, muestra el contenido protegido', async () => {
    mockFetch({
      id: '11111111-1111-1111-1111-111111111111',
      kind: 'person',
      display_name: 'Ada Lovelace',
      created_at: '2026-01-01T00:00:00Z',
    })

    renderProtected()

    expect(await screen.findByText('Contenido protegido')).toBeInTheDocument()
  })

  it('mientras carga, no muestra ni el acceso ni el contenido', () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))

    renderProtected()

    expect(screen.queryByText('Pantalla de acceso')).not.toBeInTheDocument()
    expect(screen.queryByText('Contenido protegido')).not.toBeInTheDocument()
  })
})
