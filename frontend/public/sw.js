/* HCOB Network — Web Push service worker.
 * Lives at the site root so it can intercept push events for ANY route. */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { title: "HCOB Network", body: event.data ? event.data.text() : "" };
  }

  const title = payload.title || "HCOB Network";
  const options = {
    body: payload.body || "",
    icon: "/favicon.png",
    badge: "/favicon.png",
    tag: payload.tag || "hcob-default",
    // Re-show even if a notif with the same tag is already on screen
    renotify: true,
    requireInteraction: !!payload.rush,
    data: {
      url: payload.url || "/crew",
      kind: payload.kind || "generic",
    },
    // The vibration pattern is a strong attention-grabber on Android.
    vibrate: payload.rush ? [200, 100, 200] : [120],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/crew";
  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      // If a tab on our origin is already open, focus it and navigate.
      for (const c of allClients) {
        if (c.url && typeof c.focus === "function") {
          try {
            await c.focus();
            if ("navigate" in c) {
              await c.navigate(targetUrl);
            }
            return;
          } catch (e) {
            // ignore — fall through to open a new window
          }
        }
      }
      // Otherwise open a fresh window/tab on the target URL.
      if (self.clients.openWindow) {
        await self.clients.openWindow(targetUrl);
      }
    })()
  );
});
