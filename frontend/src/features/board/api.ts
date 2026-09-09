import { apiClient } from '@/api/client'
import type { components } from '@/api/schema'

export type Board = components['schemas']['BoardRead']
export type BoardColumn = components['schemas']['ColumnRead']
export type Card = components['schemas']['CardRead']
export type CardMove = components['schemas']['CardMove']

export const boardKeys = {
  all: ['boards'] as const,
  lists: () => [...boardKeys.all, 'list'] as const,
  detail: (boardId: string) => [...boardKeys.all, 'detail', boardId] as const,
  columns: (boardId: string) => [...boardKeys.detail(boardId), 'columns'] as const,
  cards: (boardId: string) => [...boardKeys.detail(boardId), 'cards'] as const,
}

/**
 * Nothing in this app paginates columns or cards — the board is viewed whole. 100
 * is the max `PaginationParams` accepts; a board past that many columns or cards in
 * total is a known limit of this screen, not handled here.
 */
const MAX_PAGE_SIZE = 100

export async function fetchBoards(): Promise<Board[]> {
  const { data, response } = await apiClient.GET('/api/v1/boards', {
    params: { query: { size: MAX_PAGE_SIZE } },
  })

  if (!data || !response.ok) {
    throw new Error(`No se pudieron cargar los tableros (HTTP ${String(response.status)}).`)
  }

  return data.items
}

export async function fetchBoard(boardId: string): Promise<Board> {
  const { data, response } = await apiClient.GET('/api/v1/boards/{board_id}', {
    params: { path: { board_id: boardId } },
  })

  if (!data || !response.ok) {
    throw new Error(`No se pudo cargar el tablero (HTTP ${String(response.status)}).`)
  }

  return data
}

export async function fetchBoardColumns(boardId: string): Promise<BoardColumn[]> {
  const { data, response } = await apiClient.GET('/api/v1/boards/{board_id}/columns', {
    params: { path: { board_id: boardId }, query: { size: MAX_PAGE_SIZE } },
  })

  if (!data || !response.ok) {
    throw new Error(`No se pudieron cargar las columnas (HTTP ${String(response.status)}).`)
  }

  return data.items
}

export async function fetchBoardCards(boardId: string): Promise<Card[]> {
  const { data, response } = await apiClient.GET('/api/v1/boards/{board_id}/cards', {
    params: { path: { board_id: boardId }, query: { size: MAX_PAGE_SIZE } },
  })

  if (!data || !response.ok) {
    throw new Error(`No se pudieron cargar las tarjetas (HTTP ${String(response.status)}).`)
  }

  return data.items
}

/** The backend's error body is `{ detail: "..." }`, already in Spanish. */
function extractErrorDetail(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    return typeof error.detail === 'string' ? error.detail : undefined
  }
  return undefined
}

export async function moveCard(boardId: string, cardId: string, move: CardMove): Promise<Card> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/boards/{board_id}/cards/{card_id}/move',
    {
      params: { path: { board_id: boardId, card_id: cardId } },
      body: move,
    },
  )

  if (data) {
    return data
  }

  if (response.status === 404) {
    throw new Error('No se pudo mover la tarjeta.')
  }

  throw new Error(extractErrorDetail(error) ?? 'No se pudo mover la tarjeta.')
}
