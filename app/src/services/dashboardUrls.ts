import {
  DASHBOARD_LAN_URL,
  DASHBOARD_TUNNEL_URL,
  DASHBOARD_URLS_STORAGE_KEY,
} from "../config";

/** The two dashboard entry points the user can reach. */
export interface DashboardUrls {
  /** Reachable when on the same network as the controller. */
  lan: string;
  /** Reachable when the dashboard port is forwarded to the internet. */
  tunnel: string;
}

/** The built-in defaults, used when nothing valid is stored. */
export const DEFAULT_DASHBOARD_URLS: DashboardUrls = {
  lan: DASHBOARD_LAN_URL,
  tunnel: DASHBOARD_TUNNEL_URL,
};

/**
 * Normalizes a user-entered URL: trims whitespace, adds a scheme when the user
 * typed a bare host (`192.168.4.2:5000`), and strips trailing slashes.
 *
 * Returns `null` when the value cannot be parsed as an absolute http(s) URL.
 */
export function normalizeUrl(
  value: string,
  fallbackScheme: "http" | "https",
): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  // The URL parser silently percent-encodes spaces in the host, so reject any
  // whitespace up front rather than accepting "http://not a url".
  if (/\s/.test(trimmed)) return null;

  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)
    ? trimmed
    : `${fallbackScheme}://${trimmed}`;

  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    return null;
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
  if (!isValidHostname(parsed.hostname)) return null;

  return parsed.href.replace(/\/+$/, "");
}

/** Accepts DNS names, IPv4 addresses, and bracketed IPv6 literals. */
function isValidHostname(hostname: string): boolean {
  if (!hostname) return false;
  if (hostname.startsWith("[") && hostname.endsWith("]")) {
    return /^\[[0-9a-f:.]+\]$/i.test(hostname);
  }
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/i.test(
    hostname,
  );
}

/**
 * Reads the stored dashboard URLs, falling back to the defaults for any field
 * that is missing, unparseable, or invalid.
 */
export function loadDashboardUrls(): DashboardUrls {
  let stored: unknown;
  try {
    const raw = localStorage.getItem(DASHBOARD_URLS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_DASHBOARD_URLS };
    stored = JSON.parse(raw);
  } catch {
    return { ...DEFAULT_DASHBOARD_URLS };
  }

  if (typeof stored !== "object" || stored === null) {
    return { ...DEFAULT_DASHBOARD_URLS };
  }

  const record = stored as Record<string, unknown>;
  return {
    lan:
      typeof record.lan === "string"
        ? (normalizeUrl(record.lan, "http") ?? DEFAULT_DASHBOARD_URLS.lan)
        : DEFAULT_DASHBOARD_URLS.lan,
    tunnel:
      typeof record.tunnel === "string"
        ? (normalizeUrl(record.tunnel, "https") ?? DEFAULT_DASHBOARD_URLS.tunnel)
        : DEFAULT_DASHBOARD_URLS.tunnel,
  };
}

/** Persists the dashboard URLs. Throws if localStorage is unavailable. */
export function saveDashboardUrls(urls: DashboardUrls): void {
  localStorage.setItem(DASHBOARD_URLS_STORAGE_KEY, JSON.stringify(urls));
}

/** Removes any stored overrides so the defaults apply again. */
export function resetDashboardUrls(): void {
  localStorage.removeItem(DASHBOARD_URLS_STORAGE_KEY);
}
