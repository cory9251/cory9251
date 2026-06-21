import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import CustomerChatPanel from "@/components/worker/CustomerChatPanel";
import {
  ArrowLeft,
  ArrowRight,
  FolderSimple,
  CheckCircle,
  CurrencyDollar,
  CalendarBlank,
  MapPin,
  UsersThree,
  Lock,
  Broom,
  Wrench,
  Car,
  Lightning,
} from "@phosphor-icons/react";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function WorkerProjectPage() {
  const { projectId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}/worker-view`);
      setData(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  if (loading) {
    return (
      <div className="px-5 py-10 text-center text-sm text-[#4B5563]">
        Loading project…
      </div>
    );
  }
  if (!data) {
    return (
      <div className="px-5 py-10 text-center text-sm text-[#4B5563]">
        <p>This project isn&apos;t available right now.</p>
        <button
          onClick={() => nav("/crew")}
          className="mt-3 text-[#0044FF] underline"
        >
          ← Back to feed
        </button>
      </div>
    );
  }

  const linked = data.linked_gigs || [];
  const open = linked.filter((g) => g.status === "open" && g.slots_open > 0);
  const approvedHere = (data.my_gigs || []).length;
  const total = linked.length;

  return (
    <div className="px-4 pb-24 pt-4 md:px-8" data-testid="worker-project-page">
      {/* Sticky back-to-feed */}
      <Link
        to="/crew"
        className="inline-flex items-center gap-1 text-xs font-semibold text-[#4B5563] hover:text-[#030712]"
        data-testid="back-to-feed"
      >
        <ArrowLeft size={12} /> Back to feed
      </Link>

      {/* Header */}
      <div className="mt-4">
        <div className="font-mono-label flex items-center gap-2">
          <FolderSimple size={12} weight="duotone" /> Project
        </div>
        <h1
          className="mt-1 font-display text-3xl md:text-4xl font-black tracking-tight leading-[1.05]"
          data-testid="worker-project-title"
        >
          {data.title}
        </h1>

        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-[#4B5563]">
          <span className="inline-flex items-center gap-1">
            <Lightning size={12} weight="fill" className="text-[#0044FF]" />
            {total} gig{total === 1 ? "" : "s"} in this project
          </span>
          {data.scheduled_window && (
            <span className="inline-flex items-center gap-1">
              <CalendarBlank size={12} weight="duotone" />
              {fmtRange(data.scheduled_window)}
            </span>
          )}
          {open.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[#22C55E]">
              <span className="inline-block h-2 w-2 rounded-full bg-[#22C55E]" />
              {open.length} role{open.length === 1 ? "" : "s"} open
            </span>
          )}
        </div>

        {/* What this means for the worker */}
        {approvedHere > 0 ? (
          <div
            data-testid="worker-project-status-approved"
            className="mt-5 border border-[#22C55E] bg-[#ECFDF5] p-4 gb-tactile"
          >
            <div className="flex items-start gap-2">
              <CheckCircle
                size={18}
                weight="fill"
                className="mt-0.5 shrink-0 text-[#22C55E]"
              />
              <div>
                <div className="font-display text-base font-black tracking-tight">
                  You&apos;re approved on {approvedHere} gig
                  {approvedHere === 1 ? "" : "s"} in this project
                </div>
                <div className="mt-1 text-xs text-[#4B5563]">
                  Below you can see every linked gig and the rest of the crew
                  working alongside you.
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div
            data-testid="worker-project-status-shopping"
            className="mt-5 border border-[#030712]/10 bg-[#F9FAFB] p-4"
          >
            <div className="flex items-start gap-2">
              <Lock size={18} className="mt-0.5 shrink-0 text-[#4B5563]" />
              <div>
                <div className="font-display text-base font-black tracking-tight">
                  Get approved on any gig to see the crew
                </div>
                <div className="mt-1 text-xs text-[#4B5563]">
                  You can request any open role below — once HCOB approves you,
                  you&apos;ll also see who else is on this project.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Customer chat (project-scoped) — if worker is a participant */}
      <CustomerChatPanel projectId={projectId} />

      {/* Gigs */}
      <div className="mt-7">
        <div className="font-mono-label mb-3 flex items-center gap-2">
          <span>All gigs in this project</span>
        </div>
        <ul className="space-y-3">
          {linked.map((g) => (
            <ProjectGigCard key={g.gig_id} g={g} crewVisible={data.crew_visible} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProjectGigCard({ g, crewVisible }) {
  const nav = useNavigate();
  const I = CAT_ICON[g.category] || Broom;
  const pay =
    g.pay_type === "hourly"
      ? `$${(g.pay_rate || 0).toFixed(0)}/hr`
      : `$${(g.pay_rate || 0).toFixed(0)} flat`;
  const mineStatus = g.my_acceptance_status;
  const mineApproved = mineStatus && mineStatus !== "requested";
  const slotsOpen = g.slots_open;
  const closed = g.status !== "open";
  const crew = g.approved_crew || [];

  return (
    <li
      data-testid={`worker-project-gig-${g.gig_id}`}
      onClick={() => nav(`/crew/assignments/${g.gig_id}`)}
      className={`group cursor-pointer border bg-white p-4 transition-colors hover:bg-[#F9FAFB] ${
        mineApproved
          ? "border-[#22C55E]"
          : g.is_rush
          ? "border-[#EF4444]"
          : "border-[#030712]/10"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center bg-[#030712] text-white">
          <I size={18} weight="duotone" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-base font-black leading-tight truncate">
              {g.title}
            </h3>
            {mineApproved && (
              <span
                data-testid={`pill-mine-approved-${g.gig_id}`}
                className="inline-flex items-center gap-1 bg-[#22C55E] px-2 py-0.5 text-[10px] font-black tracking-widest text-white"
              >
                <CheckCircle size={10} weight="fill" /> YOU&apos;RE ON THIS
              </span>
            )}
            {mineStatus === "requested" && (
              <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[10px] font-black tracking-widest text-white">
                REQUESTED
              </span>
            )}
            {g.is_rush && !mineApproved && (
              <span className="inline-flex items-center gap-1 bg-[#EF4444] px-2 py-0.5 text-[10px] font-black tracking-widest text-white">
                RUSH
              </span>
            )}
            {closed && (
              <span className="inline-flex items-center gap-1 bg-[#F3F4F6] px-2 py-0.5 text-[10px] font-black tracking-widest text-[#4B5563]">
                CLOSED
              </span>
            )}
          </div>
          <div className="mt-1 text-[11px] text-[#4B5563]">
            {(g.category || "").toUpperCase()}
            {g.subcategory ? ` · ${g.subcategory.replace(/_/g, " ")}` : ""}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span className="inline-flex items-center gap-1">
              <CalendarBlank size={11} weight="duotone" />
              {g.scheduled_date || "Flexible"}
            </span>
            <span className="inline-flex items-center gap-1">
              <CurrencyDollar size={11} weight="duotone" />
              {pay}
            </span>
            <span className="inline-flex items-center gap-1">
              <MapPin size={11} weight="duotone" />
              {g.location || "Baltimore, MD"}
            </span>
            <span className="inline-flex items-center gap-1">
              <UsersThree size={11} weight="duotone" />
              {g.slots_filled}/{g.slots} filled
              {slotsOpen > 0 && !closed && (
                <span className="text-[#22C55E]"> · {slotsOpen} open</span>
              )}
            </span>
          </div>
        </div>
        <ArrowRight
          size={14}
          className="text-[#9CA3AF] group-hover:text-[#030712]"
        />
      </div>

      {/* Crew chips — only visible once worker is approved on any project gig */}
      {crewVisible && crew.length > 0 && (
        <div className="mt-3 border-t border-[#F3F4F6] pt-3">
          <div className="font-mono-label mb-2 text-[10px] text-[#4B5563]">
            Approved crew on this gig
          </div>
          <div className="flex flex-wrap gap-2">
            {crew.map((c, i) => (
              <span
                key={`${g.gig_id}-${i}`}
                data-testid={`crew-chip-${g.gig_id}-${i}`}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
                  c.is_me
                    ? "border-[#22C55E] bg-[#ECFDF5] text-[#15803D] font-bold"
                    : "border-[#E5E7EB] bg-white text-[#030712]"
                }`}
              >
                <span
                  className={`grid h-5 w-5 place-items-center rounded-full text-[9px] font-black ${
                    c.is_me ? "bg-[#22C55E] text-white" : "bg-[#030712] text-white"
                  }`}
                >
                  {(c.first_name || "?")[0].toUpperCase()}
                </span>
                <span className="font-semibold">
                  {c.first_name}
                  {c.is_me && " (you)"}
                </span>
                {c.gig_role && c.gig_role !== "worker" && (
                  <span className="rounded bg-[#F59E0B] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">
                    {c.gig_role}
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
      {crewVisible && crew.length === 0 && (
        <div className="mt-3 border-t border-[#F3F4F6] pt-3 text-[11px] text-[#4B5563]">
          No one approved on this gig yet — be the first.
        </div>
      )}
    </li>
  );
}

function fmtRange(window) {
  try {
    const fmt = (iso) =>
      new Date(iso).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    const a = fmt(window.start);
    const b = fmt(window.end);
    return a === b ? a : `${a} → ${b}`;
  } catch {
    return "";
  }
}
