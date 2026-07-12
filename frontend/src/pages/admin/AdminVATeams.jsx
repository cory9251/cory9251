import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { UsersThree, Crown, Plus, X, CheckCircle, PauseCircle } from "@phosphor-icons/react";

function fmt(n) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AddMember({ assignable, onAdd, disabled }) {
  const [val, setVal] = useState("");
  return (
    <div className="flex items-center gap-2">
      <select
        data-testid="add-member-select"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        disabled={disabled}
        className="h-9 min-w-[200px] border border-input bg-white px-2 text-sm disabled:opacity-50"
      >
        <option value="">{disabled ? "Team is full (max 5)" : "Add a member…"}</option>
        {assignable.map((v) => (
          <option key={v.user_id} value={v.user_id}>
            {v.name || v.email}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        data-testid="add-member-btn"
        disabled={!val || disabled}
        onClick={() => {
          onAdd(val);
          setVal("");
        }}
        className="bg-[#030712] text-white hover:bg-[#1f2937]"
      >
        <Plus size={14} />
      </Button>
    </div>
  );
}

function QualificationBadge({ team }) {
  const q = team.qualification || {};
  if (q.eligible) {
    return (
      <span
        data-testid={`override-status-${team.user_id}`}
        className="inline-flex items-center gap-1 bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800"
      >
        <CheckCircle size={11} weight="fill" /> OVERRIDE ACTIVE{q.grace ? " (GRACE)" : ""}
      </span>
    );
  }
  const reasonLabel = {
    production_paused: "PAUSED — BELOW 8 JOBS/MO",
    below_senior_tier: "PAUSED — BELOW SENIOR TIER",
    not_approved: "PAUSED — NOT APPROVED",
  }[q.reason] || "PAUSED";
  return (
    <span
      data-testid={`override-status-${team.user_id}`}
      className="inline-flex items-center gap-1 bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-700"
    >
      <PauseCircle size={11} weight="fill" /> {reasonLabel}
    </span>
  );
}

export default function AdminVATeams() {
  const [data, setData] = useState(null);
  const [allVas, setAllVas] = useState([]);

  const load = async () => {
    try {
      const [teamsRes, vasRes] = await Promise.all([
        api.get("/pm/teams"),
        api.get("/pm/vas"),
      ]);
      setData(teamsRes.data);
      setAllVas((vasRes.data.items || []).filter((v) => v.role === "va"));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load(); // eslint-disable-line
  }, []);

  const toggleLead = async (va, on) => {
    try {
      await api.put(`/pm/vas/${va.user_id}/team-lead`, { is_team_lead: on });
      toast.success(on ? `${va.name} is now a team lead` : `${va.name} is no longer a team lead`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const assignMember = async (memberId, teamLeadId) => {
    try {
      await api.put(`/pm/vas/${memberId}/team`, { team_lead_id: teamLeadId });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const eligibleLeads = useMemo(
    () =>
      allVas.filter(
        (v) => !v.is_team_lead && !v.team_lead_id && (v.va_status || "") === "approved"
      ),
    [allVas]
  );

  if (data === null) {
    return <div className="p-8 text-sm text-[#4B5563]">Loading…</div>;
  }

  const split = data.pool_split || { agent: 75, lead: 15, ops: 10 };
  const minJobs = data.min_monthly_jobs || 8;
  const maxSize = data.max_team_size || 5;

  return (
    <div className="mx-auto max-w-4xl" data-testid="admin-va-teams-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <UsersThree size={14} weight="fill" /> VA PROGRAM · TEAMS
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        VA teams &amp; overrides
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Teams are <strong>one level deep</strong>: 3–{maxSize} agents under one Team Lead. On every
        member job, the lead earns <strong>{split.lead}% of the commission pool</strong> — the
        agent always keeps their full {split.agent}% whether they&apos;re on a team or solo.
      </p>

      {/* Qualification rules banner */}
      <div className="mt-6 border border-[#030712] bg-[#F0F4FF] p-4 text-xs text-[#4B5563]" data-testid="lead-rules-banner">
        <div className="font-mono-label mb-1 text-[#030712]">TEAM LEAD QUALIFICATION (AUTO-CHECKED BY THE ENGINE)</div>
        <ul className="list-disc space-y-0.5 pl-4">
          <li>Senior tier or higher ({data.tier_thresholds?.senior ?? 25} closed + paid jobs).</li>
          <li>Personal production of at least {minJobs} closed + paid jobs per month.</li>
          <li>Below minimum for two consecutive months → override pauses (retained by the Company) until production resumes.</li>
        </ul>
      </div>

      {/* Make a team lead */}
      <div className="mt-6">
        <h2 className="font-display text-lg font-black">Create a team lead</h2>
        <p className="mt-1 text-xs text-[#9CA3AF]">
          Promotion requires Senior tier — the server rejects VAs below {data.tier_thresholds?.senior ?? 25} paid jobs.
        </p>
        <div className="mt-2 flex items-center gap-2">
          <select
            data-testid="new-lead-select"
            id="new-lead-select"
            className="h-9 min-w-[240px] border border-input bg-white px-2 text-sm"
            defaultValue=""
            onChange={async (e) => {
              const id = e.target.value;
              if (!id) return;
              const va = eligibleLeads.find((v) => v.user_id === id);
              await toggleLead(va, true);
              e.target.value = "";
            }}
          >
            <option value="">Pick an approved VA to promote…</option>
            {eligibleLeads.map((v) => (
              <option key={v.user_id} value={v.user_id}>
                {v.name || v.email}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Teams */}
      <div className="mt-8 space-y-4">
        {data.teams.length === 0 && (
          <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
            No team leads yet. Promote a VA above to get started.
          </div>
        )}
        {data.teams.map((t) => {
          const prod = t.qualification?.production;
          return (
            <div key={t.user_id} data-testid={`team-card-${t.user_id}`} className="border border-[#E5E7EB] bg-white">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] bg-[#FAFAFA] px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Crown size={16} weight="fill" className="text-amber-500" />
                  <span className="font-display text-sm font-black">{t.name}</span>
                  {t.tier?.tier && (
                    <span className="bg-[#030712] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                      {t.tier.tier} · {t.tier.paid_jobs} jobs
                    </span>
                  )}
                  <QualificationBadge team={t} />
                  <span className="text-xs text-[#6B7280]">
                    · {t.member_count}/{maxSize} member{t.member_count === 1 ? "" : "s"} · override earned{" "}
                    <span className="font-bold text-emerald-700">{fmt(t.override_earnings.total)}</span>
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  data-testid={`demote-${t.user_id}`}
                  className="text-red-600"
                  onClick={() => {
                    if (window.confirm(`Remove ${t.name} as a team lead? Their members will be unassigned.`))
                      toggleLead(t, false);
                  }}
                >
                  Remove lead
                </Button>
              </div>
              {prod && (
                <div className="border-b border-[#F3F4F6] px-4 py-2 text-xs text-[#4B5563]" data-testid={`production-${t.user_id}`}>
                  Personal production (min {minJobs}/mo): this month{" "}
                  <strong className={prod.current_month >= minJobs ? "text-emerald-700" : "text-red-600"}>{prod.current_month}</strong>
                  {" · "}last month{" "}
                  <strong className={prod.last_month >= minJobs ? "text-emerald-700" : "text-red-600"}>{prod.last_month}</strong>
                  {" · "}prior{" "}
                  <strong className={prod.prev_month >= minJobs ? "text-emerald-700" : "text-red-600"}>{prod.prev_month}</strong>
                  {t.qualification?.grace && <span className="ml-2 text-[#9CA3AF]">(new lead — grace window)</span>}
                </div>
              )}
              <div className="divide-y divide-[#F3F4F6]">
                {t.members.map((m) => (
                  <div key={m.user_id} data-testid={`member-row-${m.user_id}`} className="flex items-center justify-between px-4 py-2.5">
                    <span className="text-sm font-semibold">
                      {m.name || m.email}
                      <span className="ml-2 text-xs font-normal text-[#9CA3AF]">{m.va_status}</span>
                    </span>
                    <button
                      type="button"
                      aria-label="Remove member"
                      data-testid={`remove-member-${m.user_id}`}
                      onClick={() => assignMember(m.user_id, null)}
                      className="grid h-7 w-7 place-items-center text-[#9CA3AF] hover:text-red-600"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
                {t.members.length === 0 && (
                  <div className="px-4 py-3 text-xs text-[#9CA3AF]">No members yet.</div>
                )}
              </div>
              <div className="border-t border-[#E5E7EB] px-4 py-3">
                <AddMember
                  assignable={data.assignable_vas}
                  disabled={t.member_count >= maxSize}
                  onAdd={(memberId) => assignMember(memberId, t.user_id)}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
