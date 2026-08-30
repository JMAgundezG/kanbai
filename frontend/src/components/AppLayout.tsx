import { Button } from '@heroui/react'
import { Outlet, useNavigate } from 'react-router'

import { useCurrentActor, useLogout } from '@/features/auth/hooks'

/**
 * The page wrapper is Tailwind's, not Bootstrap's `.container`: Tailwind v4 ships a
 * `.container` utility of its own, and the utilities layer wins, so the class name is
 * effectively taken. Bootstrap is used strictly for `.row` / `.col-*`.
 *
 * Only ever rendered under ProtectedRoute, so `useCurrentActor` always has an
 * actor here by the time this paints — no loading/empty state to handle again.
 */
export function AppLayout() {
  const { data: actor } = useCurrentActor()
  const logoutMutation = useLogout()
  const navigate = useNavigate()

  function handleLogout() {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        void navigate('/acceso', { replace: true })
      },
    })
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-neutral-200 py-4">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4">
          <h1 className="text-2xl font-bold">kanbai</h1>
          {actor ? (
            <div className="flex items-center gap-3">
              <span className="text-sm opacity-80">{actor.display_name}</span>
              <Button
                variant="secondary"
                size="sm"
                onPress={handleLogout}
                isDisabled={logoutMutation.isPending}
              >
                Salir
              </Button>
            </div>
          ) : null}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
