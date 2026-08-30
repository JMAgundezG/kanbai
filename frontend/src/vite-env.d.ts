/// <reference types="vite/client" />

/** Typed explicitly: vite/client declares env vars as `any`, which would leak an
 *  untyped value into the API client. */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
