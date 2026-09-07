import { VAPID_PUBLIC_KEY } from "../config";
import { saveSubscription } from "../api/client";
import type { RawPushSubscription } from "../types";

const SW_PATH = "/sw.js";

/**
 * Registers the service worker and returns the active registration.
 * Throws if the browser doesn't support service workers.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
  if (!("serviceWorker" in navigator)) {
    throw new Error("Service workers are not supported in this browser.");
  }
  return navigator.serviceWorker.register(SW_PATH);
}

/**
 * Requests notification permission. Resolves true if granted.
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!("Notification" in window)) {
    throw new Error("Notifications are not supported in this browser.");
  }
  const permission = await Notification.requestPermission();
  return permission === "granted";
}

/**
 * Subscribes the current browser to Web Push using the app's VAPID public key,
 * then persists the subscription to the PHP backend.
 */
export async function subscribeToPush(): Promise<void> {
  const registration = await registerServiceWorker();
  const granted = await requestNotificationPermission();
  if (!granted) {
    throw new Error("Notification permission was denied.");
  }

  const existing = await registration.pushManager.getSubscription();
  const subscription =
    existing ?? (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    }));

  const raw = subscription.toJSON() as RawPushSubscription;
  await saveSubscription({
    endpoint: raw.endpoint,
    p256dh: raw.keys.p256dh,
    auth: raw.keys.auth,
  });
}

/**
 * Converts a base64url-encoded VAPID public key into a Uint8Array, which is
 * what PushManager.subscribe() expects.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}