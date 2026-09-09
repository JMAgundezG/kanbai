import { EmptyState } from '@heroui/react'
import {
  Button,
  GridList,
  GridListItem,
  isTextDropItem,
  useDragAndDrop,
  type DropItem,
  type ItemDropTarget,
} from 'react-aria-components'

import { BoardCard } from '@/features/board/components/BoardCard'
import type { Card } from '@/features/board/api'

interface BoardColumnListProps {
  columnName: string
  cards: Card[]
  isMoving: boolean
  /** Always resolved against *this* column — the caller already knows which
   *  column it owns, via the closure it builds in BoardPage. */
  onMoveCard: (cardId: string, targetIndex: number) => void
}

// A type of our own rather than `text/plain`: with `text/plain`, any text dragged
// in from another tab or application would satisfy `acceptedDragTypes` and be read
// as a card id, and the move would fail against the API with a 422.
const CARD_MIME_TYPE = 'application/vnd.kanbai.card-id'

/** Index (within `otherCards`, i.e. the destination column with the dragged card
 *  already removed) that a drop on `target` resolves to, or `null` when the target
 *  is the dragged card's own slot — a drop that must not move anything. */
function indexForDrop(otherCards: Card[], target: ItemDropTarget): number | null {
  const targetIndex = otherCards.findIndex((card) => card.id === target.key)
  if (targetIndex === -1) {
    // react-aria offers the dragged card's own before/after slots as drop
    // targets, and those are the ones it is filtered out of: reaching this
    // branch means "dropped where it already was", not "dropped at the end".
    return null
  }
  return target.dropPosition === 'after' ? targetIndex + 1 : targetIndex
}

async function readDraggedCardId(items: DropItem[]): Promise<string | null> {
  const [item] = items
  if (!item || !isTextDropItem(item)) {
    return null
  }
  return item.getText(CARD_MIME_TYPE)
}

/**
 * One `GridList` per column, each with its **own** `useDragAndDrop` call (not one
 * instance shared across columns): `onReorder` only ever fires for a drag that
 * starts and ends in the same collection, so a cross-column move never reaches it.
 * `onInsert` (dropped between cards) and `onRootDrop` (dropped on the column
 * itself) cover that case — and since each column's hook closes over its own column here,
 * neither handler needs a column id to travel inside the drag data.
 *
 * Keyboard: focus a card, press ArrowRight to reach its drag handle, Enter to
 * start the drag, Tab to walk the drop targets (including the other columns'),
 * Enter to drop, Escape to cancel. The state machine is react-aria's; the only
 * part this component has to provide is the handle itself (see below).
 */
export function BoardColumnList({ columnName, cards, isMoving, onMoveCard }: BoardColumnListProps) {
  const { dragAndDropHooks } = useDragAndDrop({
    isDisabled: isMoving,
    getItems: (keys) => [...keys].map((key) => ({ [CARD_MIME_TYPE]: String(key) })),

    onReorder(event) {
      const [draggedKey] = event.keys
      if (draggedKey === undefined) {
        return
      }
      const otherCards = cards.filter((card) => card.id !== draggedKey)
      const targetIndex = indexForDrop(otherCards, event.target)
      if (targetIndex === null) {
        return
      }
      onMoveCard(String(draggedKey), targetIndex)
    },

    onInsert(event) {
      // react-aria-components allows an async handler here, but its own type
      // declares a `void` return — wrapping keeps `useDragAndDrop`'s callback
      // shape honest instead of quietly handing it a Promise.
      void (async () => {
        const cardId = await readDraggedCardId(event.items)
        if (!cardId) {
          return
        }
        const targetIndex = indexForDrop(cards, event.target)
        if (targetIndex === null) {
          return
        }
        onMoveCard(cardId, targetIndex)
      })()
    },

    // Dropped on the column itself rather than between two cards. react-aria
    // offers this target for a column that already has cards too — it is the
    // first stop a keyboard drag reaches on entering a column — so the card goes
    // to the end, the usual meaning of "dropped on this column".
    onRootDrop(event) {
      void (async () => {
        const cardId = await readDraggedCardId(event.items)
        if (!cardId) {
          return
        }
        onMoveCard(cardId, cards.length)
      })()
    },

    acceptedDragTypes: [CARD_MIME_TYPE],

    getDropOperation: (_target, types) => (types.has(CARD_MIME_TYPE) ? 'move' : 'cancel'),
  })

  return (
    <GridList
      aria-label={`Tarjetas de la columna ${columnName}`}
      items={cards}
      dragAndDropHooks={dragAndDropHooks}
      layout="stack"
      renderEmptyState={() => (
        <EmptyState className="rounded border border-dashed border-neutral-300 p-4 text-center text-sm opacity-70">
          Sin tarjetas
        </EmptyState>
      )}
      className="flex min-h-24 flex-col gap-2"
    >
      {(card) => (
        <GridListItem key={card.id} textValue={card.title} className="outline-none">
          <div className="flex items-stretch gap-1">
            {/* react-aria-components' GridList always builds its items with
                `hasDragButton: true`, so the row itself gets no keyboard drag
                handlers: this slot is the ONLY keyboard entry point into a drag.
                It is a react-aria Button rather than a HeroUI one because the
                `drag` slot is filled by GridListItem's own context. RAC gives it
                `pointer-events: none`, so a mouse drag still starts on the row
                underneath it — the handle is there for keyboard and screen
                reader users. */}
            <Button
              slot="drag"
              aria-label={`Mover la tarjeta ${card.title}`}
              className="cursor-grab rounded px-1 text-neutral-400 outline-none data-[focus-visible]:ring-2 data-[focus-visible]:ring-blue-500"
            >
              ⠿
            </Button>
            <div className="min-w-0 flex-1">
              <BoardCard card={card} />
            </div>
          </div>
        </GridListItem>
      )}
    </GridList>
  )
}
