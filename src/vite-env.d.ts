/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  readonly VITE_ALLOWED_EMAILS?: string;
  readonly VITE_ALLOWED_DOMAINS?: string;
  readonly VITE_ALLOW_DOMAIN_LOGIN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
