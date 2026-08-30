import createClient from 'openapi-fetch'

import type { paths } from '@/api/schema'
import { notifyUnauthorized } from '@/lib/authEvents'

/**
 * Absolute on purpose. A relative base URL works in the browser but makes
 * `new Request('/api/…')` throw under Node/undici (jsdom tests included), so the
 * origin is resolved explicitly.
 *
 * In development that origin is Vite's, whose proxy forwards /api to the backend.
 * Set VITE_API_BASE_URL when the API is served from somewhere else.
 */
const baseUrl = import.meta.env.VITE_API_BASE_URL || globalThis.location.origin

const UNAUTHORIZED = 401

// A 401 here means "wrong credentials", not "the session died" — the normal
// failure mode of a login attempt, including one made by someone who already
// has a *different*, still-valid session open in another tab. Letting it
// through would wipe that real session out of the cache for nothing.
const LOGIN_PATH = '/api/v1/auth/login'

/** Typed against the backend's OpenAPI: every path and payload is checked. */
export const apiClient = createClient<paths>({
  baseUrl,
  // Sessions are an httpOnly cookie (TASK-03): without this the browser never
  // stores it, nor sends it back on the next request. Same origin in dev thanks
  // to Vite's proxy, so this needs no CORS credentials dance.
  credentials: 'include',
  // Looked up on every call instead of captured when this module is imported, so
  // a test can swap globalThis.fetch after the import has already happened.
  fetch: (request) => globalThis.fetch(request),
})

// Centralized 401 handling: every response funnels through here, so no feature
// has to special-case "the session died" on its own. See lib/authEvents.ts for
// why this is an event rather than a direct QueryClient write.
apiClient.use({
  onResponse({ response, schemaPath }) {
    if (response.status === UNAUTHORIZED && schemaPath !== LOGIN_PATH) {
      notifyUnauthorized()
    }
  },
})
