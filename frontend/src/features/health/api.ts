import { apiClient } from '@/api/client'
import type { components } from '@/api/schema'

export type Readiness = components['schemas']['ReadinessRead']

export const healthKeys = {
  all: ['health'] as const,
  readiness: () => [...healthKeys.all, 'ready'] as const,
}

/**
 * Readiness answers 503 with a perfectly valid body when the database is down,
 * and openapi-fetch resolves instead of throwing. Without this explicit throw a
 * degraded backend would look like a successful query.
 */
export async function fetchReadiness(): Promise<Readiness> {
  const { data, response } = await apiClient.GET('/api/v1/health/ready')

  if (!data || !response.ok) {
    throw new Error(`El backend no está disponible (HTTP ${String(response.status)}).`)
  }

  return data
}
