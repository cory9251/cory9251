// FRD Addendum B — shared display helpers for specialist project gigs.

export const isSpecialist = (g) => g?.template === "specialist_project";

// Open variable (range pay or TBD date) → "I'm Interested" instead of Claim.
export const takesInterestOnly = (g) =>
  isSpecialist(g) && (g.pay_mode === "range" || g.date_mode === "tbd");

const fmt$ = (n) => {
  const v = Number(n || 0);
  return `$${v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)}`;
};

const trimNum = (n) => {
  const v = Number(n || 0);
  return v % 1 === 0 ? String(v.toFixed(0)) : String(v);
};

export const estRange = (g) => {
  if (!g?.est_hours_min) return null;
  const a = trimNum(g.est_hours_min);
  const b = trimNum(g.est_hours_max);
  return a === b ? `${a} hr${a === "1" ? "" : "s"}` : `${a}–${b} hrs`;
};

export const payLine = (g) => {
  if (!isSpecialist(g) || !g.pay_mode) return null;
  if (g.pay_mode === "flat") return `${fmt$(g.pay_rate)} flat`;
  if (g.pay_mode === "hourly_estimate")
    return `${fmt$(g.pay_rate)}/hr · est ${estRange(g) || "?"}`;
  return `${fmt$(g.pay_range_min)}–${fmt$(g.pay_range_max)}`;
};

export const payReason = (g) =>
  isSpecialist(g) && g.pay_mode === "range" ? g.pay_range_reason : null;

const shortDay = (s) => {
  try {
    const [y, m, d] = String(s).split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return s;
  }
};

export const dateLine = (g) => {
  if (!isSpecialist(g)) return null;
  if (g.date_mode === "window" && g.window_start)
    return `${shortDay(g.window_start)}–${shortDay(g.window_end)} — pick your day`;
  if (g.date_mode === "tbd") return "Flexible scheduling — we'll work around you";
  return null; // fixed → normal date display
};

export const scopeLine = (g) => {
  if (!isSpecialist(g)) return null;
  const parts = [];
  if (g.quantity_count)
    parts.push(`${trimNum(g.quantity_count)} ${g.quantity_unit || ""}`.trim());
  if ((g.materials_provided || []).length) parts.push("materials provided");
  else if ((g.materials_bring || []).length) parts.push("bring your equipment");
  const est = estRange(g);
  if (est) parts.push(`est. ${est}`);
  return parts.join(" · ") || null;
};

// List of YYYY-MM-DD days inside the posted window (capped at 31).
export const windowDays = (g) => {
  if (!g?.window_start || !g?.window_end) return [];
  const out = [];
  const [y, m, d] = g.window_start.split("-").map(Number);
  let cur = new Date(y, m - 1, d);
  for (let i = 0; i < 31; i++) {
    const iso = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`;
    if (iso > g.window_end) break;
    out.push(iso);
    cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
  }
  return out;
};

export const dayLabel = (iso) => {
  try {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
};
