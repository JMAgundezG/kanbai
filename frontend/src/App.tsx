import { QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { I18nProvider } from 'react-aria-components'
import { RouterProvider, createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { authKeys } from '@/features/auth/api'
import { onUnauthorized } from '@/lib/authEvents'
import { createQueryClient } from '@/lib/queryClient'
import { BoardPage } from '@/routes/BoardPage'
import { HomePage } from '@/routes/HomePage'
import { LoginPage } from '@/routes/LoginPage'

const router = createBrowserRouter([
  { path: '/acceso', element: <LoginPage /> },
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: 'boards/:boardId', element: <BoardPage /> },
        ],
      },
    ],
  },
])

export function App() {
  // Created once per mount rather than at module scope, so a test (or a future
  // SSR entry point) never shares cache between renders.
  const [queryClient] = useState(createQueryClient)

  useEffect(
    // api/client.ts has no reference to this instance (see lib/authEvents.ts) —
    // this is the one place that connects a 401 anywhere in the app to "the
    // session is gone" in the query cache.
    () => onUnauthorized(() => queryClient.setQueryData(authKeys.me(), null)),
    [queryClient],
  )

  return (
    <QueryClientProvider client={queryClient}>
      {/* react-aria announces drag and drop to screen readers with its own
          strings; without a locale it follows the browser's, which would speak
          English over a Spanish UI (AGENTS.md § 7). */}
      <I18nProvider locale="es-ES">
        <RouterProvider router={router} />
      </I18nProvider>
    </QueryClientProvider>
  )
}
