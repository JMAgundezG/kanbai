import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RouterProvider, createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { createQueryClient } from '@/lib/queryClient'
import { HomePage } from '@/routes/HomePage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [{ index: true, element: <HomePage /> }],
  },
])

export function App() {
  // Created once per mount rather than at module scope, so a test (or a future
  // SSR entry point) never shares cache between renders.
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
