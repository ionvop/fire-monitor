import type { FireAlert, PushSubscriptionPayload } from "../types";

/**
 * API client for the PHP backend.
 *
 * The frontend is deployed on the same InfinityFree domain as the API, so all
 * requests use relative same-origin paths (no CORS headers are sent by the
 * host). Only GET and POST are supported by the server.
 */

const API_BASE = "/api";

/** Fetch the fire-detection history, newest first. */
export async function fetchFireHistory(): Promise<FireAlert[]> {
  const res = await fetch(`${API_BASE}/fire_history/`);
  if (!res.ok) {
    throw new Error(`Failed to load fire history (${res.status})`);
  }
  return (await res.json()) as FireAlert[];
}

/** Save (upsert) a Web Push subscription keyed on its endpoint. */
export async function saveSubscription(
  sub: PushSubscriptionPayload,
): Promise<void> {
  const res = await fetch(`${API_BASE}/subscriptions/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sub),
  });
  if (!res.ok) {
    throw new Error(`Failed to save subscription (${res.status})`);
  }
}