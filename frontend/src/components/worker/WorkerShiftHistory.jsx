/**
 * Worker shift history — collapsible weekly/monthly view with full detail.
 *
 * Mounted as a new section on /crew/my-assignments (per user choice 1b).
 * Renders ALL completed shifts (clock-out set) — approved, pending, paid,
 * no-show — grouped by week (Mon-Sun) or month. Each group has a subtotal
 * (paid hours + earnings); each shift expandable to reveal full detail:
 *   clock-in / clock-out · hours + break · pay rate · earnings · status
 *   gig + project context · co-workers · admin note · no-show reason
 *
 * History-only (per user choice 4b — upcoming shifts already on the
 * main list above).
 */
import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  CaretDown,
  CaretUp,
  ClockCounterClockwise,
  CurrencyDollar,
  Calendar,
  Briefcase,
  UsersThree,
  Note as NoteIcon,
  CheckCircle,
  Hourglass,
  XCircle,
  CalendarBlank,
} from "@phosphor-icons/react";

const GROUPING_OPTIONS = [
  { id: "week", label: "By week" },
  { id: "month", label: "By month" },
];

const STATUS_STYLES = {
  paid: { bg: "bg-[#065F46]", fg: "text-white", icon: CheckCircle, label: "PAID" },
  approved: { bg: "bg-[#10B981]", fg: "text-white", icon: CheckCircle, label: "APPROVED" },
  pending: { bg: "bg-[#F59E0B]", fg: "text-white", icon: Hourglass, label: "PENDING" },
  no_show: { bg: "bg-[#EF4444]", fg: "text-white", icon: XCircle, label: "NO-SHOW" },
};

function _fmt(iso, opts) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], opts || {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function _date(iso) {
  if (!iso) return null;
  try { return new Date(iso); } catch { return null; }
}

function _startOfWeek(d) {
  // ISO week: Monday → Sunday. Returns midnight of that Monday.
  const dt = new Date(d);
  dt.setHours(0, 0, 0, 0);
  const day = dt.getDay();
  // Sunday(0) → -6, Monday(1) → 0, Tuesday(2) → -1, ...
  const offset = day === 0 ? -6 : 1 - day;
  dt.setDate(dt.getDate() + offset);
  return dt;
}

function _startOfMonth(d) {
  const dt = new Date(d);
  return new Date(dt.getFullYear(), dt.getMonth(), 1);
}

function _groupLabel(grouping, startDate) {
  if (!startDate) return "Unknown";
  if (grouping === "month") {
    return startDate.toLocaleDateString([], { month: "long", year: "numeric" });
  }
  const end = new Date(startDate);
  end.setDate(end.getDate() + 6);
  const sameMonth = startDate.getMonth() === end.getMonth();
  const startFmt = startDate.toLocaleDateString([], {
    month: "short", day: "numeric",
  });
  const endFmt = end.toLocaleDateString([], {
    month: sameMonth ? undefined : "short", day: "numeric", year:
      startDate.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
  });
  return `${startFmt} – ${endFmt}`;
}

function _groupKey(shift, grouping) {
  const d = _date(shift.clock_in_at) || _date(shift.clock_out_at);
  if (!d) return "unknown";
  const start = grouping === "week" ? _startOfWeek(d) : _startOfMonth(d);
  return start.toISOString();
}

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  const Icon = s.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 ${s.bg} ${s.fg} px-2 py-0.5 text-[9px] font-mono uppercase tracking-widest`}
    >
      <Icon size={10} weight="fill" />
      {s.label}
    </span>
  );
}

function ShiftCard({ shift }) {
  const [expanded, setExpanded] = useState(false);

  const start = _date(shift.clock_in_at);
  const end = _date(shift.clock_out_at);
  const startLabel = start
    ? start.toLocaleString([], {
        weekday: "short", month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit",
      })
    : "—";
  const endLabel = end
    ? end.toLocaleString([], { hour: "numeric", minute: "2-digit" })
    : "—";

  const breakLabel = shift.break_minutes
    ? `${(shift.break_minutes / 60).toFixed(2)}h break`
    : null;

  return (
    <div
      className="border border-[#E5E7EB] bg-white"
      data-testid={`shift-card-${shift.acceptance_id}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-3 py-2.5 flex items-center gap-3 hover:bg-[#F9FAFB]"
        data-testid={`shift-toggle-${shift.acceptance_id}`}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={shift.approval_status} />
            <span className="text-sm font-bold text-[#030712] truncate">
              {shift.gig_title || "—"}
            </span>
          </div>
          <div className="mt-0.5 text-[11px] text-[#6B7280] flex items-center gap-2 flex-wrap">
            <span>{startLabel} → {endLabel}</span>
            <span className="text-[#D1D5DB]">·</span>
            <span>{shift.paid_hours.toFixed(2)}h paid</span>
            {breakLabel && <span className="text-[#9CA3AF]">({breakLabel})</span>}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-display text-base font-black text-[#065F46]">
            ${shift.earnings.toFixed(2)}
          </div>
          {expanded ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-[#E5E7EB] p-3 space-y-2 bg-[#F8FAFC] text-xs">
          {/* Project context */}
          {shift.project_title && (
            <div className="flex items-center gap-2">
              <Briefcase size={12} className="text-[#0044FF]" />
              <span className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Project
              </span>
              <span className="font-bold text-[#030712]">{shift.project_title}</span>
            </div>
          )}
          {/* Clock detail */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Clock-in
              </div>
              <div className="font-medium text-[#030712]">{_fmt(shift.clock_in_at)}</div>
            </div>
            <div>
              <div className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Clock-out
              </div>
              <div className="font-medium text-[#030712]">{_fmt(shift.clock_out_at)}</div>
            </div>
          </div>
          {/* Hours + pay detail */}
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#E5E7EB]">
            <div>
              <div className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Worked
              </div>
              <div className="font-bold text-[#030712]">{shift.hours_worked.toFixed(2)}h</div>
            </div>
            <div>
              <div className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Paid
              </div>
              <div className="font-bold text-[#030712]">{shift.paid_hours.toFixed(2)}h</div>
            </div>
            <div>
              <div className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Rate
              </div>
              <div className="font-bold text-[#030712]">
                {shift.pay_rate_applied
                  ? `$${Number(shift.pay_rate_applied).toFixed(2)}${
                      shift.pay_type_applied === "flat" ? " flat" : "/hr"
                    }`
                  : "—"}
              </div>
            </div>
          </div>
          {shift.timesheet_approved_at && (
            <div className="text-[11px] text-[#065F46] flex items-center gap-1">
              <CheckCircle size={12} weight="fill" />
              Approved {_fmt(shift.timesheet_approved_at, { month: "short", day: "numeric" })}
            </div>
          )}
          {/* Co-workers */}
          {shift.co_workers && shift.co_workers.length > 0 && (
            <div className="pt-2 border-t border-[#E5E7EB]">
              <div className="flex items-center gap-1.5">
                <UsersThree size={12} className="text-[#0044FF]" />
                <span className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                  Worked with
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {shift.co_workers.map((c) => (
                  <span
                    key={c.user_id}
                    className="px-2 py-0.5 bg-white border border-[#E5E7EB] text-[#030712]"
                  >
                    {c.first_name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* Admin note */}
          {shift.admin_note && (
            <div className="pt-2 border-t border-[#E5E7EB]">
              <div className="flex items-start gap-1.5">
                <NoteIcon size={12} className="text-[#F59E0B] mt-0.5" />
                <div>
                  <div className="font-mono uppercase tracking-widest text-[10px] text-[#92400E]">
                    Admin note
                  </div>
                  <div className="text-[#030712] whitespace-pre-wrap">
                    {shift.admin_note}
                  </div>
                </div>
              </div>
            </div>
          )}
          {/* No-show reason */}
          {shift.no_show_reason && (
            <div className="pt-2 border-t border-[#E5E7EB] bg-[#FEF2F2] -m-3 mt-2 p-3">
              <div className="flex items-start gap-1.5">
                <XCircle size={12} className="text-[#EF4444] mt-0.5" />
                <div>
                  <div className="font-mono uppercase tracking-widest text-[10px] text-[#991B1B]">
                    No-show reason
                  </div>
                  <div className="text-[#7F1D1D] whitespace-pre-wrap">
                    {shift.no_show_reason}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WorkerShiftHistory() {
  const [shifts, setShifts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [grouping, setGrouping] = useState("week");
  const [open, setOpen] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/me/shifts");
        setShifts(data?.shifts || []);
      } catch {
        setShifts([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Group by week or month — shifts come already sorted desc by clock-in.
  const groups = useMemo(() => {
    const map = new Map();
    for (const s of shifts) {
      const key = _groupKey(s, grouping);
      if (!map.has(key)) {
        const d = _date(s.clock_in_at) || _date(s.clock_out_at);
        const start = grouping === "week" ? _startOfWeek(d) : _startOfMonth(d);
        map.set(key, {
          key,
          start,
          label: _groupLabel(grouping, start),
          shifts: [],
          totalHours: 0,
          totalPaidHours: 0,
          totalEarnings: 0,
        });
      }
      const g = map.get(key);
      g.shifts.push(s);
      g.totalHours += s.hours_worked || 0;
      g.totalPaidHours += s.paid_hours || 0;
      g.totalEarnings += s.earnings || 0;
    }
    return Array.from(map.values()).sort(
      (a, b) => (b.start?.getTime?.() || 0) - (a.start?.getTime?.() || 0)
    );
  }, [shifts, grouping]);

  if (loading) {
    return (
      <div className="mt-8 text-center py-6 text-xs font-mono uppercase tracking-widest text-[#6B7280]">
        Loading shift history…
      </div>
    );
  }

  if (shifts.length === 0) return null;

  return (
    <section className="mt-8" data-testid="worker-shift-history">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between py-2 group"
        data-testid="shift-history-toggle"
      >
        <div className="flex items-center gap-2">
          <ClockCounterClockwise
            size={16}
            weight="duotone"
            className="text-[#0044FF]"
          />
          <h2 className="font-display text-lg font-black tracking-tight text-[#030712]">
            Shift history
          </h2>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
            ({shifts.length} shift{shifts.length === 1 ? "" : "s"})
          </span>
        </div>
        {open ? <CaretUp size={14} /> : <CaretDown size={14} />}
      </button>

      {open && (
        <>
          {/* Grouping toggle */}
          <div
            className="mt-2 inline-flex border border-[#E5E7EB] overflow-hidden"
            data-testid="shift-history-grouping"
          >
            {GROUPING_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setGrouping(opt.id)}
                data-testid={`shift-history-grouping-${opt.id}`}
                className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest transition-colors ${
                  grouping === opt.id
                    ? "bg-[#030712] text-white"
                    : "bg-white text-[#6B7280] hover:bg-[#F3F4F6]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Groups */}
          <div className="mt-3 space-y-4">
            {groups.map((g) => (
              <GroupBlock key={g.key} group={g} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function GroupBlock({ group }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-[#030712] bg-white" data-testid={`shift-history-group-${group.key}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between bg-[#030712] text-white px-3 py-2"
      >
        <div className="flex items-center gap-2">
          <CalendarBlank size={14} weight="duotone" />
          <span className="font-bold text-sm">{group.label}</span>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#9CA3AF]">
            {group.shifts.length} shift{group.shifts.length === 1 ? "" : "s"}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1">
            <Calendar size={12} />
            {group.totalPaidHours.toFixed(2)}h
          </div>
          <div className="flex items-center gap-1 font-bold text-[#10B981]">
            <CurrencyDollar size={12} weight="fill" />
            {group.totalEarnings.toFixed(2)}
          </div>
          {open ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </div>
      </button>
      {open && (
        <div className="divide-y divide-[#E5E7EB]">
          {group.shifts.map((s) => (
            <ShiftCard key={s.acceptance_id} shift={s} />
          ))}
        </div>
      )}
    </div>
  );
}
