/* Fire Monitor service worker.
 *
 * Handles the background `push` event and shows a system notification. The
 * notification payload is sent by the server (Phase 3) as JSON with a `title`
 * and `body`. If no payload is present, a sensible default is shown.
 */

self.addEventListener("install", () => {
  // Activate immediately; don't wait for old tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let title = "Fire detected";
  let body = "The controller has detected a fire.";
  let data = {};

  if (event.data) {
    try {
      const payload = event.data.json();
      title = payload.title ?? title;
      body = payload.body ?? body;
      data = payload.data ?? {};
    } catch {
      // Payload wasn't JSON — fall back to the raw text.
      body = event.data.text() || body;
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: "fire-alert",
      renotify: true,
      data,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(
      (clientList) => {
        for (const client of clientList) {
          if ("focus" in client) {
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow("/");
        }
      },
    ),
  );
});