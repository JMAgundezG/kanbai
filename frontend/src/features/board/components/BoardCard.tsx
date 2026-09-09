import { Card } from '@heroui/react'

import type { Card as CardData } from '@/features/board/api'

interface BoardCardProps {
  card: CardData
}

/**
 * Dumb on purpose (AGENTS.md § "Componentes tontos + hooks con la lógica"): only
 * props in, markup out. No `api.ts`/`hooks.ts` import here — the drag and drop
 * mutation lives in the column that renders this, not in the card itself.
 */
export function BoardCard({ card }: BoardCardProps) {
  return (
    <Card className="cursor-grab">
      <Card.Content>
        <div className="flex flex-col gap-1">
          <span className="font-medium">{card.title}</span>
          {card.description ? (
            <span className="line-clamp-2 text-sm opacity-70">{card.description}</span>
          ) : null}
        </div>
      </Card.Content>
    </Card>
  )
}
