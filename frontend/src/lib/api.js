import axios from "axios";

// Frontend and backend are always served from the SAME domain (ingress routes
// /api to the backend) in both preview and production. If the page is loaded
// from a different host than REACT_APP_BACKEND_URL (e.g. apex vs www — the
// registrar 308-redirects www→apex, which browsers reject on CORS preflight),
// prefer the page's own origin so API calls stay same-origin.
function computeBackendBase() {
  const envBase = process.env.REACT_APP_BACKEND_URL;
  try {
    const { protocol, host, origin } = window.location;
    if (!envBase) return origin;
    const envHost = new URL(envBase).host;
    const isLocal = host.startsWith("localhost") || host.startsWith("127.");
    if (!isLocal && protocol === "https:" && envHost !== host) return origin;
  } catch {
    // fall through to envBase
  }
  return envBase;
}

export const BACKEND_URL = computeBackendBase();
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function formatApiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function getErr(e) {
  return formatApiError(e?.response?.data?.detail) || e.message;
}
