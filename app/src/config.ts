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

/**
 * Default URL of the controller dashboard when the phone is on the same
 * network as the controller (the ESP32 access point / LAN address).
 */
export const DASHBOARD_LAN_URL = "http://192.168.4.2:5000";

/**
 * Default URL of the controller dashboard when port forwarding exposes it to
 * the internet through a dev tunnel. Replace with your own tunnel host.
 */
export const DASHBOARD_TUNNEL_URL = "https://abc123-5000.asse.devtunnels.ms/";

/**
 * localStorage key holding the user's dashboard URL overrides as JSON:
 * `{ "lan": string, "tunnel": string }`. Absent or invalid values fall back to
 * the defaults above.
 */
export const DASHBOARD_URLS_STORAGE_KEY = "fire-monitor.dashboard-urls";