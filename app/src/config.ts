/**
 * App-wide configuration.
 *
 * VAPID_PUBLIC_KEY: the public half of the Web Push VAPID key pair. It is
 * embedded in the client so the browser can subscribe. The matching PRIVATE
 * key must live only on the server (used by the Phase 3 push sender) — never
 * ship it in this bundle.
 *
 * Generate a pair with:  npx web-push generate-vapid-keys
 */
export const VAPID_PUBLIC_KEY =
  "BP2Z7ufEgIke5I-VCVCf-fKfJIgYz_TC8pJThQBxRFJAofgzDA0TPIuOIDog0oWqpPX0tDSu3raBj4Gfg-DzYg4";

/** How often (ms) the fire-history list polls the API for updates. */
export const POLL_INTERVAL_MS = 5000;

/** Maximum number of alerts to keep in the on-screen list. */
export const MAX_ALERTS = 50;