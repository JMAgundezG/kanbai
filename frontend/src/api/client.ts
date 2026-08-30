import createClient from 'openapi-fetch'

import type { paths } from '@/api/schema'

/**
 * Absolute on purpose. A relative base URL works in the browser but makes
 * `new Request('/api/…')` throw under Node/undici (jsdom tests included), so the
 * origin is resolved explicitly.
 *
 * In development that origin is Vite's, whose proxy forwards /api to the backend.
 * Set VITE_API_BASE_URL when the API is served from somewhere else.
 */
const baseUrl = import.meta.env.VITE_API_BASE_URL || globalThis.location.origin

/** Typed against the backend's OpenAPI: every path and payload is checked. */
export const apiClient = createClient<paths>({
  baseUrl,
  // Looked up on every call instead of captured when this module is imported, so
  // a test can swap globalThis.fetch after the import has already happened.
  fetch: (request) => globalThis.fetch(request),
})
