import { Alert, EmptyState, Spinner } from '@heroui/react'
import { Link } from 'react-router'

import { BackendStatusCard } from '@/features/health/components/BackendStatusCard'
import { useBoards } from '@/features/board/hooks'

/**
 * Landing screen: the actor's boards, each a link into its kanban view
 * (BoardPage, TASK-08). No task covers creating a board from the UI yet, so this
 * stays read-only — boards are created straight against the API for now.
 */
export function HomePage() {
  const boards = useBoards()

  return (
    // .row/.col-* come from Bootstrap's grid; spacing and type come from Tailwind.
    <div className="row g-4">
      <div className="col-12 col-md-6">
        <h2 className="text-xl font-semibold">Tus tableros</h2>

        {boards.isPending ? (
          <div className="flex items-center gap-3 py-4">
            <Spinner size="sm" aria-label="Cargando tus tableros" />
            <span>Cargando tus tableros…</span>
          </div>
        ) : null}

        {boards.isError ? (
          <Alert status="danger">
            <Alert.Title>No se pudieron cargar tus tableros</Alert.Title>
            <Alert.Description>{boards.error.message}</Alert.Description>
          </Alert>
        ) : null}

        {boards.data && boards.data.length === 0 ? (
          <EmptyState className="rounded border border-dashed border-neutral-300 p-6 text-center opacity-70">
            Todavía no perteneces a ningún tablero.
          </EmptyState>
        ) : null}

        {boards.data && boards.data.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-2">
            {boards.data.map((board) => (
              <li key={board.id}>
                <Link
                  to={`/boards/${board.id}`}
                  className="block rounded border border-neutral-200 px-4 py-3 hover:bg-neutral-50"
                >
                  {board.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="col-12 col-md-6">
        <BackendStatusCard />
      </div>
    </div>
  )
}
