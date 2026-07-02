import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import EarningsTicker from "@/components/va/EarningsTicker";
import { AnnouncementsBoard } from "@/components/announcements/AnnouncementsBoard";
import {
  Briefcase,
  HourglassMedium,
  CheckCircle,
  Trophy,
  PlusCircle,
  CurrencyDollar,
  Target,
  WarningCircle,
  Lightbulb,
  ChatCircleDots,
} from "@phosphor-icons/react";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

const StatCard = ({ icon: Icon, label, value, accent, testid, sub }) => (
  <div
    data-testid={testid}
    className={`flex flex-col gap-1 border ${accent || "border-[#E5E7EB]"} bg-white p-5`}
  >
    <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
      <Icon size={14} weight="duotone" />
      {label}
    </div>
    <div className="font-display text-3xl font-black">{value}</div>
    {sub && <div className="text-xs text-[#4B5563]">{sub}</div>}
  </div>
);

const ProgressBar = ({ value, target, suffix = "", testid }) => {
  const pct = target && target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  const hit = pct >= 100;
  return (
    <div data-testid={testid}>
      <div className="flex justify-between text-xs font-mono">
        <span className="text-[#4B5563]">
          {value}
          {suffix} <span className="text-[#9CA3AF]">/ {target ?? "—"}{suffix}</span>
        </span>
        <span className={hit ? "text-[#10B981] font-bold" : "text-[#4B5563]"}>{pct}%</span>
      </div>
      <div className="mt-1 h-2 w-full bg-[#F3F4F6]">
        <div
          className={`h-full transition-all ${hit ? "bg-[#10B981]" : "bg-[#0044FF]"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
};

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

  const goal = data?.goal;
  const hasGoal = goal && (goal.target_leads || goal.target_commission);

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

      {/* Company announcements board (auto-hides when empty) */}
      <div className="mb-6 max-w-3xl">
        <AnnouncementsBoard />
      </div>

      {/* Earnings ticker — big money-on-the-screen banner */}
      <EarningsTicker
        mtdAmount={data?.mtd_commission}
        pendingAmount={data?.commissions_pending}
        tier={data?.tier}
      />

      {/* Stale-lead alert */}
      {data?.stale_leads_count > 0 && (
        <Link
          to="/va/leads?filter=stale"
          data-testid="stale-leads-alert"
          className="mb-6 flex items-center justify-between gap-3 border border-[#F59E0B] bg-[#FFFBEB] p-4 hover:bg-[#FEF3C7]"
        >
          <div className="flex items-center gap-3">
            <WarningCircle size={20} className="text-[#D97706]" weight="duotone" />
            <div>
              <div className="font-bold text-[#92400E]">
                {data.stale_leads_count} lead{data.stale_leads_count === 1 ? "" : "s"} need follow-up
              </div>
              <div className="text-xs text-[#92400E]/80">
                These leads haven&apos;t had movement in 7+ days. Time to reach out.
              </div>
            </div>
          </div>
          <div className="font-mono-label text-[#92400E]">View →</div>
        </Link>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          icon={Briefcase}
          label="Active leads"
          value={data?.active_leads ?? 0}
          testid="stat-active-leads"
          sub={`${data?.conversion_rate ?? 0}% conversion rate`}
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
          sub={`${data?.paid_count ?? 0} paid commission${(data?.paid_count ?? 0) === 1 ? "" : "s"}`}
        />
      </div>

      {/* Goal progress + leaderboard rank */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div
          data-testid="goal-card"
          className="border border-[#E5E7EB] bg-white p-6 lg:col-span-2"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-mono-label">
              <Target size={14} weight="duotone" /> Monthly goal
            </div>
            <div className="font-mono-label text-[#9CA3AF]">{goal?.month || "—"}</div>
          </div>
          {hasGoal ? (
            <div className="mt-4 space-y-4">
              {goal.target_leads != null && (
                <div>
                  <div className="font-bold text-xs uppercase tracking-widest mb-1">Leads submitted</div>
                  <ProgressBar
                    value={goal.mtd_leads || 0}
                    target={goal.target_leads}
                    testid="goal-progress-leads"
                  />
                </div>
              )}
              {goal.target_commission != null && (
                <div>
                  <div className="font-bold text-xs uppercase tracking-widest mb-1">Commission paid</div>
                  <ProgressBar
                    value={goal.mtd_commission || 0}
                    target={goal.target_commission}
                    suffix="$"
                    testid="goal-progress-commission"
                  />
                </div>
              )}
              {goal.note && (
                <p className="border-l-2 border-[#0044FF] pl-3 text-xs italic text-[#4B5563]">
                  &ldquo;{goal.note}&rdquo;
                </p>
              )}
            </div>
          ) : (
            <p className="mt-4 text-sm text-[#9CA3AF]">
              No goal set for this month yet. Ask your Program Manager to set one to track your progress.
            </p>
          )}
        </div>

        <Link
          to="/va/leaderboard"
          data-testid="leaderboard-card"
          className="border border-[#E5E7EB] bg-[#030712] p-6 text-white hover:bg-[#1f2937]"
        >
          <div className="flex items-center gap-2 font-mono-label text-white/70">
            <Trophy size={14} weight="duotone" /> Leaderboard rank
          </div>
          <div className="mt-2 font-display text-5xl font-black leading-none">
            #{data?.leaderboard_rank ?? "—"}
          </div>
          <div className="mt-1 text-xs text-white/70">
            of {data?.leaderboard_total ?? 0} active VAs · last 30 days
          </div>
          <div className="mt-4 text-[11px] uppercase tracking-widest text-white/80">
            View full leaderboard →
          </div>
        </Link>
      </div>

      {/* Submit + Templates row */}
      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
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

        <Link
          to="/va/templates"
          data-testid="templates-card"
          className="border border-[#E5E7EB] bg-white p-6 hover:border-[#030712]"
        >
          <div className="flex items-center gap-2 font-mono-label">
            <Lightbulb size={14} weight="duotone" /> Pitch templates
          </div>
          <div className="mt-2 font-display text-xl font-black">Need help reaching out?</div>
          <p className="mt-2 text-xs text-[#4B5563]">
            Copy proven pitches written by your team for DMs, emails, and SMS.
          </p>
          <div className="mt-4 text-[11px] uppercase tracking-widest text-[#0044FF]">
            Browse library →
          </div>
        </Link>
      </div>

      {/* Coaching notes from PM */}
      {data?.shared_notes && data.shared_notes.length > 0 && (
        <div
          data-testid="shared-notes-card"
          className="mb-8 border border-[#0044FF]/30 bg-[#EFF6FF] p-6"
        >
          <div className="flex items-center gap-2 font-mono-label text-[#0044FF]">
            <ChatCircleDots size={14} weight="duotone" /> From your Program Manager
          </div>
          <ul className="mt-3 space-y-2">
            {data.shared_notes.map((n) => (
              <li
                key={n.note_id}
                data-testid={`shared-note-${n.note_id}`}
                className="border-l-2 border-[#0044FF] bg-white p-3 text-sm"
              >
                <p className="whitespace-pre-wrap">{n.text}</p>
                <div className="mt-1 text-[10px] uppercase tracking-widest text-[#9CA3AF]">
                  {n.author_name} · {new Date(n.created_at).toLocaleDateString()}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
