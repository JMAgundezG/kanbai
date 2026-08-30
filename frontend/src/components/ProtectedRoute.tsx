import { Alert, Spinner } from '@heroui/react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { useCurrentActor } from '@/features/auth/hooks'

/**
 * Guards the routes nested under it: no session → redirect to /acceso, keeping
 * the origin so LoginForm can send the user back where they were headed.
 *
 * Purely a guard, no chrome of its own — that is AppLayout's job, one level
 * further down the tree.
 */
export function ProtectedRoute() {
  const { data: actor, isPending, isError, error } = useCurrentActor()
  const location = useLocation()

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner aria-label="Comprobando la sesión" />
      </div>
    )
  }

  if (isError) {
    // A real failure (backend down, network error) — not "no session". Shown
    // in place rather than redirecting, so a dead backend doesn't look like a
    // login problem.
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <Alert status="danger">
          <Alert.Title>No se puede comprobar la sesión</Alert.Title>
          <Alert.Description>{error.message}</Alert.Description>
        </Alert>
      </div>
    )
  }

  if (!actor) {
    return <Navigate to="/acceso" replace state={{ from: location }} />
  }

  return <Outlet />
}
