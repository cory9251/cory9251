import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Crown, CurrencyDollar, CheckCircle, PauseCircle } from "@phosphor-icons/react";

function fmt(n) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function VAMyTeam() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/va/team")
      .then((r) => setData(r.data))
      .catch((e) => setError(getErr(e)));
  }, []);

  if (error) {
    return (
      <div className="p-6 md:p-10" data-testid="va-team-page">
        <div className="border border-red-200 bg-red-50 p-6 text-sm text-red-700" data-testid="va-team-error">
          {error}
        </div>
      </div>
    );
  }

  if (!data) return <div className="p-8 text-sm text-[#4B5563]">Loading…</div>;

  const e = data.override_earnings || { total: 0, by_status: {} };
  const pending =
    (e.by_status?.pending_approval || 0) +
    (e.by_status?.pm_approved || 0) +
    (e.by_status?.owner_approved || 0) +
    (e.by_status?.calculating || 0);
  const paid = e.by_status?.paid || 0;
  const q = data.qualification || {};
  const prod = q.production || {};
  const minJobs = data.min_monthly_jobs || 8;

  return (
    <div className="p-6 md:p-10" data-testid="va-team-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <Crown size={14} weight="fill" className="text-amber-500" /> TEAM LEAD
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        My team
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        You earn <span className="font-bold text-[#030712]">{data.lead_share_pct}% of the commission pool</span> on
        every job your team members close — on top of your own production. Your members always
        keep their full {data.pool_split?.agent ?? 75}%, so being on your team never costs them anything.
      </p>

      {/* Qualification status */}
      <div
        data-testid="lead-qualification-card"
        className={`mt-6 border p-4 ${q.eligible ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          {q.eligible ? (
            <span className="inline-flex items-center gap-1 text-sm font-black text-emerald-800">
              <CheckCircle size={16} weight="fill" /> Override active{q.grace ? " (grace window)" : ""}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-sm font-black text-red-700">
              <PauseCircle size={16} weight="fill" /> Override paused
              {q.reason === "production_paused" && " — production below minimum"}
              {q.reason === "below_senior_tier" && " — Senior tier required"}
            </span>
          )}
          {q.tier?.tier && (
            <span className="bg-[#030712] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
              {q.tier.tier} · {q.tier.paid_jobs} paid jobs
            </span>
          )}
        </div>
        <div className="mt-2 text-xs text-[#4B5563]">
          Keep your personal production at <strong>{minJobs}+ closed &amp; paid jobs per month</strong> to
          stay qualified. This month:{" "}
          <strong className={Number(prod.current_month || 0) >= minJobs ? "text-emerald-700" : "text-red-600"}>
            {prod.current_month ?? 0}/{minJobs}
          </strong>
          {" · "}last month: <strong>{prod.last_month ?? 0}</strong>
          {" · "}prior: <strong>{prod.prev_month ?? 0}</strong>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">TEAM SIZE</div>
          <div className="font-display mt-1 text-2xl font-black">{data.member_count}</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">POOL SHARE</div>
          <div className="font-display mt-1 text-2xl font-black text-[#0044FF]">{data.lead_share_pct}%</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">OVERRIDE PENDING</div>
          <div className="font-display mt-1 text-2xl font-black text-amber-600">{fmt(pending)}</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">OVERRIDE PAID</div>
          <div className="font-display mt-1 text-2xl font-black text-emerald-700">{fmt(paid)}</div>
        </div>
      </div>

      <h2 className="font-display mt-8 text-lg font-black">Members</h2>
      <div className="mt-3 space-y-2">
        {data.members.length === 0 && (
          <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
            No members yet — your Program Manager assigns your team.
          </div>
        )}
        {data.members.map((m) => (
          <div key={m.user_id} data-testid={`team-member-${m.user_id}`} className="flex flex-wrap items-center justify-between gap-2 border border-[#E5E7EB] bg-white px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-[#0044FF] text-xs font-bold text-white">
                {(m.name || "?").slice(0, 1).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-semibold">{m.name || m.email}</div>
                <div className="text-xs text-[#6B7280]">
                  {m.lead_count} lead{m.lead_count === 1 ? "" : "s"} · {m.booked_count} booked
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 text-sm font-black text-emerald-700">
              <CurrencyDollar size={14} weight="bold" />
              {fmt(m.override_earned)} earned
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
