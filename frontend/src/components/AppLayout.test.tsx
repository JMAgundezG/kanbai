import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppLayout } from '@/components/AppLayout'

function renderLayoutAt(path: string) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        id: '11111111-1111-1111-1111-111111111111',
        kind: 'person',
        display_name: 'Ada Lovelace',
        created_at: '2026-01-01T00:00:00Z',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<p>Vista inicial</p>} />
            <Route path="boards/:boardId" element={<p>Vista del tablero</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AppLayout', () => {
  it('el título del encabezado lleva a la vista inicial', async () => {
    const user = userEvent.setup()
    renderLayoutAt('/boards/22222222-2222-2222-2222-222222222222')

    expect(screen.getByText('Vista del tablero')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'kanbai' }))

    expect(await screen.findByText('Vista inicial')).toBeInTheDocument()
  })
})
