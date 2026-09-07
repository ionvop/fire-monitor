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
  /** Detection confidence (0.0 - 1.0), if reported. */
  confidence_score: number | null;
  /** Lifecycle status: "detected" while firing, "retracted" after. */
  status: string;
  /** Servo pan angle at detection, if reported. */
  x: number | null;
  /** Servo tilt angle at detection, if reported. */
  y: number | null;
  /** URL of the annotated capture image, if one was saved. */
  capture_image_url: string | null;
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