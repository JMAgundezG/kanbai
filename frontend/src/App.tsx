import { QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { RouterProvider, createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { authKeys } from '@/features/auth/api'
import { onUnauthorized } from '@/lib/authEvents'
import { createQueryClient } from '@/lib/queryClient'
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
        children: [{ index: true, element: <HomePage /> }],
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
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
