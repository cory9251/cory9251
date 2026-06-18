/**
 * Wall-clock time helpers for gigs.
 *
 * A gig has three date-related fields:
 *   - `scheduled_local`: "YYYY-MM-DDTHH:mm" — the wall-clock string the admin
 *      entered (NO timezone). This is the single source of truth for display.
 *      The hour shown on the worker's phone matches the hour at the job site
 *      regardless of where the worker happens to be.
 *   - `scheduled_at`: ISO 8601 with timezone (usually UTC). Used for sorting
 *      and as a legacy fallback when `scheduled_local` is missing.
 *   - `scheduled_date`: a pre-formatted display string. Used as the last-
 *      resort fallback when neither of the above is parseable.
 */

import { format, formatDistanceToNowStrict, isToday, isTomorrow, isYesterday, addHours } from "date-fns";

/**
 * Returns a JS `Date` representing the gig's wall-clock time in the browser's
 * local timezone. Two gigs at "9:00 AM" anywhere in the world will both
 * return a Date whose `getHours()` is 9.
 */
export function getGigDate(gig) {
  if (!gig) return null;
  const local = gig.scheduled_local;
  if (local && typeof local === "string") {
    // Naive ISO string (no Z, no offset) → JS treats as local. We construct
    // explicitly to avoid any browser ambiguity around the legacy
    // `new Date("2026-03-14T09:00")` parsing.
    const m = local.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (m) {
      const [, y, mo, d, h, mi] = m;
      return new Date(
        parseInt(y, 10),
        parseInt(mo, 10) - 1,
        parseInt(d, 10),
        parseInt(h, 10),
        parseInt(mi, 10),
        0,
        0
      );
    }
  }
  if (gig.scheduled_at) {
    const dt = new Date(gig.scheduled_at);
    if (!isNaN(dt.getTime())) return dt;
  }
  return null;
}

function maybeEnd(gig, start) {
  const hrs = Number(gig?.duration_hours || 0);
  if (!start || !hrs || hrs <= 0) return null;
  return addHours(start, hrs);
}

function dayPrefix(d, opts = { shortMonth: false }) {
  if (!d) return "";
  if (isToday(d)) return "Today";
  if (isTomorrow(d)) return "Tomorrow";
  if (isYesterday(d)) return "Yesterday";
  return format(d, opts.shortMonth ? "EEE MMM d" : "EEE, MMM d");
}

function timeStr(d) {
  if (!d) return "";
  const mi = d.getMinutes();
  return mi === 0 ? format(d, "h a") : format(d, "h:mm a");
}

/**
 * Compact relative format ideal for cards: "Today · 9 AM – 5 PM",
 * "Tomorrow · 9 AM", "Fri Mar 14 · 9 AM".
 * Falls back to `gig.scheduled_date` if no date can be derived.
 */
export function formatGigWhen(gig) {
  const d = getGigDate(gig);
  if (!d) return gig?.scheduled_date || "Flexible";
  const end = maybeEnd(gig, d);
  const day = dayPrefix(d, { shortMonth: true });
  const startTxt = timeStr(d);
  if (end) return `${day} · ${startTxt} – ${timeStr(end)}`;
  return `${day} · ${startTxt}`;
}

/**
 * Slightly longer one-line label for detail pages: e.g.
 * "Friday, March 14 · 9:00 AM – 5:00 PM (8h)".
 */
export function formatGigLong(gig) {
  const d = getGigDate(gig);
  if (!d) return gig?.scheduled_date || "Flexible";
  const end = maybeEnd(gig, d);
  const day = isToday(d)
    ? `Today, ${format(d, "MMMM d")}`
    : isTomorrow(d)
    ? `Tomorrow, ${format(d, "MMMM d")}`
    : format(d, "EEEE, MMMM d");
  const startTxt = timeStr(d);
  const hrs = Number(gig?.duration_hours || 0);
  if (end) {
    return `${day} · ${startTxt} – ${timeStr(end)} (${hrs}h)`;
  }
  return `${day} · ${startTxt}`;
}

/**
 * Short label for chips/lists: "Fri Mar 14 · 9 AM".
 */
export function formatGigShort(gig) {
  const d = getGigDate(gig);
  if (!d) return gig?.scheduled_date || "Flexible";
  return `${format(d, "EEE MMM d")} · ${timeStr(d)}`;
}

/**
 * "Starts in 3h", "Started 20m ago" — useful next to a CTA.
 */
export function formatGigRelative(gig) {
  const d = getGigDate(gig);
  if (!d) return "";
  const ms = d.getTime() - Date.now();
  if (Math.abs(ms) < 60_000) return ms >= 0 ? "Starts now" : "Just started";
  const dist = formatDistanceToNowStrict(d, { addSuffix: false });
  return ms >= 0 ? `Starts in ${dist}` : `Started ${dist} ago`;
}

/**
 * True when the gig is happening today (wall-clock).
 */
export function isGigToday(gig) {
  const d = getGigDate(gig);
  return d ? isToday(d) : false;
}

/**
 * True when the gig is happening tomorrow (wall-clock).
 */
export function isGigTomorrow(gig) {
  const d = getGigDate(gig);
  return d ? isTomorrow(d) : false;
}


/**
 * Full date + time for feed cards — what workers want to see at a glance.
 * Example: "Fri, Mar 14, 2026 · 9:00 AM – 5:00 PM" or "Today · 9:00 AM – 5:00 PM".
 * Today/Tomorrow get word labels prepended so the worker doesn't have to
 * mentally translate the date.
 */
export function formatGigFull(gig) {
  const d = getGigDate(gig);
  if (!d) return gig?.scheduled_date || "Flexible";
  const end = maybeEnd(gig, d);
  const day = isToday(d)
    ? `Today · ${format(d, "EEE, MMM d, yyyy")}`
    : isTomorrow(d)
    ? `Tomorrow · ${format(d, "EEE, MMM d, yyyy")}`
    : format(d, "EEE, MMM d, yyyy");
  const startTxt = format(d, "h:mm a");
  if (end) return `${day} · ${startTxt} – ${format(end, "h:mm a")}`;
  return `${day} · ${startTxt}`;
}

/**
 * Pure numeric epoch (ms) for the gig start time. Returns Infinity when no
 * date can be parsed so undated gigs sort to the END of "Soonest first".
 */
export function gigStartMs(gig) {
  const d = getGigDate(gig);
  return d ? d.getTime() : Number.POSITIVE_INFINITY;
}
