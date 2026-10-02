/**
 * Shared data types matching the PHP/SQLite backend schema.
 *
 * See `public/api/tools/schema.sql` and the endpoint handlers in
 * `public/api/fire_history/index.php` and `public/api/subscriptions/index.php`.
 */

/** A single fire-detection record from the `fire_history` table. */
export interface FireAlert {
  id: number;
  /** ISO-8601 timestamp string (UTC), e.g. "2026-09-07 12:34:56". */
  timestamp: string;
  /** Hottest-pixel temperature in Celsius at the transition, if reported. */
  temperature_c: number | null;
  /** Lifecycle status: "detected" while firing, "retracted" after. */
  status: string;
}

/** A Web Push subscription as stored in the `subscriptions` table. */
export interface PushSubscriptionPayload {
  endpoint: string;
  p256dh: string;
  auth: string;
}

/** The JSON body the browser's PushManager produces. */
export interface RawPushSubscription {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}