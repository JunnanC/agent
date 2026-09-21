/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_VERSION?: string
  readonly VITE_OPENAPI_REVISION?: string
  readonly VITE_GIT_REVISION?: string
  readonly VITE_BUILD_TIME?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

