import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  Briefcase,
  HourglassMedium,
  CheckCircle,
  Trophy,
  PlusCircle,
  CurrencyDollar,
} from "@phosphor-icons/react";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

const StatCard = ({ icon: Icon, label, value, accent, testid }) => (
  <div
    data-testid={testid}
    className={`flex flex-col gap-1 border ${accent || "border-[#E5E7EB]"} bg-white p-5`}
  >
    <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
      <Icon size={14} weight="duotone" />
      {label}
    </div>
    <div className="font-display text-3xl font-black">{value}</div>
  </div>
);

export default function VADashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/va/dashboard");
        setData(data);
      } catch (e) {
        setErr(getErr(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="p-8 font-mono-label">Loading…</div>;
  if (err)
    return (
      <div className="m-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700" data-testid="va-dashboard-error">
        {err}
      </div>
    );

  return (
    <div className="p-6 md:p-10" data-testid="va-dashboard">
      <div className="mb-8">
        <div className="font-mono-label">VA Portal</div>
        <h1 className="font-display text-4xl font-black tracking-tight">
          Welcome back, {user?.name?.split(" ")[0]}
        </h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Submit leads, track stages, and watch your commissions land. All earnings are reviewed by your Program Manager before payout.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          icon={Briefcase}
          label="Active leads"
          value={data?.active_leads ?? 0}
          testid="stat-active-leads"
        />
        <StatCard
          icon={HourglassMedium}
          label="Commissions pending"
          value={fmtMoney(data?.commissions_pending)}
          accent="border-amber-300"
          testid="stat-pending"
        />
        <StatCard
          icon={CheckCircle}
          label="Approved (awaiting payout)"
          value={fmtMoney(data?.commissions_approved)}
          accent="border-[#0044FF]"
          testid="stat-approved"
        />
        <StatCard
          icon={CurrencyDollar}
          label="Total paid lifetime"
          value={fmtMoney(data?.total_paid)}
          accent="border-emerald-400"
          testid="stat-paid"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="border border-[#E5E7EB] bg-white p-6 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-mono-label">Quick action</div>
              <div className="font-display text-2xl font-black mt-1">Submit a new lead</div>
              <p className="mt-2 text-sm text-[#4B5563]">
                All leads must go through this form to be eligible for commission.
              </p>
            </div>
            <Link
              to="/va/submit"
              data-testid="quick-submit-lead-btn"
              className="hidden md:flex items-center gap-2 bg-[#030712] px-5 py-3 text-sm font-semibold text-white hover:bg-[#1f2937]"
            >
              <PlusCircle size={18} weight="bold" /> Submit New Lead
            </Link>
          </div>
          <Link
            to="/va/submit"
            className="mt-4 flex md:hidden items-center justify-center gap-2 bg-[#030712] px-5 py-3 text-sm font-semibold text-white hover:bg-[#1f2937]"
          >
            <PlusCircle size={18} weight="bold" /> Submit New Lead
          </Link>
        </div>
        <div
          data-testid="leaderboard-card"
          className="border border-[#E5E7EB] bg-[#030712] p-6 text-white"
        >
          <div className="flex items-center gap-2 font-mono-label text-white/70">
            <Trophy size={14} weight="duotone" /> Leaderboard
          </div>
          <div className="mt-2 font-display text-5xl font-black leading-none">
            #{data?.leaderboard_rank ?? "—"}
          </div>
          <div className="mt-1 text-xs text-white/70">
            of {data?.leaderboard_total ?? 0} active VAs · last 30 days
          </div>
          <div className="mt-4 text-[11px] text-white/60">
            Rank only — earnings stay private.
          </div>
        </div>
      </div>
    </div>
  );
}
