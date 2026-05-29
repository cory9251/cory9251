import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  parseISO,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import {
  CaretLeft,
  CaretRight,
  Plus,
  Broom,
  Wrench,
  Car,
} from "@phosphor-icons/react";

const CAT_COLOR = {
  cleaning: { bg: "bg-[#0044FF]", text: "text-white" },
  labor: { bg: "bg-[#030712]", text: "text-white" },
  driver: { bg: "bg-[#F59E0B]", text: "text-[#030712]" },
};
const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function AdminCalendar() {
  const [cursor, setCursor] = useState(new Date());
  const [gigs, setGigs] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [presetDate, setPresetDate] = useState(null);
  const [hoverDay, setHoverDay] = useState(null);
  const nav = useNavigate();

  const load = async () => {
    try {
      const { data } = await api.get("/gigs");
      // Only consider gigs with a real scheduled_at; ignore legacy free-text gigs
      setGigs(data.filter((g) => g.scheduled_at));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const monthStart = startOfMonth(cursor);
  const monthEnd = endOfMonth(cursor);
  const days = useMemo(
    () =>
      eachDayOfInterval({
        start: startOfWeek(monthStart, { weekStartsOn: 0 }),
        end: endOfWeek(monthEnd, { weekStartsOn: 0 }),
      }),
    [monthStart, monthEnd]
  );

  // Index gigs by yyyy-MM-dd for quick lookup
  const gigsByDate = useMemo(() => {
    const map = new Map();
    for (const g of gigs) {
      try {
        const d = parseISO(g.scheduled_at);
        const key = format(d, "yyyy-MM-dd");
        if (!map.has(key)) map.set(key, []);
        map.get(key).push({ ...g, _date: d });
      } catch {}
    }
    // Sort each day's gigs chronologically
    for (const arr of map.values()) {
      arr.sort((a, b) => a._date - b._date);
    }
    return map;
  }, [gigs]);

  const monthGigCount = days
    .filter((d) => isSameMonth(d, cursor))
    .reduce(
      (sum, d) =>
        sum + (gigsByDate.get(format(d, "yyyy-MM-dd"))?.length || 0),
      0
    );

  const upcoming = useMemo(() => {
    const now = new Date();
    return gigs
      .map((g) => ({ ...g, _date: parseISO(g.scheduled_at) }))
      .filter((g) => g._date >= now)
      .sort((a, b) => a._date - b._date)
      .slice(0, 5);
  }, [gigs]);

  const openCreateFor = (day) => {
    setPresetDate(day);
    setCreateOpen(true);
  };

  return (
    <div data-testid="admin-calendar">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div>
          <div className="font-mono-label">Schedule</div>
          <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
            Calendar
          </h1>
          <p className="mt-1 text-sm text-[#4B5563]">
            {monthGigCount} gig{monthGigCount === 1 ? "" : "s"} scheduled in{" "}
            {format(cursor, "MMMM yyyy")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            data-testid="cal-prev"
            variant="outline"
            onClick={() => setCursor(subMonths(cursor, 1))}
            className="h-10 w-10 rounded-none p-0"
          >
            <CaretLeft size={16} weight="bold" />
          </Button>
          <Button
            data-testid="cal-today"
            variant="outline"
            onClick={() => setCursor(new Date())}
            className="h-10 rounded-none px-4 font-mono-label text-[#030712]"
          >
            Today
          </Button>
          <Button
            data-testid="cal-next"
            variant="outline"
            onClick={() => setCursor(addMonths(cursor, 1))}
            className="h-10 w-10 rounded-none p-0"
          >
            <CaretRight size={16} weight="bold" />
          </Button>
          <Button
            data-testid="cal-new-gig"
            onClick={() => {
              setPresetDate(new Date());
              setCreateOpen(true);
            }}
            className="ml-2 h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            <Plus size={16} className="mr-1" /> New gig
          </Button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        <span className="font-mono-label">Legend</span>
        {[
          { k: "cleaning", label: "Cleaning" },
          { k: "labor", label: "Labor" },
          { k: "driver", label: "Driver" },
        ].map((c) => {
          const Icon = CAT_ICON[c.k];
          return (
            <span key={c.k} className="inline-flex items-center gap-2 text-xs">
              <span className={`grid h-5 w-5 place-items-center ${CAT_COLOR[c.k].bg} ${CAT_COLOR[c.k].text}`}>
                <Icon size={11} weight="bold" />
              </span>
              {c.label}
            </span>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4">
        {/* Month grid */}
        <div className="lg:col-span-3 border-r-0 lg:border-r border-[#E5E7EB]">
          <div className="grid grid-cols-7 border-b border-[#E5E7EB] bg-[#F9FAFB]">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <div
                key={d}
                className="font-mono-label border-r border-[#E5E7EB] px-3 py-2 text-center last:border-r-0"
              >
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {days.map((day, i) => {
              const key = format(day, "yyyy-MM-dd");
              const dayGigs = gigsByDate.get(key) || [];
              const outside = !isSameMonth(day, cursor);
              const today = isToday(day);
              return (
                <button
                  key={i}
                  data-testid={`cal-day-${key}`}
                  onClick={() => openCreateFor(day)}
                  onMouseEnter={() => setHoverDay(key)}
                  onMouseLeave={() => setHoverDay(null)}
                  className={`relative flex min-h-[120px] flex-col items-stretch gap-1 border-b border-r border-[#E5E7EB] p-2 text-left transition-colors ${
                    outside ? "bg-[#FAFAFB] text-[#9CA3AF]" : "bg-white"
                  } ${hoverDay === key ? "bg-[#F0F4FF]" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-display text-sm font-bold ${
                        today
                          ? "grid h-6 w-6 place-items-center bg-[#0044FF] text-white"
                          : ""
                      }`}
                    >
                      {format(day, "d")}
                    </span>
                    {dayGigs.length > 0 && (
                      <span className="font-mono-label text-[9px]">
                        {dayGigs.length} gig{dayGigs.length === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                  <div className="space-y-1">
                    {dayGigs.slice(0, 3).map((g) => {
                      const c = CAT_COLOR[g.category] || CAT_COLOR.labor;
                      return (
                        <span
                          key={g.gig_id}
                          data-testid={`cal-chip-${g.gig_id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            nav(`/admin/gigs/${g.gig_id}`);
                          }}
                          className={`block cursor-pointer truncate px-2 py-1 text-[11px] font-semibold ${c.bg} ${c.text}`}
                          title={`${format(g._date, "h:mm a")} — ${g.title}`}
                        >
                          {format(g._date, "h:mma")} {g.title}
                        </span>
                      );
                    })}
                    {dayGigs.length > 3 && (
                      <span className="px-2 text-[10px] font-semibold text-[#4B5563]">
                        +{dayGigs.length - 3} more
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Upcoming side panel */}
        <aside className="bg-[#F9FAFB] p-6 lg:p-8">
          <div className="font-mono-label">Next up</div>
          <h2 className="mt-1 font-display text-2xl font-black">Upcoming</h2>
          {upcoming.length === 0 ? (
            <div className="mt-6 border border-dashed border-[#E5E7EB] bg-white p-6 text-sm text-[#4B5563]">
              No future gigs scheduled. Click a date to add one.
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {upcoming.map((g) => {
                const c = CAT_COLOR[g.category] || CAT_COLOR.labor;
                const Icon = CAT_ICON[g.category];
                return (
                  <li
                    key={g.gig_id}
                    data-testid={`upcoming-${g.gig_id}`}
                    onClick={() => nav(`/admin/gigs/${g.gig_id}`)}
                    className="cursor-pointer border border-[#E5E7EB] bg-white p-3 hover:border-[#030712]"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`grid h-7 w-7 place-items-center ${c.bg} ${c.text}`}>
                        <Icon size={13} weight="duotone" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-display text-sm font-bold">
                          {g.title}
                        </div>
                        <div className="font-mono-label text-[10px]">
                          {format(g._date, "EEE MMM d · h:mm a")}
                        </div>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px]">
                      <span className="text-[#4B5563]">{g.location}</span>
                      <span className="font-bold">
                        {g.slots_filled}/{g.slots}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
      </div>

      <CreateGigDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={load}
        initialDate={presetDate}
      />
    </div>
  );
}
