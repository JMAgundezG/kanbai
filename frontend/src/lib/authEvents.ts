/**
 * Minimal pub/sub to decouple `api/client.ts` from the app's `QueryClient`.
 *
 * The client has no reference to it: `App` creates its instance with
 * `useState` (TASK-02, on purpose — isolates tests from a module-level
 * singleton), so there is nothing for `api/client.ts` to import directly.
 * Instead, any 401 response notifies here, and `App` subscribes once with
 * whichever `QueryClient` instance it owns.
 */
type Listener = () => void

const listeners = new Set<Listener>()

/** Returns an unsubscribe function, ready for a `useEffect` cleanup. */
export function onUnauthorized(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function notifyUnauthorized(): void {
  for (const listener of listeners) {
    listener()
  }
}
