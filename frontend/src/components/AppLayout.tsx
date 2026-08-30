import { Outlet } from 'react-router'

/**
 * The page wrapper is Tailwind's, not Bootstrap's `.container`: Tailwind v4 ships a
 * `.container` utility of its own, and the utilities layer wins, so the class name is
 * effectively taken. Bootstrap is used strictly for `.row` / `.col-*`.
 */
export function AppLayout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-neutral-200 py-4">
        <div className="mx-auto w-full max-w-6xl px-4">
          <h1 className="text-2xl font-bold">kanbai</h1>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
