import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  type Card,
  type CardMove,
  boardKeys,
  fetchBoard,
  fetchBoardCards,
  fetchBoardColumns,
  fetchBoards,
  moveCard,
} from '@/features/board/api'
import { moveCardOptimistically } from '@/features/board/lib'

export function useBoards() {
  return useQuery({
    queryKey: boardKeys.lists(),
    queryFn: fetchBoards,
  })
}

export function useBoard(boardId: string) {
  return useQuery({
    queryKey: boardKeys.detail(boardId),
    queryFn: () => fetchBoard(boardId),
  })
}

export function useBoardColumns(boardId: string) {
  return useQuery({
    queryKey: boardKeys.columns(boardId),
    queryFn: () => fetchBoardColumns(boardId),
  })
}

export function useBoardCards(boardId: string) {
  return useQuery({
    queryKey: boardKeys.cards(boardId),
    queryFn: () => fetchBoardCards(boardId),
  })
}

interface MoveCardVariables {
  cardId: string
  move: CardMove
}

interface MoveCardContext {
  previousCards: Card[] | undefined
}

/**
 * Optimistic move: the card jumps to its new column/slot immediately, before the
 * API responds. `onError` puts the previous card list straight back — the visual
 * "snap back" the task requires — and `onSettled` always invalidates afterwards
 * (success or failure) so the real `position` values from the backend, not the
 * optimistic guess, are what the UI ends up trusting.
 */
export function useMoveCard(boardId: string) {
  const queryClient = useQueryClient()
  const cardsKey = boardKeys.cards(boardId)

  return useMutation<Card, Error, MoveCardVariables, MoveCardContext>({
    mutationFn: ({ cardId, move }) => moveCard(boardId, cardId, move),

    onMutate: async ({ cardId, move }) => {
      await queryClient.cancelQueries({ queryKey: cardsKey })
      const previousCards = queryClient.getQueryData<Card[]>(cardsKey)

      if (previousCards) {
        queryClient.setQueryData<Card[]>(
          cardsKey,
          moveCardOptimistically(previousCards, cardId, move.column_id, move.position),
        )
      }

      return { previousCards }
    },

    onError: (_error, _variables, context) => {
      if (context?.previousCards) {
        queryClient.setQueryData(cardsKey, context.previousCards)
      }
    },

    onSettled: () => queryClient.invalidateQueries({ queryKey: cardsKey }),
  })
}
