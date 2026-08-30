import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/authEvents', () => ({
  notifyUnauthorized: vi.fn(),
}))

// Imported after the mock so the middleware registered at module load time
// captures the mocked function.
import { apiClient } from '@/api/client'
import { notifyUnauthorized } from '@/lib/authEvents'

function mockFetch(body: unknown, status: number) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => {
  // restoreAllMocks undoes the fetch spy; the mocked authEvents module is a
  // vi.fn() created once by the factory above, so its call log needs a
  // separate, explicit reset between tests.
  vi.restoreAllMocks()
  vi.mocked(notifyUnauthorized).mockClear()
})

describe('apiClient — manejo centralizado del 401', () => {
  it('notifica en un 401 de un endpoint protegido cualquiera', async () => {
    mockFetch({ detail: 'No has iniciado sesión.' }, 401)

    await apiClient.GET('/api/v1/auth/me')

    expect(notifyUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('no notifica en un 401 de /auth/login: son credenciales incorrectas, no una sesión caída', async () => {
    mockFetch({ detail: 'El email o la contraseña no son correctos.' }, 401)

    await apiClient.POST('/api/v1/auth/login', {
      body: { email: 'ada@example.com', password: 'lo-que-sea' },
    })

    expect(notifyUnauthorized).not.toHaveBeenCalled()
  })
})
