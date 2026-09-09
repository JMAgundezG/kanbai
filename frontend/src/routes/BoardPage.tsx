import { Alert, EmptyState, Spinner } from '@heroui/react'
import { useMemo, useRef } from 'react'
import { useParams } from 'react-router'

import { BoardColumnList } from '@/features/board/components/BoardColumnList'
import { useBoard, useBoardCards, useBoardColumns, useMoveCard } from '@/features/board/hooks'
import { groupCardsByColumn } from '@/features/board/lib'

/**
 * The screen the product is named after: a board's columns and cards, with drag
 * and drop (accessible, keyboard-operable via react-aria-components — see
 * BoardColumnList) to move a card between columns.
 */
export function BoardPage() {
  // The route declares :boardId as a required segment (see App.tsx), so it is
  // always present once this component renders.
  const { boardId } = useParams<{ boardId: string }>()
  const boardIdValue = boardId ?? ''

  const board = useBoard(boardIdValue)
  const columns = useBoardColumns(boardIdValue)
  const cards = useBoardCards(boardIdValue)
  const moveCardMutation = useMoveCard(boardIdValue)
  const moveInFlight = useRef(false)

  function handleMove(columnId: string, cardId: string, position: number) {
    if (moveInFlight.current) return
    moveInFlight.current = true
    moveCardMutation.mutate({ cardId, move: { column_id: columnId, position } }, {
      onSettled: () => { moveInFlight.current = false },
    })
  }

  const cardsByColumn = useMemo(() => groupCardsByColumn(cards.data ?? []), [cards.data])

  const isPending = board.isPending || columns.isPending || cards.isPending
  const loadError = board.error ?? columns.error ?? cards.error

  if (isPending) {
    return (
      <div className="flex min-h-48 items-center justify-center">
        <Spinner aria-label="Cargando el tablero" />
      </div>
    )
  }

  if (loadError) {
    return (
      <Alert status="danger">
        <Alert.Title>No se pudo cargar el tablero</Alert.Title>
        <Alert.Description>{loadError.message}</Alert.Description>
      </Alert>
    )
  }

  const boardColumns = columns.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">{board.data?.name}</h2>

      {moveCardMutation.isError ? (
        <Alert status="danger">
          <Alert.Title>No se pudo mover la tarjeta</Alert.Title>
          <Alert.Description>{moveCardMutation.error.message}</Alert.Description>
        </Alert>
      ) : null}

      {boardColumns.length === 0 ? (
        // Should not happen in practice (TASK-05 always seeds three columns), but
        // a board somehow left without any is its own empty state, distinct from
        // "has columns, none have cards yet" — that case is handled per-column
        // below (each GridList's own renderEmptyState), which keeps the column
        // names visible instead of hiding the whole board behind one message.
        <EmptyState className="rounded border border-dashed border-neutral-300 p-8 text-center opacity-70">
          Este tablero todavía no tiene columnas.
        </EmptyState>
      ) : null}

      {boardColumns.length > 0 ? (
        // .row/.col-* come from Bootstrap's grid (estilos-frontend.md); spacing,
        // type and the cards themselves come from Tailwind/HeroUI.
        <div className="row g-4">
          {boardColumns.map((column) => (
            <div key={column.id} className="col-12 col-md">
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide opacity-70">
                {column.name}
              </h3>
              <BoardColumnList
                columnName={column.name}
                cards={cardsByColumn.get(column.id) ?? []}
                isMoving={moveCardMutation.isPending}
                onMoveCard={(cardId, targetIndex) =>
                  handleMove(column.id, cardId, targetIndex)
                }
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
