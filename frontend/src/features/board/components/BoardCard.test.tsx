import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Card } from '@/features/board/api'
import { BoardCard } from '@/features/board/components/BoardCard'

function makeCard(overrides: Partial<Card> = {}): Card {
  return {
    id: 'card-1',
    board_id: 'board-1',
    column_id: 'column-1',
    title: 'Escribir la spec',
    description: null,
    position: 0,
    created_by_actor_id: 'actor-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('BoardCard', () => {
  it('pinta el título', () => {
    render(<BoardCard card={makeCard()} />)

    expect(screen.getByText('Escribir la spec')).toBeInTheDocument()
  })

  it('pinta la descripción cuando existe', () => {
    render(<BoardCard card={makeCard({ description: 'Antes de implementar' })} />)

    expect(screen.getByText('Antes de implementar')).toBeInTheDocument()
  })

  it('sin descripción no revienta', () => {
    render(<BoardCard card={makeCard({ description: null })} />)

    expect(screen.getByText('Escribir la spec')).toBeInTheDocument()
  })
})
