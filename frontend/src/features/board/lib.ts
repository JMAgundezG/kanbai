import type { Card } from '@/features/board/api'

/**
 * Recomputes the flat `Card[]` the API returns after moving `cardId` into
 * `targetColumnId` at `targetIndex` (an index *within that column's cards*, the
 * same unit the move endpoint takes). Pure so it can be unit-tested without a
 * DOM or a mocked `fetch`, and reused identically by the optimistic write and by
 * the reordering math below it.
 *
 * Only reorders the array — it does not touch `position`. The real float value is
 * decided by the backend; the optimistic write only needs cards to render in the
 * right slot until the mutation settles and the query is invalidated.
 */
export function moveCardOptimistically(
  cards: Card[],
  cardId: string,
  targetColumnId: string,
  targetIndex: number,
): Card[] {
  const movedCard = cards.find((card) => card.id === cardId)
  if (!movedCard) {
    return cards
  }

  const withoutMoved = cards.filter((card) => card.id !== cardId)
  const updatedCard: Card = { ...movedCard, column_id: targetColumnId }

  let seenInTargetColumn = 0
  for (const [index, card] of withoutMoved.entries()) {
    if (card.column_id !== targetColumnId) {
      continue
    }
    if (seenInTargetColumn === targetIndex) {
      return [...withoutMoved.slice(0, index), updatedCard, ...withoutMoved.slice(index)]
    }
    seenInTargetColumn += 1
  }

  // targetIndex is at or past the end of the target column (including an empty
  // one): append right after the target column's last card, or anywhere if the
  // column has none — same "clamped to the end" behavior the backend documents.
  let lastIndexInTargetColumn = -1
  for (const [index, card] of withoutMoved.entries()) {
    if (card.column_id === targetColumnId) {
      lastIndexInTargetColumn = index
    }
  }

  const insertAt = lastIndexInTargetColumn + 1
  return [...withoutMoved.slice(0, insertAt), updatedCard, ...withoutMoved.slice(insertAt)]
}

/** Groups the flat, API-ordered card list by column, keeping relative order. */
export function groupCardsByColumn(cards: Card[]): Map<string, Card[]> {
  const grouped = new Map<string, Card[]>()
  for (const card of cards) {
    const columnCards = grouped.get(card.column_id)
    if (columnCards) {
      columnCards.push(card)
    } else {
      grouped.set(card.column_id, [card])
    }
  }
  return grouped
}
