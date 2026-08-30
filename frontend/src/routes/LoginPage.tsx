import { Card } from '@heroui/react'
import { useNavigate, useLocation } from 'react-router'

import { LoginForm } from '@/features/auth/components/LoginForm'

interface RedirectState {
  from?: { pathname?: string }
}

function isRedirectState(state: unknown): state is RedirectState {
  return typeof state === 'object' && state !== null
}

/** `ProtectedRoute` stashes the page it bounced the user from in navigation
 *  state; land back there instead of always going to `/`. */
function redirectTarget(state: unknown): string {
  if (isRedirectState(state) && typeof state.from?.pathname === 'string') {
    return state.from.pathname
  }
  return '/'
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <Card.Header>
          <Card.Title>Acceder a kanbai</Card.Title>
        </Card.Header>
        <Card.Content>
          <LoginForm
            onSuccess={() => {
              void navigate(redirectTarget(location.state), { replace: true })
            }}
          />
        </Card.Content>
      </Card>
    </div>
  )
}
