import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import {
  Briefcase,
  UsersThree,
  CheckCircle,
  IdentificationCard,
  ClockCounterClockwise,
  Plus,
  Megaphone,
  Lightning,
  CurrencyDollar,
} from "@phosphor-icons/react";
import { formatGigShort } from "@/lib/gigDate";

const KPI = ({ label, value, icon: Icon, accent }) => (
  <div className="flex items-start justify-between border-r border-b border-[#E5E7EB] p-6 last:border-r-0">
    <div>
      <div className="font-mono-label">{label}</div>
      <div className="mt-3 font-display text-5xl font-black tracking-tighter">
        {value}
      </div>
    </div>
    <div
      className={`grid h-9 w-9 place-items-center ${
        accent ? "bg-[#0044FF] text-white" : "bg-[#030712] text-white"
      }`}
    >
      <Icon size={18} weight="duotone" />
    </div>
  </div>
);

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [recentGigs, setRecentGigs] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const nav = useNavigate();

  const load = async () => {
    try {
      const [s, g] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/gigs"),
      ]);
      setStats(s.data);
      setRecentGigs(g.data.slice(0, 6));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="" data-testid="admin-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div>
          <div className="font-mono-label">Operations</div>
          <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
            Dashboard
          </h1>
        </div>
        <Button
          data-testid="dashboard-create-gig"
          onClick={() => setCreateOpen(true)}
          className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
        >
          <Plus size={16} className="mr-2" /> New gig
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 border-l border-t border-[#E5E7EB]">
        <KPI label="Open gigs" value={stats?.open_gigs ?? "—"} icon={Briefcase} accent />
        <KPI label="Filled" value={stats?.filled_gigs ?? "—"} icon={CheckCircle} />
        <KPI label="Workers" value={stats?.total_workers ?? "—"} icon={UsersThree} />
        <KPI
          label="Pending requests"
          value={stats?.pending_requests ?? "—"}
          icon={ClockCounterClockwise}
        />
        <KPI
          label="Pending ID"
          value={stats?.pending_id_verification ?? "—"}
          icon={IdentificationCard}
        />
      </div>

      {stats?.available_now > 0 && (
        <div
          data-testid="dashboard-available-strip"
          className="border-b border-[#E5E7EB] bg-[#ECFDF5] px-6 py-3 md:px-10"
        >
          <button
            data-testid="dashboard-available-link"
            onClick={() => nav("/ops/workers?status=approved")}
            className="flex w-full items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-[#065F46]">
              <Lightning size={18} weight="fill" className="animate-pulse" />
              <span className="font-display text-sm font-bold">
                {stats.available_now} worker
                {stats.available_now === 1 ? " is" : "s are"} available right now — perfect for RUSH gigs
              </span>
            </div>
            <span className="font-mono-label text-[#065F46]">Browse roster →</span>
          </button>
        </div>
      )}

      {stats?.pending_requests > 0 && (
        <div className="border-b border-[#E5E7EB] bg-[#FFFBEB] px-6 py-3 md:px-10">
          <button
            data-testid="dashboard-pending-apps-link"
            onClick={() => nav("/ops/requests")}
            className="flex w-full items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-[#92400E]">
              <ClockCounterClockwise size={18} weight="fill" />
              <span className="font-display text-sm font-bold">
                {stats.pending_requests} gig request
                {stats.pending_requests === 1 ? "" : "s"} waiting for your approval
              </span>
            </div>
            <span className="font-mono-label">Review now →</span>
          </button>
        </div>
      )}

      {stats?.missing_payout > 0 && (
        <div
          data-testid="dashboard-missing-payout-strip"
          className="border-b border-[#E5E7EB] bg-[#FFFBEB] px-6 py-3 md:px-10"
        >
          <button
            data-testid="dashboard-missing-payout-link"
            onClick={() => nav("/ops/workers?payout_status=missing")}
            className="flex w-full items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-[#92400E]">
              <CurrencyDollar size={18} weight="fill" />
              <span className="font-display text-sm font-bold">
                {stats.missing_payout} worker
                {stats.missing_payout === 1 ? "" : "s"} missing a payout method — you can't pay them yet
              </span>
            </div>
            <span className="font-mono-label">See list →</span>
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 border-t border-[#E5E7EB]">
        <div className="lg:col-span-2 border-r border-[#E5E7EB]">
          <div className="flex items-center justify-between border-b border-[#E5E7EB] px-6 py-4">
            <div>
              <div className="font-mono-label">Recent gigs</div>
              <div className="font-display text-xl font-bold">Latest posts</div>
            </div>
            <button
              data-testid="view-all-gigs"
              onClick={() => nav("/ops/gigs")}
              className="text-xs font-semibold text-[#0044FF] hover:underline"
            >
              View all →
            </button>
          </div>

          {recentGigs.length === 0 ? (
            <div className="p-8 text-sm text-[#4B5563]">
              No gigs yet. Create your first opportunity to get started.
            </div>
          ) : (
            <div className="divide-y divide-[#E5E7EB]">
              {recentGigs.map((g) => (
                <button
                  key={g.gig_id}
                  data-testid={`recent-gig-${g.gig_id}`}
                  onClick={() => nav(`/ops/gigs/${g.gig_id}`)}
                  className="flex w-full items-center justify-between px-6 py-4 text-left hover:bg-[#F9FAFB]"
                >
                  <div>
                    <div className="font-display text-base font-bold">{g.title}</div>
                    <div className="mt-1 text-xs text-[#4B5563]">
                      {g.category.toUpperCase()} · {g.location} · {formatGigShort(g)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono-label">
                      {g.slots_filled}/{g.slots} filled
                    </span>
                    <span
                      className={`px-2 py-1 text-[10px] font-bold tracking-widest ${
                        g.status === "open"
                          ? "bg-[#0044FF] text-white"
                          : "bg-[#030712] text-white"
                      }`}
                    >
                      {g.status.toUpperCase()}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-[#F9FAFB] p-6">
          <div className="font-mono-label">Quick blast</div>
          <div className="mt-2 font-display text-2xl font-bold leading-tight">
            Notify your crew in one tap.
          </div>
          <p className="mt-3 text-sm text-[#4B5563]">
            From any gig, hit{" "}
            <span className="inline-flex items-center gap-1 font-semibold text-[#030712]">
              <Megaphone size={14} weight="fill" /> Blast
            </span>
            . Choose channels — in-app, email, SMS — and send to your entire roster.
          </p>
          <Button
            onClick={() => nav("/ops/gigs")}
            className="mt-6 h-10 w-full rounded-none border border-[#030712] bg-white text-[#030712] hover:bg-[#030712] hover:text-white"
          >
            Open gig list
          </Button>
        </div>
      </div>

      <CreateGigDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={load} />
    </div>
  );
}
