import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Link } from "react-router-dom";
import {
  CurrencyDollar,
  TrendUp,
  Warning,
  Trophy,
  Buildings,
  ChartLineUp,
} from "@phosphor-icons/react";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

const Stat = ({ icon: Icon, label, value, accent, testid }) => (
  <div data-testid={testid} className={`border ${accent || "border-[#E5E7EB]"} bg-white p-5`}>
    <div className="flex items-center gap-2 font-mono-label">
      <Icon size={14} weight="duotone" />
      {label}
    </div>
    <div className="mt-2 font-display text-3xl font-black">{value}</div>
  </div>
);

export default function AdminVAOverview() {
  const { user } = useAuth();
  const [owner, setOwner] = useState(null);
  const [report, setReport] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [w, o] = await Promise.all([
          api.get("/pm/weekly-report"),
          user?.is_owner ? api.get("/owner/dashboard") : Promise.resolve({ data: null }),
        ]);
        setReport(w.data);
        setOwner(o.data);
      } catch (e) {
        setErr(getErr(e));
      }
    })();
  }, [user?.is_owner]);

  return (
    <div className="p-6 md:p-10" data-testid="admin-va-overview">
      <div className="mb-6 flex flex-col gap-1">
        <div className="font-mono-label">{user?.is_owner ? "Owner overview" : "Program Manager overview"}</div>
        <h1 className="font-display text-4xl font-black tracking-tight">VA Commission Program</h1>
        <p className="text-sm text-[#4B5563]">
          Snapshot of this week&apos;s leads, bookings, commissions owed, and active commercial accounts.
        </p>
        <Link
          to="/ops/va-program/analytics"
          data-testid="va-analytics-cta"
          className="mt-3 inline-flex w-fit items-center gap-2 border-2 border-[#030712] bg-white px-4 py-2 text-xs font-bold uppercase tracking-widest text-[#030712] transition-colors hover:bg-[#030712] hover:text-white"
        >
          <ChartLineUp size={14} weight="bold" />
          Open detailed analytics →
        </Link>
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {/* Owner-only top KPIs */}
      {user?.is_owner && owner && (
        <div className="mb-6">
          <div className="mb-2 font-mono-label text-[10px]">Payout actions</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Link to="/ops/payouts" data-testid="owner-payout-kpi">
              <Stat
                icon={CurrencyDollar}
                label="Awaiting your sign-off"
                value={`${owner.payout_queue_count} · ${fmtMoney(owner.payout_queue_amount)}`}
                accent="border-violet-600"
              />
            </Link>
            <Stat
              icon={TrendUp}
              label="Commissions this month"
              value={fmtMoney(owner.month_total_commissions)}
            />
            <Stat
              icon={Buildings}
              label="Commercial revenue / mo"
              value={fmtMoney(owner.commercial_monthly_revenue_total)}
            />
            <Stat
              icon={Warning}
              label="Open alerts"
              value={owner.alerts?.length || 0}
              accent={owner.alerts?.length ? "border-amber-500" : "border-[#E5E7EB]"}
            />
          </div>
        </div>
      )}

      {/* Weekly report */}
      {report && (
        <div className="border border-[#E5E7EB] bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="font-mono-label">Weekly report</div>
              <h2 className="font-display text-2xl font-black">
                Week of {report.week_start} → {report.week_end}
              </h2>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="border border-[#E5E7EB] p-4">
              <div className="font-mono-label">Total leads</div>
              <div className="mt-1 font-display text-2xl font-black">{report.total_leads}</div>
            </div>
            <div className="border border-[#E5E7EB] p-4">
              <div className="font-mono-label">Total bookings</div>
              <div className="mt-1 font-display text-2xl font-black">{report.total_bookings}</div>
            </div>
            <div className="border border-[#E5E7EB] p-4">
              <div className="font-mono-label">Revenue from paid jobs</div>
              <div className="mt-1 font-display text-2xl font-black">{fmtMoney(report.total_revenue)}</div>
            </div>
            <div className="border border-emerald-400 p-4">
              <div className="font-mono-label">Commissions owed</div>
              <div className="mt-1 font-display text-2xl font-black text-emerald-700">{fmtMoney(report.commission_owed)}</div>
            </div>
          </div>

          {/* Top VAs */}
          <div className="mt-6">
            <div className="mb-2 flex items-center gap-2 font-mono-label">
              <Trophy size={14} weight="duotone" /> Top VAs (this week)
            </div>
            {report.top_vas.length === 0 ? (
              <div className="text-xs text-[#4B5563]">No activity yet this week.</div>
            ) : (
              <ol className="space-y-1">
                {report.top_vas.map((va, i) => (
                  <li
                    key={va.va_user_id}
                    data-testid={`top-va-${i}`}
                    className="flex items-center justify-between border-b border-[#E5E7EB] py-2 text-sm last:border-0"
                  >
                    <span>
                      <span className="font-mono text-xs text-[#4B5563]">#{i + 1}</span>{" "}
                      <span className="font-semibold">{va.va_name}</span>
                    </span>
                    <span className="font-mono">{va.leads} leads</span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          {/* Flags */}
          <div className="mt-6">
            <div className="mb-2 flex items-center gap-2 font-mono-label">
              <Warning size={14} weight="duotone" /> Flags this week
            </div>
            {report.flags.length === 0 ? (
              <div className="text-xs text-emerald-700">No violations this week. 🎉</div>
            ) : (
              <ul className="space-y-1 text-sm">
                {report.flags.map((f) => (
                  <li
                    key={f.violation_id}
                    data-testid={`flag-${f.violation_id}`}
                    className="border-b border-[#E5E7EB] py-2 last:border-0"
                  >
                    <div className="font-semibold text-amber-900">{f.kind?.replace(/_/g, " ")}</div>
                    <div className="text-xs text-[#4B5563]">{(f.created_at || "").slice(0, 16).replace("T", " ")}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Owner extra: top performers (30d) */}
      {user?.is_owner && owner && (owner.top_by_volume?.length || owner.top_by_conversion?.length) && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="border border-[#E5E7EB] bg-white p-6">
            <div className="font-mono-label flex items-center gap-2">
              <Trophy size={14} weight="duotone" /> Top by volume (30 days)
            </div>
            <ol className="mt-2">
              {owner.top_by_volume.map((va, i) => (
                <li key={va.va_user_id} className="flex items-center justify-between border-b border-[#E5E7EB] py-2 text-sm last:border-0">
                  <span>
                    <span className="font-mono text-xs text-[#4B5563]">#{i + 1}</span>{" "}
                    <span className="font-semibold">{va.va_name}</span>
                  </span>
                  <span className="font-mono">{va.leads}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="border border-[#E5E7EB] bg-white p-6">
            <div className="font-mono-label flex items-center gap-2">
              <Trophy size={14} weight="duotone" /> Top by conversion (30 days)
            </div>
            <ol className="mt-2">
              {owner.top_by_conversion.map((va, i) => (
                <li key={va.va_user_id} className="flex items-center justify-between border-b border-[#E5E7EB] py-2 text-sm last:border-0">
                  <span>
                    <span className="font-mono text-xs text-[#4B5563]">#{i + 1}</span>{" "}
                    <span className="font-semibold">{va.va_name}</span>
                  </span>
                  <span className="font-mono">{va.conversion}%</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}
