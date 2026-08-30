import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LoginForm } from '@/features/auth/components/LoginForm'

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

afterEach(() => {
  vi.restoreAllMocks()
})

describe('LoginForm', () => {
  it('no llama a la API y avisa en español si se envía sin rellenar', async () => {
    const user = userEvent.setup()
    const fetchSpy = mockFetch({})

    renderWithQuery(<LoginForm />)
    await user.click(screen.getByRole('button', { name: /acceder/i }))

    expect(
      await screen.findByText('Introduce tu email y tu contraseña.'),
    ).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('un acceso correcto llama a onSuccess con el actor', async () => {
    const user = userEvent.setup()
    const actor = {
      id: '11111111-1111-1111-1111-111111111111',
      kind: 'person',
      display_name: 'Ada Lovelace',
      created_at: '2026-01-01T00:00:00Z',
    }
    mockFetch(actor)
    const onSuccess = vi.fn()

    renderWithQuery(<LoginForm onSuccess={onSuccess} />)
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/contraseña/i), 'correcto-caballo-batería')
    await user.click(screen.getByRole('button', { name: /acceder/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(actor)
    })
  })

  it('credenciales inválidas muestran el mensaje de error en español', async () => {
    const user = userEvent.setup()
    mockFetch({ detail: 'El email o la contraseña no son correctos.' }, 401)

    renderWithQuery(<LoginForm />)
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com')
    await user.type(screen.getByLabelText(/contraseña/i), 'lo-que-sea')
    await user.click(screen.getByRole('button', { name: /acceder/i }))

    expect(
      await screen.findByText('El email o la contraseña no son correctos.'),
    ).toBeInTheDocument()
  })
})
