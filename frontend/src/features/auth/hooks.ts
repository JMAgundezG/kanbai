import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  type Actor,
  type LoginCredentials,
  authKeys,
  fetchCurrentActor,
  login,
  logout,
} from '@/features/auth/api'

export function useCurrentActor() {
  return useQuery({
    queryKey: authKeys.me(),
    queryFn: fetchCurrentActor,
    // A 401 is not transient — retrying it just delays showing the login screen.
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (credentials: LoginCredentials) => login(credentials),
    onSuccess: (actor: Actor) => {
      // Written directly instead of invalidated: the response already is the
      // actor, so there is no reason to round-trip to /me again.
      queryClient.setQueryData(authKeys.me(), actor)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(authKeys.me(), null)
    },
  })
}
