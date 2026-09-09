import { describe, expect, it } from 'vitest'

import type { Card } from '@/features/board/api'
import { groupCardsByColumn, moveCardOptimistically } from '@/features/board/lib'

const COLUMN_A = 'column-a'
const COLUMN_B = 'column-b'

function makeCard(id: string, columnId: string, position: number): Card {
  return {
    id,
    board_id: 'board-1',
    column_id: columnId,
    title: `Tarjeta ${id}`,
    description: null,
    position,
    created_by_actor_id: 'actor-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('moveCardOptimistically', () => {
  it('mueve una tarjeta a otra columna, en el índice indicado', () => {
    const cards = [
      makeCard('a1', COLUMN_A, 0),
      makeCard('a2', COLUMN_A, 1),
      makeCard('b1', COLUMN_B, 0),
      makeCard('b2', COLUMN_B, 1),
    ]

    const result = moveCardOptimistically(cards, 'a1', COLUMN_B, 1)

    expect(result.map((card) => card.id)).toEqual(['a2', 'b1', 'a1', 'b2'])
    expect(result.find((card) => card.id === 'a1')?.column_id).toBe(COLUMN_B)
  })

  it('mueve al final de una columna vacía', () => {
    const cards = [makeCard('a1', COLUMN_A, 0)]

    const result = moveCardOptimistically(cards, 'a1', COLUMN_B, 0)

    expect(result).toHaveLength(1)
    expect(result[0]?.column_id).toBe(COLUMN_B)
  })

  it('reordena dentro de la misma columna', () => {
    const cards = [makeCard('a1', COLUMN_A, 0), makeCard('a2', COLUMN_A, 1)]

    const result = moveCardOptimistically(cards, 'a2', COLUMN_A, 0)

    expect(result.map((card) => card.id)).toEqual(['a2', 'a1'])
  })

  it('un índice mayor que el tamaño de la columna la deja al final', () => {
    const cards = [
      makeCard('a1', COLUMN_A, 0),
      makeCard('b1', COLUMN_B, 0),
      makeCard('b2', COLUMN_B, 1),
    ]

    const result = moveCardOptimistically(cards, 'a1', COLUMN_B, 99)

    expect(result.map((card) => card.id)).toEqual(['b1', 'b2', 'a1'])
  })

  it('devuelve la lista sin cambios si la tarjeta no existe', () => {
    const cards = [makeCard('a1', COLUMN_A, 0)]

    const result = moveCardOptimistically(cards, 'missing', COLUMN_B, 0)

    expect(result).toEqual(cards)
  })
})

describe('groupCardsByColumn', () => {
  it('agrupa por columna conservando el orden relativo', () => {
    const cards = [
      makeCard('a1', COLUMN_A, 0),
      makeCard('b1', COLUMN_B, 0),
      makeCard('a2', COLUMN_A, 1),
    ]

    const grouped = groupCardsByColumn(cards)

    expect(grouped.get(COLUMN_A)?.map((card) => card.id)).toEqual(['a1', 'a2'])
    expect(grouped.get(COLUMN_B)?.map((card) => card.id)).toEqual(['b1'])
  })
})
