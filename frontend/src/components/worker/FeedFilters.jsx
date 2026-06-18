import React, { useMemo, useState } from "react";
import {
  Funnel,
  CaretDown,
  X,
  Lightning,
} from "@phosphor-icons/react";

/**
 * Sort options for any gig list. Each entry includes a compare function that
 * receives two enriched gigs (with `getGigDate`-style fields) and returns the
 * standard JS sort delta.
 *
 * Exported separately from the component so consumers can also sort headless
 * (e.g. when memoising a filtered+sorted array for the empty-state branch).
 */
export const SORT_OPTIONS = [
  { key: "newest", label: "Newest" },
  { key: "soonest", label: "Soonest start" },
  { key: "pay_high", label: "Highest pay" },
  { key: "closest", label: "Closest (zip)" },
];

export const DATE_RANGE_OPTIONS = [
  { key: "any", label: "Any date" },
  { key: "today", label: "Today" },
  { key: "tomorrow", label: "Tomorrow" },
  { key: "this_week", label: "This week" },
  { key: "next_7", label: "Next 7 days" },
  { key: "next_30", label: "Next 30 days" },
];

export const DEFAULT_FILTERS = {
  sort: "newest",
  category: "all",
  pay_min: "",
  date_range: "any",
  zip_prefix: "",
  rush_only: false,
  open_slots_only: false,
};

/**
 * Reusable header for any worker feed: search + sort dropdown + collapsible
 * filter panel + active-filter chips. Pure presentational — pass `value` /
 * `onChange` and we render. The parent applies the filters to its data.
 *
 * Layout intentionally collapses to a single row on mobile and expands on
 * tap, since this lives at the top of /crew and we don't want to push gig
 * cards below the fold on a phone.
 */
export default function FeedFilters({
  value,
  onChange,
  showCategory = true,
  showSlotsToggle = true,
  showRushToggle = true,
  showDateRange = true,
  categoryOptions = DEFAULT_CATEGORY_OPTIONS,
  resultCount,
  totalCount,
  testIdPrefix = "feed-filters",
}) {
  const [open, setOpen] = useState(false);

  const v = { ...DEFAULT_FILTERS, ...(value || {}) };
  const set = (patch) => onChange?.({ ...v, ...patch });

  const activeChips = useMemo(() => {
    const chips = [];
    if (v.category && v.category !== "all") chips.push({ key: "category", label: labelFor(v.category, categoryOptions), onClear: () => set({ category: "all" }) });
    if (v.date_range && v.date_range !== "any") chips.push({ key: "date_range", label: labelFor(v.date_range, DATE_RANGE_OPTIONS), onClear: () => set({ date_range: "any" }) });
    if (v.pay_min) chips.push({ key: "pay_min", label: `≥ $${v.pay_min}`, onClear: () => set({ pay_min: "" }) });
    if (v.zip_prefix) chips.push({ key: "zip", label: `ZIP ${v.zip_prefix}…`, onClear: () => set({ zip_prefix: "" }) });
    if (v.rush_only) chips.push({ key: "rush", label: "Rush only", onClear: () => set({ rush_only: false }) });
    if (v.open_slots_only) chips.push({ key: "open", label: "Has open slots", onClear: () => set({ open_slots_only: false }) });
    return chips;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v, categoryOptions]);

  const activeCount = activeChips.length;

  const clearAll = () => onChange?.({ ...DEFAULT_FILTERS, sort: v.sort }); // keep sort, reset filters

  return (
    <div data-testid={testIdPrefix} className="mt-4">
      {/* Single-row control bar: Filters toggle + Sort dropdown */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          data-testid={`${testIdPrefix}-toggle`}
          type="button"
          onClick={() => setOpen((x) => !x)}
          className={`inline-flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm font-bold transition-colors ${
            open ? "border-[#0044FF] bg-[#0044FF] text-white" : "border-[#030712] bg-white text-[#030712] hover:bg-[#F9FAFB]"
          }`}
        >
          <Funnel size={14} weight="fill" />
          Filters
          {activeCount > 0 && (
            <span
              data-testid={`${testIdPrefix}-active-count`}
              className={`grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-[10px] font-black ${
                open ? "bg-white text-[#0044FF]" : "bg-[#0044FF] text-white"
              }`}
            >
              {activeCount}
            </span>
          )}
          <CaretDown size={12} weight="bold" className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>

        <div className="relative flex-1 min-w-[140px]">
          <select
            data-testid={`${testIdPrefix}-sort`}
            value={v.sort}
            onChange={(e) => set({ sort: e.target.value })}
            className="h-10 w-full appearance-none rounded-2xl border border-[#030712] bg-white px-3 pr-8 text-sm font-bold text-[#030712]"
          >
            {SORT_OPTIONS.map((s) => (
              <option key={s.key} value={s.key}>Sort: {s.label}</option>
            ))}
          </select>
          <CaretDown size={12} weight="bold" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#030712]" />
        </div>

        {(typeof resultCount === "number" || typeof totalCount === "number") && (
          <div
            data-testid={`${testIdPrefix}-result-count`}
            className="font-mono-label whitespace-nowrap text-[10px] uppercase tracking-widest text-[#4B5563]"
          >
            {resultCount ?? totalCount}{totalCount != null && resultCount !== totalCount ? ` / ${totalCount}` : ""} shown
          </div>
        )}
      </div>

      {/* Active filter chips */}
      {activeChips.length > 0 && (
        <div data-testid={`${testIdPrefix}-chips`} className="mt-2 flex flex-wrap items-center gap-1.5">
          {activeChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              data-testid={`${testIdPrefix}-chip-${chip.key}`}
              onClick={chip.onClear}
              className="group inline-flex items-center gap-1 rounded-full border border-[#0044FF]/40 bg-[#EFF6FF] px-2.5 py-1 text-[11px] font-semibold text-[#0044FF] hover:bg-[#DBEAFE]"
            >
              {chip.label}
              <X size={11} weight="bold" className="opacity-60 group-hover:opacity-100" />
            </button>
          ))}
          <button
            type="button"
            data-testid={`${testIdPrefix}-clear-all`}
            onClick={clearAll}
            className="text-[11px] font-bold text-[#EF4444] hover:underline"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Expanded filter panel */}
      {open && (
        <div
          data-testid={`${testIdPrefix}-panel`}
          className="mt-3 space-y-3 rounded-2xl border border-[#E5E7EB] bg-white p-4"
        >
          {showCategory && (
            <Row label="Category">
              <select
                data-testid={`${testIdPrefix}-category`}
                value={v.category}
                onChange={(e) => set({ category: e.target.value })}
                className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
              >
                {categoryOptions.map((c) => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            </Row>
          )}

          {showDateRange && (
            <Row label="When">
              <select
                data-testid={`${testIdPrefix}-date-range`}
                value={v.date_range}
                onChange={(e) => set({ date_range: e.target.value })}
                className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
              >
                {DATE_RANGE_OPTIONS.map((d) => (
                  <option key={d.key} value={d.key}>{d.label}</option>
                ))}
              </select>
            </Row>
          )}

          <Row label="Minimum pay">
            <div className="flex items-center gap-1">
              <span className="font-mono-label text-sm text-[#4B5563]">$</span>
              <input
                data-testid={`${testIdPrefix}-pay-min`}
                type="number"
                min="0"
                inputMode="numeric"
                value={v.pay_min}
                onChange={(e) => set({ pay_min: e.target.value.replace(/[^0-9.]/g, "") })}
                placeholder="0"
                className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
              />
              <span className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">/HR OR FIXED</span>
            </div>
          </Row>

          <Row label="ZIP starts with">
            <input
              data-testid={`${testIdPrefix}-zip-prefix`}
              type="text"
              inputMode="numeric"
              maxLength={5}
              value={v.zip_prefix}
              onChange={(e) => set({ zip_prefix: e.target.value.replace(/[^0-9]/g, "") })}
              placeholder="e.g. 212 for nearby Baltimore"
              className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
            />
          </Row>

          <div className="flex flex-wrap gap-2">
            {showRushToggle && (
              <Toggle
                testId={`${testIdPrefix}-rush-only`}
                active={v.rush_only}
                onClick={() => set({ rush_only: !v.rush_only })}
                icon={Lightning}
              >
                Rush only
              </Toggle>
            )}
            {showSlotsToggle && (
              <Toggle
                testId={`${testIdPrefix}-open-slots-only`}
                active={v.open_slots_only}
                onClick={() => set({ open_slots_only: !v.open_slots_only })}
              >
                Open slots only
              </Toggle>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const DEFAULT_CATEGORY_OPTIONS = [
  { key: "all", label: "All categories" },
  { key: "cleaning", label: "Cleaning" },
  { key: "labor", label: "Labor" },
  { key: "driver", label: "Driver / Ride" },
];

function labelFor(key, options) {
  return options.find((o) => o.key === key)?.label || key;
}

function Row({ label, children }) {
  return (
    <div>
      <div className="font-mono-label mb-1 text-[10px] uppercase tracking-widest text-[#4B5563]">{label}</div>
      {children}
    </div>
  );
}

function Toggle({ active, onClick, children, testId, icon: I }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${
        active
          ? "border-[#0044FF] bg-[#0044FF] text-white"
          : "border-[#E5E7EB] bg-white text-[#030712] hover:bg-[#F9FAFB]"
      }`}
    >
      {I ? <I size={11} weight="fill" /> : null}
      {children}
    </button>
  );
}

/**
 * Pure helper that takes a list of gig objects + the current filter state
 * and returns a new (filtered, sorted) list. Lives here so both feeds share
 * identical semantics.
 *
 * @param {Array} gigs
 * @param {object} filters - shape of DEFAULT_FILTERS
 * @param {string} workerZip - the signed-in worker's zip, used for "Closest" sort
 */
export function applyFeedFilters(gigs, filters, workerZip) {
  const v = { ...DEFAULT_FILTERS, ...(filters || {}) };
  let out = [...(gigs || [])];

  if (v.category && v.category !== "all") {
    out = out.filter((g) => g.category === v.category);
  }
  if (v.pay_min) {
    const min = Number(v.pay_min) || 0;
    out = out.filter((g) => Number(g.pay_rate || 0) >= min);
  }
  if (v.zip_prefix) {
    const px = v.zip_prefix;
    out = out.filter((g) => String(g.zip_code || g.location_zip || "").startsWith(px));
  }
  if (v.rush_only) {
    out = out.filter((g) => !!g.is_rush);
  }
  if (v.open_slots_only) {
    out = out.filter((g) => {
      const slots = Number(g.slots ?? 0);
      const filled = Number(g.slots_filled ?? 0);
      return slots === 0 || filled < slots; // 0 means "unlimited / open"
    });
  }
  if (v.date_range && v.date_range !== "any") {
    out = out.filter((g) => matchesDateRange(g, v.date_range));
  }

  // Sort
  if (v.sort === "soonest") {
    out.sort((a, b) => safeStartMs(a) - safeStartMs(b));
  } else if (v.sort === "pay_high") {
    out.sort((a, b) => Number(b.pay_rate || 0) - Number(a.pay_rate || 0));
  } else if (v.sort === "closest" && workerZip) {
    out.sort((a, b) => zipDistance(a, workerZip) - zipDistance(b, workerZip));
  } else {
    // newest (default): backend already returns newest first, but re-sort
    // by created_at desc just in case
    out.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  }

  return out;
}

function safeStartMs(gig) {
  // Inline reimplementation so this file doesn't have to import gigDate
  // (and conversely so consumers only need to import THIS file).
  const local = gig?.scheduled_local;
  if (local && typeof local === "string") {
    const m = local.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (m) {
      const [, y, mo, d, h, mi] = m;
      return new Date(+y, +mo - 1, +d, +h, +mi).getTime();
    }
  }
  if (gig?.scheduled_at) {
    const t = new Date(gig.scheduled_at).getTime();
    if (!isNaN(t)) return t;
  }
  return Number.POSITIVE_INFINITY;
}

function zipDistance(gig, workerZip) {
  const gigZip = String(gig.zip_code || gig.location_zip || "");
  if (!gigZip) return Number.POSITIVE_INFINITY;
  // Compare digit-by-digit prefix match: more matching leading digits = closer.
  // Not Haversine but cheap, no network, and correlates well within Baltimore.
  let match = 0;
  for (let i = 0; i < Math.min(gigZip.length, workerZip.length); i++) {
    if (gigZip[i] === workerZip[i]) match++;
    else break;
  }
  return -match; // bigger match = smaller distance
}

function matchesDateRange(gig, range) {
  const start = safeStartMs(gig);
  if (!isFinite(start)) return range === "any";
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const endOfToday = startOfToday + 24 * 60 * 60 * 1000;
  switch (range) {
    case "today":
      return start >= startOfToday && start < endOfToday;
    case "tomorrow":
      return start >= endOfToday && start < endOfToday + 24 * 60 * 60 * 1000;
    case "this_week": {
      // End of week = upcoming Sunday 23:59
      const day = now.getDay(); // 0 = Sun
      const daysUntilSun = 7 - day;
      const endOfWeek = startOfToday + daysUntilSun * 24 * 60 * 60 * 1000;
      return start >= startOfToday && start < endOfWeek;
    }
    case "next_7":
      return start >= startOfToday && start < startOfToday + 7 * 24 * 60 * 60 * 1000;
    case "next_30":
      return start >= startOfToday && start < startOfToday + 30 * 24 * 60 * 60 * 1000;
    default:
      return true;
  }
}
