import { describe, expect, it, vi } from 'vitest'

import { notifyUnauthorized, onUnauthorized } from '@/lib/authEvents'

describe('authEvents', () => {
  it('notifica a los oyentes suscritos', () => {
    const listener = vi.fn()
    onUnauthorized(listener)

    notifyUnauthorized()

    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('deja de notificar tras desuscribirse', () => {
    const listener = vi.fn()
    const unsubscribe = onUnauthorized(listener)
    unsubscribe()

    notifyUnauthorized()

    expect(listener).not.toHaveBeenCalled()
  })
})
