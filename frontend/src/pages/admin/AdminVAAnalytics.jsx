import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Link } from "react-router-dom";
import {
  TrendUp,
  Funnel,
  Drop,
  CaretLeft,
  CurrencyDollar,
  Warning,
} from "@phosphor-icons/react";
import { format, parseISO } from "date-fns";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(0)}`;
}

function fmtMonth(periodStr) {
  // "2026-06" → "Jun '26"
  try {
    return format(parseISO(periodStr + "-01"), "MMM ''yy");
  } catch {
    return periodStr;
  }
}

function conversionTone(pct) {
  // Green when good, amber middling, red bad.
  if (pct >= 25) return { fg: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-500" };
  if (pct >= 10) return { fg: "text-amber-800", bg: "bg-amber-50", border: "border-amber-500" };
  return { fg: "text-rose-700", bg: "bg-rose-50", border: "border-rose-400" };
}

function leakTone(days) {
  if (days >= 21) return { fg: "text-rose-700", bg: "bg-rose-50", border: "border-rose-500" };
  if (days >= 14) return { fg: "text-amber-800", bg: "bg-amber-50", border: "border-amber-500" };
  return { fg: "text-[#030712]", bg: "bg-[#F3F4F6]", border: "border-[#E5E7EB]" };
}

const STAGE_LABEL = {
  new_lead: "New",
  contacted: "Contacted",
  quoted: "Quoted",
  booked: "Booked",
};

export default function AdminVAAnalytics() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [leakDays, setLeakDays] = useState(7);
  const [months, setMonths] = useState(6);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/pm/analytics", { params: { months, leak_days: leakDays } });
      setData(r.data);
      setErr("");
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [months, leakDays]);

  // Velocity chart math: scale all bars to the max month total.
  const velMax = useMemo(() => {
    const v = data?.velocity || [];
    return Math.max(1, ...v.map((m) => m.total || 0));
  }, [data]);

  const funnelTotals = useMemo(() => {
    const f = data?.funnel || [];
    return f.reduce(
      (acc, r) => {
        acc.leads += r.leads;
        acc.contacted += r.contacted;
        acc.quoted += r.quoted;
        acc.booked += r.booked;
        acc.paid += r.paid;
        return acc;
      },
      { leads: 0, contacted: 0, quoted: 0, booked: 0, paid: 0 }
    );
  }, [data]);

  return (
    <div className="p-6 md:p-10" data-testid="va-analytics-page">
      <div className="mb-6 flex flex-col gap-1">
        <Link
          to="/ops/va-program"
          className="inline-flex items-center gap-1 font-mono-label text-[10px] text-[#4B5563] hover:text-[#0044FF]"
        >
          <CaretLeft size={11} /> Back to VA overview
        </Link>
        <div className="font-mono-label">Analytics</div>
        <h1 className="font-display text-4xl font-black tracking-tight">
          VA Commission analytics
        </h1>
        <p className="text-sm text-[#4B5563]">
          Spot underperforming VAs and stuck leads <em>before</em> they churn off the program.
        </p>
      </div>

      {/* Window controls */}
      <div className="mb-6 flex flex-wrap items-center gap-2 text-xs">
        <label className="font-mono-label">Velocity window:</label>
        {[3, 6, 12].map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`vel-window-${n}`}
            onClick={() => setMonths(n)}
            className={`border px-2 py-1 font-mono ${
              months === n
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
            }`}
          >
            {n}mo
          </button>
        ))}
        <span className="mx-2 text-[#E5E7EB]">|</span>
        <label className="font-mono-label">Leak threshold:</label>
        {[7, 14, 21].map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`leak-${n}`}
            onClick={() => setLeakDays(n)}
            className={`border px-2 py-1 font-mono ${
              leakDays === n
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
            }`}
          >
            ≥{n}d
          </button>
        ))}
        {loading && <span className="ml-2 font-mono-label text-[10px] text-[#4B5563]">Loading…</span>}
      </div>

      {err && (
        <div
          className="mb-4 border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700"
          data-testid="va-analytics-error"
        >
          {err}
        </div>
      )}

      {/* 1) Velocity chart */}
      <section className="mb-8" data-testid="va-velocity-section">
        <div className="mb-3 flex items-center gap-2 font-mono-label">
          <TrendUp size={14} weight="duotone" /> Commission velocity — last {months} months
        </div>
        <div className="border border-[#E5E7EB] bg-white p-6">
          {data?.velocity?.length ? (
            <div className="flex h-56 items-end gap-2 sm:gap-4">
              {data.velocity.map((m) => {
                const pct = (t) => `${Math.max(0, (Number(t) || 0) / velMax) * 100}%`;
                const paidH = pct(m.paid);
                const apprH = pct(m.owner_approved + m.pm_approved);
                const pendH = pct(m.pending);
                return (
                  <div
                    key={m.period}
                    data-testid={`vel-bar-${m.period}`}
                    className="flex flex-1 flex-col items-center"
                    title={`Total ${fmtMoney(m.total)} · ${m.count} commission${m.count === 1 ? "" : "s"}`}
                  >
                    <div className="mb-1 font-mono text-[10px] text-[#030712]">{fmtMoney(m.total)}</div>
                    <div className="relative flex w-full max-w-12 flex-col items-stretch overflow-hidden border border-[#E5E7EB] bg-white" style={{ height: 200 }}>
                      <div className="flex w-full flex-1 flex-col-reverse">
                        {m.paid > 0 && (
                          <div className="bg-emerald-500" style={{ height: paidH }} title={`Paid: ${fmtMoney(m.paid)}`} />
                        )}
                        {(m.owner_approved + m.pm_approved) > 0 && (
                          <div className="bg-violet-400" style={{ height: apprH }} title={`Approved: ${fmtMoney(m.owner_approved + m.pm_approved)}`} />
                        )}
                        {m.pending > 0 && (
                          <div className="bg-amber-300" style={{ height: pendH }} title={`Pending: ${fmtMoney(m.pending)}`} />
                        )}
                      </div>
                    </div>
                    <div className="mt-2 font-mono-label text-[10px]">{fmtMonth(m.period)}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="font-mono-label text-[#4B5563]">No commission data yet.</div>
          )}
          {/* Legend */}
          <div className="mt-5 flex flex-wrap gap-4 text-[11px]">
            <Legend swatch="bg-emerald-500" label="Paid" />
            <Legend swatch="bg-violet-400" label="Approved (pending payout)" />
            <Legend swatch="bg-amber-300" label="Pending PM review" />
          </div>
        </div>
      </section>

      {/* 2) Funnel — per VA */}
      <section className="mb-8" data-testid="va-funnel-section">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono-label">
            <Funnel size={14} weight="duotone" /> Per-VA conversion funnel
          </div>
          <div className="font-mono-label text-[10px] text-[#4B5563]">
            {data?.funnel?.length || 0} VAs · {funnelTotals.leads} total leads
          </div>
        </div>
        <div className="overflow-x-auto border border-[#E5E7EB] bg-white">
          <table className="min-w-full text-sm">
            <thead className="border-b border-[#E5E7EB] bg-[#F9FAFB] text-left font-mono-label">
              <tr>
                <th className="px-4 py-2">VA</th>
                <th className="px-2 py-2 text-right">Leads</th>
                <th className="px-2 py-2 text-right">Contacted</th>
                <th className="px-2 py-2 text-right">Quoted</th>
                <th className="px-2 py-2 text-right">Booked</th>
                <th className="px-2 py-2 text-right">Paid</th>
                <th className="px-4 py-2 text-right">Conversion</th>
              </tr>
            </thead>
            <tbody>
              {(data?.funnel || []).slice(0, 25).map((r) => {
                const tone = conversionTone(r.conversion);
                return (
                  <tr
                    key={r.va_user_id}
                    data-testid={`funnel-row-${r.va_user_id}`}
                    className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB]"
                  >
                    <td className="px-4 py-2 font-semibold text-[#030712]">{r.va_name || "—"}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.leads}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.contacted}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.quoted}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.booked}</td>
                    <td className="px-2 py-2 text-right font-mono">{r.paid}</td>
                    <td className={`px-4 py-2 text-right ${tone.fg} font-bold`}>{r.conversion}%</td>
                  </tr>
                );
              })}
              {(!data?.funnel || data.funnel.length === 0) && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center font-mono-label text-[#4B5563]">
                    No VA activity yet.
                  </td>
                </tr>
              )}
            </tbody>
            {data?.funnel?.length > 0 && (
              <tfoot className="border-t border-[#E5E7EB] bg-[#F9FAFB] font-mono text-xs">
                <tr>
                  <td className="px-4 py-2 font-bold uppercase tracking-widest">Totals</td>
                  <td className="px-2 py-2 text-right">{funnelTotals.leads}</td>
                  <td className="px-2 py-2 text-right">{funnelTotals.contacted}</td>
                  <td className="px-2 py-2 text-right">{funnelTotals.quoted}</td>
                  <td className="px-2 py-2 text-right">{funnelTotals.booked}</td>
                  <td className="px-2 py-2 text-right">{funnelTotals.paid}</td>
                  <td className="px-4 py-2 text-right">
                    {funnelTotals.leads
                      ? `${((funnelTotals.paid / funnelTotals.leads) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <div className="mt-2 font-mono-label text-[10px] text-[#4B5563]">
          Showing top 25 VAs by lead volume · conversion = paid / leads.
        </div>
      </section>

      {/* 3) Leaks */}
      <section data-testid="va-leaks-section">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono-label">
            <Drop size={14} weight="duotone" /> Leaks — leads stuck ≥ {leakDays} days
          </div>
          <div className="font-mono-label text-[10px] text-[#4B5563]">
            {data?.leaks?.length || 0} stuck
          </div>
        </div>
        {(data?.leaks || []).length === 0 ? (
          <div className="border border-emerald-300 bg-emerald-50 p-6 text-sm text-emerald-800">
            <Warning size={14} weight="duotone" className="mr-1 inline" />
            No leaks. Every lead has moved within the last {leakDays} days. 🎯
          </div>
        ) : (
          <div className="border border-[#E5E7EB] bg-white">
            {data.leaks.map((l) => {
              const tone = leakTone(l.days_stuck);
              return (
                <Link
                  key={l.lead_id}
                  to={`/ops/va-program/pipeline?lead=${l.lead_id}`}
                  data-testid={`leak-${l.lead_id}`}
                  className={`flex items-center justify-between gap-3 border-l-4 ${tone.border} ${tone.bg} px-4 py-3 transition-colors hover:brightness-95`}
                >
                  <div className="min-w-0">
                    <div className={`font-semibold ${tone.fg}`}>
                      {l.prospect_name || "Unnamed lead"}
                    </div>
                    <div className="mt-0.5 font-mono-label text-[10px] text-[#4B5563]">
                      {l.va_name || "Unknown VA"} ·{" "}
                      <span className="uppercase">{STAGE_LABEL[l.stage] || l.stage}</span>
                      {l.service_type ? ` · ${l.service_type}` : ""}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-mono font-bold ${tone.fg}`}>
                      {l.days_stuck}d
                    </div>
                    <div className="font-mono-label text-[9px] text-[#4B5563]">
                      since change
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
        <div className="mt-2 font-mono-label text-[10px] text-[#4B5563]">
          Tap a row → opens that lead in the pipeline so you can nudge the VA.
        </div>
      </section>

      {/* Cash-flow summary strip (small) */}
      {data && (
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="va-cashflow-strip">
          <Mini
            icon={CurrencyDollar}
            label="Paid this window"
            value={fmtMoney(data.velocity.reduce((a, m) => a + m.paid, 0))}
          />
          <Mini
            icon={CurrencyDollar}
            label="Approved · pending payout"
            value={fmtMoney(data.velocity.reduce((a, m) => a + m.owner_approved + m.pm_approved, 0))}
          />
          <Mini
            icon={CurrencyDollar}
            label="Pending PM review"
            value={fmtMoney(data.velocity.reduce((a, m) => a + m.pending, 0))}
          />
          <Mini
            icon={Drop}
            label="Leads stuck"
            value={data.leaks?.length || 0}
          />
        </div>
      )}
    </div>
  );
}

const Legend = ({ swatch, label }) => (
  <div className="flex items-center gap-2 text-[#4B5563]">
    <span className={`inline-block h-3 w-3 ${swatch}`} />
    <span>{label}</span>
  </div>
);

const Mini = ({ icon: Icon, label, value }) => (
  <div className="border border-[#E5E7EB] bg-white p-3">
    <div className="flex items-center gap-1.5 font-mono-label text-[10px]">
      <Icon size={11} weight="duotone" /> {label}
    </div>
    <div className="mt-1 font-display text-lg font-black">{value}</div>
  </div>
);
