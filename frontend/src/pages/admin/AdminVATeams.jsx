import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  UsersThree,
  Crown,
  Plus,
  X,
  Percent,
  FloppyDisk,
} from "@phosphor-icons/react";

function fmt(n) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AddMember({ assignable, onAdd }) {
  const [val, setVal] = useState("");
  return (
    <div className="flex items-center gap-2">
      <select
        data-testid="add-member-select"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        className="h-9 min-w-[200px] border border-input bg-white px-2 text-sm"
      >
        <option value="">Add a member…</option>
        {assignable.map((v) => (
          <option key={v.user_id} value={v.user_id}>
            {v.name || v.email}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        data-testid="add-member-btn"
        disabled={!val}
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

export default function AdminVATeams() {
  const [data, setData] = useState(null);
  const [allVas, setAllVas] = useState([]);
  const [pct, setPct] = useState("");
  const [l2pct, setL2pct] = useState("");
  const [savingPct, setSavingPct] = useState(false);

  const load = async () => {
    try {
      const [teamsRes, vasRes] = await Promise.all([
        api.get("/pm/teams"),
        api.get("/pm/vas"),
      ]);
      setData(teamsRes.data);
      setPct(String(teamsRes.data.team_override_pct));
      setL2pct(String(teamsRes.data.team_override_l2_pct ?? 5));
      setAllVas((vasRes.data.items || []).filter((v) => v.role === "va"));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load(); // eslint-disable-line
  }, []);

  const savePct = async () => {
    const v = parseFloat(pct);
    const v2 = parseFloat(l2pct);
    if (!Number.isFinite(v) || v < 0 || v > 100) return toast.error("Level-1 rate must be 0–100");
    if (!Number.isFinite(v2) || v2 < 0 || v2 > 100) return toast.error("Level-2 rate must be 0–100");
    setSavingPct(true);
    try {
      await api.put("/pm/commission-settings", { team_override_pct: v, team_override_l2_pct: v2 });
      toast.success("Override rates saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingPct(false);
    }
  };

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

  // Approved VAs that are NOT leads and NOT already on a team → eligible to be leads.
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

  return (
    <div className="mx-auto max-w-4xl" data-testid="admin-va-teams-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <UsersThree size={14} weight="fill" /> VA PROGRAM · TEAMS
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        VA teams &amp; overrides
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Turn a VA into a team lead, then add members — including other leads to
        build a 2-level chain. When a member's lead pays out, their direct lead
        earns the level-1 override and that lead's own lead earns level-2 —
        both split from the closing VA's commission.
      </p>

      {/* Override rates */}
      <div className="mt-6 flex flex-wrap items-end gap-4 border border-[#030712] bg-[#F0F4FF] p-4">
        <div>
          <label className="font-mono-label flex items-center gap-1 text-[#4B5563]">
            <Percent size={12} /> LEVEL 1 (DIRECT LEAD)
          </label>
          <div className="mt-1 flex items-center gap-1">
            <Input
              data-testid="override-pct-input"
              type="number"
              min="0"
              max="100"
              value={pct}
              onChange={(e) => setPct(e.target.value)}
              className="h-9 w-20"
            />
            <span className="text-sm font-bold">%</span>
          </div>
        </div>
        <div>
          <label className="font-mono-label flex items-center gap-1 text-[#4B5563]">
            <Percent size={12} /> LEVEL 2 (LEAD'S LEAD)
          </label>
          <div className="mt-1 flex items-center gap-1">
            <Input
              data-testid="override-l2-pct-input"
              type="number"
              min="0"
              max="100"
              value={l2pct}
              onChange={(e) => setL2pct(e.target.value)}
              className="h-9 w-20"
            />
            <span className="text-sm font-bold">%</span>
          </div>
        </div>
        <Button
          data-testid="save-override-pct"
          onClick={savePct}
          disabled={savingPct}
          className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
        >
          <FloppyDisk size={15} className="mr-1" /> Save rates
        </Button>
        <p className="ml-auto max-w-[16rem] text-xs text-[#4B5563]">
          Both come out of the closer. e.g. L1 10% + L2 5% → a $100 commission =
          $85 closer + $10 direct lead + $5 top lead.
        </p>
      </div>

      {/* Make a team lead */}
      <div className="mt-6">
        <h2 className="font-display text-lg font-black">Create a team lead</h2>
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
        {data.teams.map((t) => (
          <div key={t.user_id} data-testid={`team-card-${t.user_id}`} className="border border-[#E5E7EB] bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] bg-[#FAFAFA] px-4 py-3">
              <div className="flex items-center gap-2">
                <Crown size={16} weight="fill" className="text-amber-500" />
                <span className="font-display text-sm font-black">{t.name}</span>
                {t.reports_to && (
                  <span className="rounded bg-[#EEF2FF] px-1.5 py-0.5 text-[10px] font-bold text-[#4338CA]">
                    ↑ under {t.reports_to.name}
                  </span>
                )}
                <span className="text-xs text-[#6B7280]">
                  · {t.member_count} member{t.member_count === 1 ? "" : "s"} · override earned{" "}
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
            <div className="divide-y divide-[#F3F4F6]">
              {t.members.map((m) => (
                <div key={m.user_id} data-testid={`member-row-${m.user_id}`} className="flex items-center justify-between px-4 py-2.5">
                  <span className="text-sm font-semibold">
                    {m.name || m.email}
                    <span className="ml-2 text-xs font-normal text-[#9CA3AF]">{m.va_status}</span>
                    {m.sub_member_count > 0 && (
                      <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                        sub-lead · {m.sub_member_count}
                      </span>
                    )}
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
                onAdd={(memberId) => assignMember(memberId, t.user_id)}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
