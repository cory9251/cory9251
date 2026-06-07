// Web Push helpers — register the service worker, ask for permission, post
// the resulting PushSubscription to our backend, and surface platform-specific
// hints (e.g. iOS needs PWA install before push works).
import { api, getErr } from "@/lib/api";

const SW_URL = "/sw.js";

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let bin = "";
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return window.btoa(bin);
}

export function detectPlatform() {
  const ua = navigator.userAgent || "";
  if (/iPad|iPhone|iPod/.test(ua) && !window.MSStream) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "other";
}

export function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

export function canPush() {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function pushPermission() {
  if (!("Notification" in window)) return "unsupported";
  return Notification.permission; // "default" | "granted" | "denied"
}

/**
 * Returns a high-level state the UI can render directly:
 *   - "unsupported"  → browser can't do push at all
 *   - "ios_needs_pwa" → iOS Safari, not yet installed to home screen
 *   - "blocked"      → user clicked Block previously
 *   - "available"    → ready to ask & subscribe
 *   - "enabled"      → already subscribed (caller should also check /api/push/status)
 */
export function pushReadiness() {
  if (!canPush()) {
    const platform = detectPlatform();
    if (platform === "ios" && !isStandalone()) return "ios_needs_pwa";
    return "unsupported";
  }
  const p = pushPermission();
  if (p === "denied") return "blocked";
  if (p === "granted") return "enabled";
  return "available";
}

async function fetchPublicKey() {
  const { data } = await api.get("/push/public-key");
  return data.public_key;
}

/**
 * Triggers the browser permission prompt (if not granted yet), creates a
 * PushSubscription, and POSTs it to our backend. Returns the subscription on
 * success and throws on failure.
 */
export async function enablePush() {
  if (!canPush()) throw new Error("Push notifications aren't supported on this browser.");
  const reg = await navigator.serviceWorker.register(SW_URL);
  await navigator.serviceWorker.ready;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      permission === "denied"
        ? "You blocked notifications. Allow them from your browser settings to receive gig alerts."
        : "Notifications were not allowed."
    );
  }

  const publicKey = await fetchPublicKey();
  const applicationServerKey = urlBase64ToUint8Array(publicKey);

  // Re-use an existing subscription if the browser kept one.
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
  }

  const json = sub.toJSON();
  await api.post("/push/subscribe", {
    endpoint: json.endpoint,
    keys: {
      p256dh: json.keys?.p256dh || arrayBufferToBase64(sub.getKey("p256dh")),
      auth: json.keys?.auth || arrayBufferToBase64(sub.getKey("auth")),
    },
    user_agent: navigator.userAgent,
    platform: detectPlatform(),
  });

  return sub;
}

export async function disablePush() {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.getRegistration(SW_URL);
  if (!reg) return;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return;
  try {
    await api({
      url: "/push/subscribe",
      method: "DELETE",
      data: { endpoint: sub.endpoint },
    });
  } catch (e) {
    // ignore network errors — we'll still unsubscribe locally
    console.warn("Failed to unregister on server:", getErr(e));
  }
  await sub.unsubscribe();
}

export async function sendTestPush() {
  const { data } = await api.post("/push/test", {});
  return data;
}

/**
 * Lightweight server-status fetch — caller renders enabled / device count.
 */
export async function getPushStatus() {
  try {
    const { data } = await api.get("/push/status");
    return data;
  } catch (e) {
    return { enabled: false, device_count: 0, server_configured: false };
  }
}
