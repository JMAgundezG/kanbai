import { useQuery } from '@tanstack/react-query'

import { fetchReadiness, healthKeys } from '@/features/health/api'

export function useBackendStatus() {
  return useQuery({
    queryKey: healthKeys.readiness(),
    queryFn: fetchReadiness,
  })
}
