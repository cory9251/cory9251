import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { CurrencyDollar } from "@phosphor-icons/react";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

const STATUS_LABELS = {
  calculating: { label: "Calculating", color: "bg-[#9CA3AF] text-white" },
  pending_approval: { label: "Pending approval", color: "bg-amber-500 text-white" },
  pm_approved: { label: "PM approved", color: "bg-[#0044FF] text-white" },
  owner_approved: { label: "Owner approved", color: "bg-violet-600 text-white" },
  paid: { label: "Paid ✓", color: "bg-emerald-700 text-white" },
  flagged: { label: "Flagged", color: "bg-red-600 text-white" },
  rejected: { label: "Rejected", color: "bg-red-700 text-white" },
};

function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || STATUS_LABELS.calculating;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${s.color}`}>
      {s.label}
    </span>
  );
}

export default function VAEarnings() {
  const [resp, setResp] = useState(null);
  const [err, setErr] = useState("");
  const [month, setMonth] = useState(""); // YYYY-MM
  const [status, setStatus] = useState("");
  const [serviceType, setServiceType] = useState("");

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (month) params.set("month", month);
      if (status) params.set("status", status);
      if (serviceType) params.set("service_type", serviceType);
      const { data } = await api.get(`/va/earnings?${params.toString()}`);
      setResp(data);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [month, status, serviceType]);

  return (
    <div className="p-6 md:p-10" data-testid="va-earnings">
      <div className="mb-6">
        <div className="font-mono-label">Earnings</div>
        <h1 className="font-display text-4xl font-black tracking-tight">My earnings</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Every commission is auto-calculated from the rate table and reviewed by Ops + Owner before payout.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="border border-[#E5E7EB] bg-white p-5" data-testid="totals-month">
          <div className="font-mono-label">This month</div>
          <div className="mt-2 font-display text-3xl font-black">
            {fmtMoney(resp?.totals?.this_month)}
          </div>
        </div>
        <div className="border border-emerald-400 bg-white p-5" data-testid="totals-all">
          <div className="font-mono-label">All time</div>
          <div className="mt-2 font-display text-3xl font-black text-emerald-700">
            {fmtMoney(resp?.totals?.all_time)}
          </div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-5 col-span-2 sm:col-span-2">
          <div className="font-mono-label mb-2">Filters</div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="month"
              data-testid="filter-month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="h-9 border border-[#030712] bg-white px-2 text-xs"
            />
            <select
              data-testid="filter-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="h-9 border border-[#030712] bg-white px-2 text-xs"
            >
              <option value="">All statuses</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            <select
              data-testid="filter-service"
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
              className="h-9 border border-[#030712] bg-white px-2 text-xs"
            >
              <option value="">All services</option>
              <option value="routine">Routine</option>
              <option value="deep">Deep</option>
              <option value="moveout">Move-out</option>
              <option value="specialty">Specialty</option>
              <option value="commercial">Commercial</option>
            </select>
            {(month || status || serviceType) && (
              <button
                data-testid="clear-filters"
                onClick={() => {
                  setMonth("");
                  setStatus("");
                  setServiceType("");
                }}
                className="h-9 border border-[#E5E7EB] px-3 text-xs hover:bg-[#F9FAFB]"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="earnings-error">
          {err}
        </div>
      )}

      {!resp ? (
        <div className="font-mono-label">Loading…</div>
      ) : resp.items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 border border-dashed border-[#E5E7EB] bg-white p-12 text-center" data-testid="earnings-empty">
          <CurrencyDollar size={36} weight="duotone" className="text-[#4B5563]" />
          <div className="font-display text-lg font-black">No commissions yet</div>
          <div className="max-w-md text-sm text-[#4B5563]">
            Commissions show up here once Ops marks your lead as Booked, then Paid.
          </div>
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-4 py-3">Lead</th>
                <th className="px-4 py-3">Service</th>
                <th className="px-4 py-3">Calculation</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {resp.items.map((c) => (
                <tr
                  key={c.commission_id}
                  data-testid={`comm-row-${c.commission_id}`}
                  className="border-t border-[#E5E7EB] hover:bg-[#F9FAFB]"
                >
                  <td className="px-4 py-3 font-semibold">{c.prospect_name}</td>
                  <td className="px-4 py-3 capitalize">{c.service_type}</td>
                  <td className="px-4 py-3 text-xs text-[#4B5563]">{c.calc_notes}</td>
                  <td className="px-4 py-3 text-right font-mono font-semibold">{fmtMoney(c.amount)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-[#4B5563]">
                    {(c.created_at || "").slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
