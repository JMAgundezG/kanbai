import { apiClient } from '@/api/client'
import type { components } from '@/api/schema'

export type Actor = components['schemas']['ActorRead']
export type LoginCredentials = components['schemas']['LoginRequest']

export const authKeys = {
  all: ['auth'] as const,
  me: () => [...authKeys.all, 'me'] as const,
}

const UNAUTHORIZED = 401

/**
 * A 401 here means "nobody is signed in" — the normal, expected state on a
 * fresh visit — not a failed request. Any other non-OK status is a real
 * problem the caller must surface, not silently treat as "no session".
 */
export async function fetchCurrentActor(): Promise<Actor | null> {
  const { data, response } = await apiClient.GET('/api/v1/auth/me')

  if (response.status === UNAUTHORIZED) {
    return null
  }

  if (!data || !response.ok) {
    throw new Error(`No se pudo comprobar la sesión (HTTP ${String(response.status)}).`)
  }

  return data
}

/** The backend's 401 body is `{ detail: "..." }`, already in Spanish. */
function extractErrorDetail(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    return typeof error.detail === 'string' ? error.detail : undefined
  }
  return undefined
}

export async function login(credentials: LoginCredentials): Promise<Actor> {
  const { data, error, response } = await apiClient.POST('/api/v1/auth/login', {
    body: credentials,
  })

  if (data) {
    return data
  }

  if (response.status === UNAUTHORIZED) {
    throw new Error(extractErrorDetail(error) ?? 'El email o la contraseña no son correctos.')
  }

  throw new Error(`No se pudo iniciar sesión (HTTP ${String(response.status)}).`)
}

export async function logout(): Promise<void> {
  const { response } = await apiClient.POST('/api/v1/auth/logout')

  if (!response.ok) {
    throw new Error(`No se pudo cerrar la sesión (HTTP ${String(response.status)}).`)
  }
}
