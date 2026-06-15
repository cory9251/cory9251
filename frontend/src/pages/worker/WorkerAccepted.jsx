import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, CurrencyDollar, MapPin, Clock, Hourglass } from "@phosphor-icons/react";
import { formatGigWhen, isGigToday, isGigTomorrow } from "@/lib/gigDate";

export default function WorkerAccepted() {
  const [items, setItems] = useState([]);
  const [earnings, setEarnings] = useState(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [g, e] = await Promise.all([
          api.get("/gigs", { params: { status: "all" } }),
          api.get("/me/earnings"),
        ]);
        // we want only ones the worker accepted; backend already attaches my_acceptance
        setItems(g.data.filter((g) => g.my_acceptance));
        setEarnings(e.data);
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, []);

  return (
    <div className="px-5 py-6" data-testid="worker-accepted">
      <div className="font-mono-label">My commitments</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        My gigs
      </h1>

      {earnings && (
        <div
          data-testid="worker-earnings-summary"
          className="mt-5 grid grid-cols-2 gap-3"
        >
          <div className="rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4">
            <div className="font-mono-label flex items-center gap-1 text-[#065F46]">
              <CurrencyDollar size={11} weight="duotone" /> Approved earnings
            </div>
            <div className="mt-1 font-display text-2xl font-black text-[#065F46]">
              ${earnings.approved.total_earnings.toFixed(2)}
            </div>
            <div className="mt-0.5 text-[10px] font-mono-label text-[#065F46]/80">
              {(earnings.approved.total_paid_hours ?? earnings.approved.total_hours).toFixed(2)}h paid
              {earnings.approved.total_break_minutes
                ? ` · ${(earnings.approved.total_break_minutes / 60).toFixed(2)}h break`
                : ""}
            </div>
          </div>
          <div className="rounded-2xl border border-[#F59E0B]/30 bg-[#FFFBEB] p-4">
            <div className="font-mono-label flex items-center gap-1 text-[#92400E]">
              <Hourglass size={11} weight="duotone" /> Pending approval
            </div>
            <div className="mt-1 font-display text-2xl font-black text-[#92400E]">
              {earnings.pending.count}
            </div>
            <div className="mt-0.5 text-[10px] font-mono-label text-[#92400E]/80">
              {earnings.pending.hours.toFixed(2)}h waiting
            </div>
          </div>
        </div>
      )}

      <div className="mt-5 space-y-4">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            You haven't accepted any gigs yet.
          </div>
        ) : (
          items.map((g) => {
            const acc = g.my_acceptance || {};
            const isRequested = acc.status === "requested";
            const onClock = acc.clock_in_at && !acc.clock_out_at;
            const completed = !!acc.clock_out_at;
            const approved = !!acc.timesheet_approved;
            return (
            <button
              key={g.gig_id}
              data-testid={`accepted-gig-${g.gig_id}`}
              onClick={() => nav(`/crew/gigs/${g.gig_id}`)}
              className="gb-tactile w-full rounded-2xl border border-black/5 bg-white p-5 text-left"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-mono-label">
                    {g.category} · {g.subcategory || "general"}
                  </div>
                  <div className="mt-1 font-display text-lg font-bold">{g.title}</div>
                </div>
                {isRequested ? (
                  <span
                    data-testid={`requested-badge-${g.gig_id}`}
                    className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white"
                  >
                    <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                    REQUESTED
                  </span>
                ) : onClock ? (
                  <span
                    data-testid={`on-clock-badge-${g.gig_id}`}
                    className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white"
                  >
                    <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                    ON THE CLOCK
                  </span>
                ) : completed ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                    <CheckCircle size={10} weight="fill" />{" "}
                    {acc.hours_worked != null ? `${acc.hours_worked.toFixed(2)}H` : "DONE"}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#0044FF] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                    <CheckCircle size={10} weight="fill" /> APPROVED
                  </span>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-3 border-t border-[#E5E7EB] pt-3 text-xs">
                <Tag icon={CurrencyDollar} v={`$${Number(g.pay_rate).toFixed(0)}${g.pay_type === "hourly" ? "/hr" : ""}`} />
                <Tag icon={MapPin} v={g.location} />
                <Tag icon={Clock} v={formatGigWhen(g)} highlight={isGigToday(g) || isGigTomorrow(g)} />
              </div>
              {completed && (
                <div
                  data-testid={`earnings-${g.gig_id}`}
                  className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
                    approved
                      ? "border-[#10B981]/30 bg-[#ECFDF5]"
                      : "border-[#F59E0B]/30 bg-[#FFFBEB]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`font-mono-label ${approved ? "text-[#065F46]" : "text-[#92400E]"}`}>
                      {approved ? "Earnings (approved)" : "Earnings pending HCOB approval"}
                    </span>
                    <span className={`font-display text-base font-black ${approved ? "text-[#065F46]" : "text-[#92400E]"}`}>
                      {approved && acc.earnings != null
                        ? `$${acc.earnings.toFixed(2)}`
                        : "—"}
                    </span>
                  </div>
                  {(acc.break_minutes_applied != null || acc.break_minutes_effective) ? (
                    <div
                      data-testid={`break-line-${g.gig_id}`}
                      className={`mt-1 text-[10px] ${
                        approved ? "text-[#065F46]/80" : "text-[#92400E]/80"
                      }`}
                    >
                      {`${Number(acc.hours_worked || 0).toFixed(2)}h worked – `}
                      {`${((Number(acc.break_minutes_applied ?? acc.break_minutes_effective ?? 0)) / 60).toFixed(2)}h break = `}
                      {`${Number(acc.paid_hours ?? Math.max(0, (acc.hours_worked || 0) - (acc.break_minutes_applied ?? acc.break_minutes_effective ?? 0) / 60)).toFixed(2)}h paid`}
                    </div>
                  ) : (
                    <div className={`mt-1 text-[10px] ${approved ? "text-[#065F46]/80" : "text-[#92400E]/80"}`}>
                      {`${Number(acc.hours_worked || 0).toFixed(2)}h paid`}
                    </div>
                  )}
                </div>
              )}
            </button>
            );
          })
        )}
      </div>
    </div>
  );
}
const Tag = ({ icon: I, v, highlight }) => (
  <span
    className={`inline-flex items-center gap-1 ${
      highlight ? "font-bold text-[#0044FF]" : "text-[#030712]"
    }`}
  >
    <I size={12} weight={highlight ? "fill" : "duotone"} /> {v}
  </span>
);

