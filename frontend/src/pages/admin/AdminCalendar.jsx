import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  addDays,
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  startOfDay,
  startOfMonth,
  startOfWeek,
  subDays,
  subMonths,
  subWeeks,
} from "date-fns";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { getGigDate } from "@/lib/gigDate";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import {
  CaretLeft,
  CaretRight,
  Plus,
  Broom,
  Wrench,
  Car,
  Users,
  CurrencyDollar,
  Clock,
} from "@phosphor-icons/react";
import { TAG_CONFIG, getOrderedTags } from "@/lib/gigTags";

const CAT_COLOR = {
  cleaning: { bg: "bg-[#0044FF]", text: "text-white", soft: "#0044FF" },
  labor: { bg: "bg-[#030712]", text: "text-white", soft: "#030712" },
  driver: { bg: "bg-[#F59E0B]", text: "text-[#030712]", soft: "#F59E0B" },
};
const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };
const VIEW_MODES = ["month", "week", "day"];

// Heatmap step: how much each gig adds to the workload score
const computeWorkloadScore = (dayGigs) => {
  // Score = sum of slots (each open slot = 1 unit of demand)
  return dayGigs.reduce((s, g) => s + Number(g.slots || 1), 0);
};

const heatmapTint = (score, max) => {
  if (!score || max === 0) return "";
  const intensity = Math.min(1, score / Math.max(max, 1));
  // Light → dark blue tint based on intensity; switches to red when >=80% capacity
  if (intensity >= 0.8) {
    const alpha = 0.10 + intensity * 0.18;
    return `rgba(239, 68, 68, ${alpha.toFixed(3)})`;
  }
  const alpha = 0.06 + intensity * 0.22;
  return `rgba(0, 68, 255, ${alpha.toFixed(3)})`;
};

const computeDailyTotals = (dayGigs) => {
  let totalPay = 0;
  let totalHours = 0;
  let totalSlots = 0;
  let totalFilled = 0;
  for (const g of dayGigs) {
    const slots = Number(g.slots || 1);
    const hours = Number(g.duration_hours || 0);
    const rate = Number(g.pay_rate || 0);
    totalSlots += slots;
    totalFilled += Number(g.slots_filled || 0);
    totalHours += hours * slots;
    // Crude $ value per day: hourly = rate*hours*slots, flat = rate*slots
    if (g.pay_type === "hourly") {
      totalPay += rate * Math.max(hours, 0) * slots;
    } else {
      totalPay += rate * slots;
    }
  }
  return { totalPay, totalHours, totalSlots, totalFilled };
};

export default function AdminCalendar() {
  const [view, setView] = useState("month");
  const [cursor, setCursor] = useState(new Date());
  const [gigs, setGigs] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [presetDate, setPresetDate] = useState(null);
  const nav = useNavigate();

  const load = async () => {
    try {
      const { data } = await api.get("/gigs");
      // Keep gigs that have ANY usable date — scheduled_local (wall-clock) or
      // scheduled_at (ISO). getGigDate() reads scheduled_local first.
      setGigs(data.filter((g) => g.scheduled_local || g.scheduled_at));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Index gigs by yyyy-MM-dd (wall-clock)
  const gigsByDate = useMemo(() => {
    const map = new Map();
    for (const g of gigs) {
      try {
        const d = getGigDate(g);
        if (!d) continue;
        const key = format(d, "yyyy-MM-dd");
        if (!map.has(key)) map.set(key, []);
        map.get(key).push({ ...g, _date: d });
      } catch {}
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => a._date - b._date);
    }
    return map;
  }, [gigs]);

  // Compute the date range visible for the current view
  const { days, headerLabel, headerSub } = useMemo(() => {
    if (view === "month") {
      const monthStart = startOfMonth(cursor);
      const monthEnd = endOfMonth(cursor);
      const all = eachDayOfInterval({
        start: startOfWeek(monthStart, { weekStartsOn: 0 }),
        end: endOfWeek(monthEnd, { weekStartsOn: 0 }),
      });
      const inMonthGigs = all
        .filter((d) => isSameMonth(d, cursor))
        .reduce((s, d) => s + (gigsByDate.get(format(d, "yyyy-MM-dd"))?.length || 0), 0);
      return {
        days: all,
        headerLabel: format(cursor, "MMMM yyyy"),
        headerSub: `${inMonthGigs} gig${inMonthGigs === 1 ? "" : "s"} scheduled this month`,
      };
    }
    if (view === "week") {
      const start = startOfWeek(cursor, { weekStartsOn: 0 });
      const end = endOfWeek(cursor, { weekStartsOn: 0 });
      const all = eachDayOfInterval({ start, end });
      const weekGigs = all.reduce(
        (s, d) => s + (gigsByDate.get(format(d, "yyyy-MM-dd"))?.length || 0),
        0
      );
      return {
        days: all,
        headerLabel: `${format(start, "MMM d")} – ${format(end, "MMM d, yyyy")}`,
        headerSub: `${weekGigs} gig${weekGigs === 1 ? "" : "s"} scheduled this week`,
      };
    }
    // day view
    const key = format(cursor, "yyyy-MM-dd");
    const cnt = gigsByDate.get(key)?.length || 0;
    return {
      days: [cursor],
      headerLabel: format(cursor, "EEEE, MMMM d, yyyy"),
      headerSub: `${cnt} gig${cnt === 1 ? "" : "s"} on this day`,
    };
  }, [view, cursor, gigsByDate]);

  // Max workload score across visible days (for heatmap normalization)
  const maxScore = useMemo(() => {
    let m = 0;
    for (const d of days) {
      const k = format(d, "yyyy-MM-dd");
      const s = computeWorkloadScore(gigsByDate.get(k) || []);
      if (s > m) m = s;
    }
    return m;
  }, [days, gigsByDate]);

  const goPrev = () => {
    if (view === "month") setCursor(subMonths(cursor, 1));
    else if (view === "week") setCursor(subWeeks(cursor, 1));
    else setCursor(subDays(cursor, 1));
  };
  const goNext = () => {
    if (view === "month") setCursor(addMonths(cursor, 1));
    else if (view === "week") setCursor(addWeeks(cursor, 1));
    else setCursor(addDays(cursor, 1));
  };

  const openCreateFor = (day) => {
    setPresetDate(day);
    setCreateOpen(true);
  };

  return (
    <div data-testid="admin-calendar">
      <div className="flex flex-col gap-3 border-b border-[#E5E7EB] px-4 py-5 md:flex-row md:flex-wrap md:items-end md:justify-between md:gap-4 md:px-10 md:py-8">
        <div>
          <div className="font-mono-label">Schedule</div>
          <h1 className="mt-1 font-display text-2xl font-black tracking-tight md:text-4xl">
            {headerLabel}
          </h1>
          <p className="mt-1 text-xs text-[#4B5563] md:text-sm">{headerSub}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* View mode toggle */}
          <div
            data-testid="cal-view-toggle"
            className="inline-flex overflow-hidden border border-[#E5E7EB]"
          >
            {VIEW_MODES.map((m) => (
              <button
                key={m}
                data-testid={`cal-view-${m}`}
                onClick={() => setView(m)}
                className={`h-9 px-2.5 font-mono-label text-[10px] tracking-[0.16em] transition-colors md:h-10 md:px-3 md:tracking-[0.18em] ${
                  view === m
                    ? "bg-[#030712] text-white"
                    : "bg-white text-[#4B5563] hover:bg-[#F9FAFB]"
                }`}
              >
                {m.toUpperCase()}
              </button>
            ))}
          </div>
          <Button
            data-testid="cal-prev"
            variant="outline"
            onClick={goPrev}
            className="h-9 w-9 rounded-none p-0 md:h-10 md:w-10"
            aria-label="Previous"
          >
            <CaretLeft size={16} weight="bold" />
          </Button>
          <Button
            data-testid="cal-today"
            variant="outline"
            onClick={() => setCursor(new Date())}
            className="h-9 rounded-none px-3 font-mono-label text-[#030712] md:h-10 md:px-4"
          >
            Today
          </Button>
          <Button
            data-testid="cal-next"
            variant="outline"
            onClick={goNext}
            className="h-9 w-9 rounded-none p-0 md:h-10 md:w-10"
            aria-label="Next"
          >
            <CaretRight size={16} weight="bold" />
          </Button>
          <Button
            data-testid="cal-new-gig"
            onClick={() => {
              setPresetDate(new Date());
              setCreateOpen(true);
            }}
            className="ml-auto h-9 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc] md:ml-2 md:h-10 md:px-4"
          >
            <Plus size={16} className="md:mr-1" /> <span className="hidden sm:inline">New gig</span>
          </Button>
        </div>
      </div>

      {/* Legend + heatmap key (horizontally scrollable on mobile) */}
      <div className="flex flex-nowrap items-center gap-x-5 gap-y-3 overflow-x-auto border-b border-[#E5E7EB] px-4 py-3 md:flex-wrap md:gap-x-6 md:overflow-visible md:px-10">
        <span className="font-mono-label shrink-0">Legend</span>
        {[
          { k: "cleaning", label: "Cleaning" },
          { k: "labor", label: "Labor" },
          { k: "driver", label: "Driver" },
        ].map((c) => {
          const Icon = CAT_ICON[c.k];
          return (
            <span key={c.k} className="inline-flex shrink-0 items-center gap-2 text-xs">
              <span
                className={`grid h-5 w-5 place-items-center ${CAT_COLOR[c.k].bg} ${CAT_COLOR[c.k].text}`}
              >
                <Icon size={11} weight="bold" />
              </span>
              {c.label}
            </span>
          );
        })}
        <span className="font-mono-label ml-2 shrink-0">Workload</span>
        <span className="inline-flex shrink-0 items-center gap-1 text-xs">
          <span className="h-4 w-6" style={{ background: "rgba(0,68,255,0.08)" }} />
          <span className="h-4 w-6" style={{ background: "rgba(0,68,255,0.18)" }} />
          <span className="h-4 w-6" style={{ background: "rgba(0,68,255,0.28)" }} />
          <span className="h-4 w-6" style={{ background: "rgba(239,68,68,0.22)" }} />
          <span className="whitespace-nowrap text-[#4B5563]">light → heavy → overbooked</span>
        </span>
      </div>

      {view === "month" && (
        <MonthGrid
          days={days}
          cursor={cursor}
          gigsByDate={gigsByDate}
          maxScore={maxScore}
          nav={nav}
          openCreateFor={openCreateFor}
        />
      )}
      {view === "week" && (
        <WeekGrid
          days={days}
          gigsByDate={gigsByDate}
          maxScore={maxScore}
          nav={nav}
          openCreateFor={openCreateFor}
        />
      )}
      {view === "day" && (
        <DayView
          day={cursor}
          gigs={gigsByDate.get(format(cursor, "yyyy-MM-dd")) || []}
          nav={nav}
          openCreateFor={openCreateFor}
        />
      )}

      <CreateGigDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={load}
        initialDate={presetDate}
      />
    </div>
  );
}

// --- MONTH VIEW ----------------------------------------------------------
function MonthGrid({ days, cursor, gigsByDate, maxScore, nav, openCreateFor }) {
  // Tapped day for the mobile bottom-sheet
  const [sheetDay, setSheetDay] = useState(null);

  return (
    <div className="border-b border-[#E5E7EB]">
      <div className="grid grid-cols-7 border-b border-[#E5E7EB] bg-[#F9FAFB]">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div
            key={d}
            className="font-mono-label border-r border-[#E5E7EB] px-1 py-1.5 text-center last:border-r-0 md:px-3 md:py-2"
          >
            <span className="md:hidden">{d[0]}</span>
            <span className="hidden md:inline">{d}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day, i) => {
          const key = format(day, "yyyy-MM-dd");
          const dayGigs = gigsByDate.get(key) || [];
          const outside = !isSameMonth(day, cursor);
          const today = isToday(day);
          const score = computeWorkloadScore(dayGigs);
          const tint = !outside && score > 0 ? heatmapTint(score, maxScore) : "";
          const totals = computeDailyTotals(dayGigs);

          return (
            <button
              key={i}
              data-testid={`cal-day-${key}`}
              onClick={() => {
                // On mobile, tap-to-open the day sheet (only if there are gigs).
                // Empty-day tap → still opens create dialog directly.
                if (window.matchMedia("(max-width: 767px)").matches && dayGigs.length > 0) {
                  setSheetDay({ day, gigs: dayGigs, totals });
                } else {
                  openCreateFor(day);
                }
              }}
              className={`relative flex min-h-[64px] flex-col items-stretch gap-1 border-b border-r border-[#E5E7EB] p-1 text-left transition-colors md:min-h-[140px] md:p-2 ${
                outside ? "bg-[#FAFAFB] text-[#9CA3AF]" : "bg-white"
              }`}
              style={tint ? { background: tint } : undefined}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`font-display text-xs font-bold md:text-sm ${
                    today
                      ? "grid h-5 w-5 place-items-center bg-[#0044FF] text-white md:h-6 md:w-6"
                      : ""
                  }`}
                >
                  {format(day, "d")}
                </span>
                {dayGigs.length > 0 && (
                  <span className="font-mono-label hidden text-[9px] md:inline">
                    {dayGigs.length} · {totals.totalSlots} slot
                    {totals.totalSlots === 1 ? "" : "s"}
                  </span>
                )}
              </div>
              {/* MOBILE: dot strip (max 4 dots, +N indicator) */}
              <div className="flex flex-wrap items-center gap-0.5 md:hidden">
                {dayGigs.slice(0, 4).map((g) => {
                  const c = CAT_COLOR[g.category] || CAT_COLOR.labor;
                  return (
                    <span
                      key={g.gig_id}
                      className={`h-1.5 w-1.5 rounded-full ${c.bg}`}
                    />
                  );
                })}
                {dayGigs.length > 4 && (
                  <span className="ml-0.5 text-[8px] font-bold text-[#4B5563]">
                    +{dayGigs.length - 4}
                  </span>
                )}
              </div>
              {/* DESKTOP: full chip stack */}
              <div className="hidden space-y-1 md:block">
                {dayGigs.slice(0, 3).map((g) => (
                  <MonthChip key={g.gig_id} gig={g} nav={nav} />
                ))}
                {dayGigs.length > 3 && (
                  <span className="px-2 text-[10px] font-semibold text-[#4B5563]">
                    +{dayGigs.length - 3} more
                  </span>
                )}
              </div>
              {/* DESKTOP only: daily totals strip */}
              {dayGigs.length > 0 && (
                <div className="mt-auto hidden items-center gap-2 border-t border-black/5 pt-1 text-[9px] text-[#4B5563] md:flex">
                  <CurrencyDollar size={10} weight="bold" />
                  <span className="font-bold text-[#030712]">
                    ${Math.round(totals.totalPay).toLocaleString()}
                  </span>
                  <Clock size={10} weight="bold" className="ml-1" />
                  <span>{totals.totalHours.toFixed(0)}h</span>
                  <Users size={10} weight="bold" className="ml-auto" />
                  <span>
                    {totals.totalFilled}/{totals.totalSlots}
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Mobile day-detail bottom sheet */}
      {sheetDay && (
        <DaySheet
          day={sheetDay.day}
          gigs={sheetDay.gigs}
          totals={sheetDay.totals}
          onClose={() => setSheetDay(null)}
          nav={nav}
          openCreateFor={openCreateFor}
        />
      )}
    </div>
  );
}

// Mobile-only bottom sheet listing a day's gigs in full detail
function DaySheet({ day, gigs, totals, onClose, nav, openCreateFor }) {
  return (
    <div
      data-testid="cal-day-sheet"
      className="fixed inset-0 z-50 flex flex-col md:hidden"
      onClick={onClose}
    >
      <div className="flex-1 bg-black/40 backdrop-blur-sm" />
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[80vh] overflow-y-auto rounded-t-2xl bg-white"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-[#E5E7EB] bg-white px-5 py-4">
          <div>
            <div className="font-mono-label text-[10px]">{format(day, "EEEE")}</div>
            <div className="font-display text-xl font-black">{format(day, "MMM d")}</div>
          </div>
          <button
            data-testid="cal-day-sheet-close"
            onClick={onClose}
            className="text-sm font-semibold text-[#4B5563]"
            aria-label="Close"
          >
            Close
          </button>
        </div>
        <div className="grid grid-cols-3 gap-2 border-b border-[#E5E7EB] bg-[#F9FAFB] px-5 py-3 text-center">
          <Stat label="Gigs" value={gigs.length} />
          <Stat label="Pay" value={`$${Math.round(totals.totalPay).toLocaleString()}`} />
          <Stat label="Slots" value={`${totals.totalFilled}/${totals.totalSlots}`} />
        </div>
        <ul className="divide-y divide-[#E5E7EB]">
          {gigs.map((g) => {
            const c = CAT_COLOR[g.category] || CAT_COLOR.labor;
            const Icon = CAT_ICON[g.category];
            const tags = getOrderedTags(g.tags);
            return (
              <li
                key={g.gig_id}
                data-testid={`cal-day-sheet-gig-${g.gig_id}`}
                onClick={() => {
                  onClose();
                  nav(`/ops/gigs/${g.gig_id}`);
                }}
                className="flex items-start gap-3 px-5 py-3 active:bg-[#F0F4FF]"
              >
                <span
                  className={`grid h-9 w-9 shrink-0 place-items-center ${c.bg} ${c.text}`}
                >
                  <Icon size={16} weight="duotone" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono-label text-[10px]">
                      {format(g._date, "h:mm a")}
                    </span>
                    {tags.slice(0, 3).map((t) => {
                      const I = TAG_CONFIG[t]?.icon;
                      const cfg = TAG_CONFIG[t];
                      return I ? (
                        <span
                          key={t}
                          className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[8px] font-black tracking-widest ${cfg.pillClass}`}
                        >
                          <I size={8} weight="fill" />
                          {cfg.label}
                        </span>
                      ) : null;
                    })}
                  </div>
                  <div className="mt-1 font-display text-sm font-bold leading-tight">
                    {g.title}
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-[#4B5563]">
                    <span className="truncate">{g.location}</span>
                    <span className="font-bold text-[#030712]">
                      {g.slots_filled}/{g.slots} · ${Number(g.pay_rate).toFixed(0)}
                      {g.pay_type === "hourly" ? "/hr" : ""}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        <div className="sticky bottom-0 border-t border-[#E5E7EB] bg-white p-3">
          <Button
            data-testid="cal-day-sheet-add"
            onClick={() => {
              onClose();
              openCreateFor(day);
            }}
            className="h-11 w-full rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            <Plus size={16} className="mr-1" /> Add gig on this day
          </Button>
        </div>
      </div>
    </div>
  );
}

function MonthChip({ gig, nav }) {
  const c = CAT_COLOR[gig.category] || CAT_COLOR.labor;
  const tags = getOrderedTags(gig.tags);
  const flameTag = tags[0]; // strongest tag
  return (
    <span
      data-testid={`cal-chip-${gig.gig_id}`}
      onClick={(e) => {
        e.stopPropagation();
        nav(`/ops/gigs/${gig.gig_id}`);
      }}
      className={`flex cursor-pointer items-center gap-1 truncate px-2 py-1 text-[11px] font-semibold ${c.bg} ${c.text}`}
      title={`${format(gig._date, "h:mm a")} — ${gig.title}`}
    >
      {flameTag && (
        <span
          className="grid h-3 w-3 place-items-center rounded-full"
          style={{
            background: TAG_CONFIG[flameTag]?.pulse ? "#fff" : "rgba(255,255,255,0.85)",
          }}
        >
          {(() => {
            const I = TAG_CONFIG[flameTag]?.icon;
            return I ? <I size={8} weight="fill" color={c.soft} /> : null;
          })()}
        </span>
      )}
      <span className="truncate">
        {format(gig._date, "h:mma")} {gig.title}
      </span>
    </span>
  );
}

// --- WEEK VIEW ----------------------------------------------------------
function WeekGrid({ days, gigsByDate, maxScore, nav, openCreateFor }) {
  return (
    <div className="border-b border-[#E5E7EB]">
      {/* Mobile: stacked agenda (one row per day) */}
      <div className="md:hidden">
        {days.map((day) => {
          const key = format(day, "yyyy-MM-dd");
          const dayGigs = gigsByDate.get(key) || [];
          const score = computeWorkloadScore(dayGigs);
          const tint = score > 0 ? heatmapTint(score, maxScore) : "";
          const today = isToday(day);
          const totals = computeDailyTotals(dayGigs);
          return (
            <div
              key={key}
              data-testid={`cal-week-day-${key}`}
              className="border-b border-[#E5E7EB]"
              style={tint ? { background: tint } : undefined}
            >
              <button
                onClick={() => openCreateFor(day)}
                className="flex w-full items-center justify-between border-b border-[#E5E7EB] bg-white/70 px-4 py-2.5 text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <div className="font-mono-label text-[9px]">{format(day, "EEE")}</div>
                    <div
                      className={`font-display text-xl font-black leading-none ${
                        today ? "text-[#0044FF]" : ""
                      }`}
                    >
                      {format(day, "d")}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-[#030712]">
                      {dayGigs.length === 0
                        ? "No gigs"
                        : `${dayGigs.length} gig${dayGigs.length === 1 ? "" : "s"}`}
                    </div>
                    {dayGigs.length > 0 && (
                      <div className="font-mono-label text-[9px] text-[#4B5563]">
                        {totals.totalFilled}/{totals.totalSlots} slots · $
                        {Math.round(totals.totalPay).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
                <Plus size={14} className="text-[#4B5563]" />
              </button>
              {dayGigs.length > 0 && (
                <div className="space-y-1.5 p-2">
                  {dayGigs.map((g) => (
                    <WeekCard key={g.gig_id} gig={g} nav={nav} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Desktop: 7-column grid */}
      <div className="hidden grid-cols-7 md:grid">
        {days.map((day) => {
          const key = format(day, "yyyy-MM-dd");
          const dayGigs = gigsByDate.get(key) || [];
          const score = computeWorkloadScore(dayGigs);
          const tint = score > 0 ? heatmapTint(score, maxScore) : "";
          const today = isToday(day);
          const totals = computeDailyTotals(dayGigs);
          return (
            <div
              key={key}
              data-testid={`cal-week-day-desktop-${key}`}
              className="flex min-h-[520px] flex-col border-r border-[#E5E7EB] last:border-r-0"
              style={tint ? { background: tint } : undefined}
            >
              <button
                onClick={() => openCreateFor(day)}
                className="flex items-center justify-between border-b border-[#E5E7EB] bg-white/70 px-3 py-2 text-left hover:bg-white"
              >
                <div>
                  <div className="font-mono-label text-[10px]">{format(day, "EEE")}</div>
                  <div
                    className={`font-display text-lg font-black ${
                      today ? "text-[#0044FF]" : ""
                    }`}
                  >
                    {format(day, "d")}
                  </div>
                </div>
                {dayGigs.length > 0 && (
                  <div className="text-right text-[10px] text-[#4B5563]">
                    <div className="font-bold text-[#030712]">
                      ${Math.round(totals.totalPay).toLocaleString()}
                    </div>
                    <div>
                      {totals.totalFilled}/{totals.totalSlots} slots
                    </div>
                  </div>
                )}
              </button>
              <div className="flex-1 space-y-1.5 p-2">
                {dayGigs.length === 0 ? (
                  <div className="font-mono-label py-6 text-center text-[10px] text-[#9CA3AF]">
                    no gigs
                  </div>
                ) : (
                  dayGigs.map((g) => <WeekCard key={g.gig_id} gig={g} nav={nav} />)
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekCard({ gig, nav }) {
  const c = CAT_COLOR[gig.category] || CAT_COLOR.labor;
  const Icon = CAT_ICON[gig.category];
  const tags = getOrderedTags(gig.tags);
  return (
    <button
      data-testid={`cal-week-chip-${gig.gig_id}`}
      onClick={() => nav(`/ops/gigs/${gig.gig_id}`)}
      className="block w-full overflow-hidden bg-white text-left shadow-sm transition-transform hover:-translate-y-0.5"
    >
      <div className={`flex items-center gap-2 px-2 py-1.5 ${c.bg} ${c.text}`}>
        <Icon size={12} weight="duotone" />
        <span className="font-mono-label text-[9px]">{format(gig._date, "h:mma")}</span>
        {tags.length > 0 && (
          <span className="ml-auto inline-flex gap-0.5">
            {tags.slice(0, 2).map((t) => {
              const I = TAG_CONFIG[t]?.icon;
              return I ? (
                <I key={t} size={10} weight="fill" />
              ) : null;
            })}
          </span>
        )}
      </div>
      <div className="space-y-1 p-2 text-[11px]">
        <div className="line-clamp-2 font-display text-xs font-bold leading-tight text-[#030712]">
          {gig.title}
        </div>
        <div className="flex items-center justify-between text-[10px] text-[#4B5563]">
          <span className="truncate">{gig.location}</span>
          <span className="font-bold text-[#030712]">
            {gig.slots_filled}/{gig.slots}
          </span>
        </div>
      </div>
    </button>
  );
}

// --- DAY VIEW ----------------------------------------------------------
function DayView({ day, gigs, nav, openCreateFor }) {
  const hours = useMemo(() => {
    // Build a 24-hour timeline grouped by hour-of-day
    const buckets = new Map();
    for (let h = 6; h < 24; h++) buckets.set(h, []);
    for (const g of gigs) {
      const h = g._date.getHours();
      if (!buckets.has(h)) buckets.set(h, []);
      buckets.get(h).push(g);
    }
    return Array.from(buckets.entries()).sort((a, b) => a[0] - b[0]);
  }, [gigs]);

  const totals = computeDailyTotals(gigs);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4">
      <div className="lg:col-span-3 border-r-0 lg:border-r border-[#E5E7EB]">
        {/* Day summary banner */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3 md:gap-x-6 md:px-10">
          <Stat label="Gigs" value={gigs.length} />
          <Stat
            label="Pay"
            value={`$${Math.round(totals.totalPay).toLocaleString()}`}
          />
          <Stat label="Hours" value={`${totals.totalHours.toFixed(1)}h`} />
          <Stat
            label="Workforce"
            value={`${totals.totalFilled}/${totals.totalSlots}`}
          />
          <Button
            data-testid="day-add-gig"
            onClick={() => openCreateFor(day)}
            className="ml-auto h-9 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc]"
          >
            <Plus size={14} className="md:mr-1" />
            <span className="hidden sm:inline">Add gig on this day</span>
          </Button>
        </div>

        {/* Hour timeline */}
        <div className="divide-y divide-[#E5E7EB]">
          {hours.map(([h, bucketGigs]) => (
            <div
              key={h}
              data-testid={`day-hour-${h}`}
              className={`flex gap-3 px-4 py-3 md:gap-4 md:px-10 ${
                bucketGigs.length === 0 ? "" : "bg-[#FBFCFF]"
              }`}
            >
              <div className="font-mono-label w-12 shrink-0 pt-1 text-[10px] md:w-14">
                {format(new Date(day).setHours(h, 0, 0, 0), "h a")}
              </div>
              <div className="flex-1">
                {bucketGigs.length === 0 ? (
                  <div className="h-6 border-l-2 border-dashed border-[#E5E7EB]" />
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {bucketGigs.map((g) => (
                      <DayCard key={g.gig_id} gig={g} nav={nav} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {gigs.length === 0 && (
            <div className="px-4 py-12 text-center text-sm text-[#4B5563] md:px-10 md:py-16">
              <div>No gigs scheduled for this day yet.</div>
              <Button
                onClick={() => openCreateFor(day)}
                className="mt-4 h-10 rounded-none bg-[#0044FF] px-4 text-white hover:bg-[#0036cc]"
              >
                <Plus size={14} className="mr-1" /> Add the first one
              </Button>
            </div>
          )}
        </div>
      </div>

      <aside className="bg-[#F9FAFB] p-6 lg:p-8">
        <div className="font-mono-label">At a glance</div>
        <h2 className="mt-1 font-display text-2xl font-black">
          {format(day, "EEEE")}
        </h2>
        <div className="mt-1 text-sm text-[#4B5563]">
          {format(day, "MMMM d, yyyy")}
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <BigStat
            label="Total pay"
            value={`$${Math.round(totals.totalPay).toLocaleString()}`}
            icon={CurrencyDollar}
          />
          <BigStat
            label="Total hours"
            value={`${totals.totalHours.toFixed(1)}`}
            icon={Clock}
          />
          <BigStat
            label="Slots filled"
            value={`${totals.totalFilled}/${totals.totalSlots}`}
            icon={Users}
          />
          <BigStat label="Gigs" value={gigs.length} icon={Plus} />
        </div>

        <div className="mt-6">
          <div className="font-mono-label text-[10px]">Roster</div>
          <ul className="mt-2 space-y-2">
            {gigs.length === 0 ? (
              <li className="border border-dashed border-[#E5E7EB] bg-white p-3 text-xs text-[#4B5563]">
                Nothing on the books for this day.
              </li>
            ) : (
              gigs.map((g) => (
                <li
                  key={g.gig_id}
                  onClick={() => nav(`/ops/gigs/${g.gig_id}`)}
                  className="cursor-pointer border border-[#E5E7EB] bg-white p-3 text-[11px] hover:border-[#030712]"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-display text-sm font-bold text-[#030712]">
                      {format(g._date, "h:mma")}
                    </span>
                    <span className="font-mono-label text-[9px] text-[#4B5563]">
                      {g.slots_filled}/{g.slots}
                    </span>
                  </div>
                  <div className="mt-1 truncate text-[12px]">{g.title}</div>
                </li>
              ))
            )}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function DayCard({ gig, nav }) {
  const c = CAT_COLOR[gig.category] || CAT_COLOR.labor;
  const Icon = CAT_ICON[gig.category];
  const tags = getOrderedTags(gig.tags);
  return (
    <button
      data-testid={`day-card-${gig.gig_id}`}
      onClick={() => nav(`/ops/gigs/${gig.gig_id}`)}
      className="overflow-hidden border border-[#E5E7EB] bg-white text-left transition-transform hover:-translate-y-0.5 hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.18)]"
    >
      <div className={`flex items-center gap-2 px-3 py-2 ${c.bg} ${c.text}`}>
        <Icon size={14} weight="duotone" />
        <span className="font-mono-label text-[9px]">{format(gig._date, "h:mma")}</span>
        {tags.length > 0 && (
          <span className="ml-auto inline-flex gap-1">
            {tags.slice(0, 3).map((t) => {
              const I = TAG_CONFIG[t]?.icon;
              return I ? (
                <I key={t} size={11} weight="fill" />
              ) : null;
            })}
          </span>
        )}
      </div>
      <div className="p-3 text-[11px]">
        <div className="line-clamp-2 font-display text-sm font-bold leading-tight">
          {gig.title}
        </div>
        <div className="mt-2 flex items-center justify-between text-[10px] text-[#4B5563]">
          <span className="truncate">{gig.location}</span>
          <span className="font-bold text-[#030712]">
            {gig.slots_filled}/{gig.slots} · ${Number(gig.pay_rate).toFixed(0)}
            {gig.pay_type === "hourly" ? "/hr" : ""}
          </span>
        </div>
      </div>
    </button>
  );
}

function Stat({ label, value }) {
  return (
    <div className="leading-tight">
      <div className="font-mono-label text-[9px]">{label}</div>
      <div className="font-display text-base font-bold">{value}</div>
    </div>
  );
}

function BigStat({ label, value, icon: Icon }) {
  return (
    <div className="border border-[#E5E7EB] bg-white p-3">
      <div className="flex items-center gap-1.5 font-mono-label text-[9px] text-[#4B5563]">
        {Icon && <Icon size={11} weight="bold" />}
        {label}
      </div>
      <div className="mt-1 font-display text-lg font-black text-[#030712]">{value}</div>
    </div>
  );
}
