import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ArrowRight, Percent, Monitor, FloppyDisk } from "@phosphor-icons/react";
import MessageUserButton from "@/components/messages/MessageUserButton";
import { serviceTypeLabel } from "@/lib/leadOptions";

const STAGES = [
  { value: "new_lead", label: "New Lead", color: "bg-[#0044FF]" },
  { value: "contacted", label: "Contacted", color: "bg-violet-600" },
  { value: "quoted", label: "Quoted", color: "bg-amber-500" },
  { value: "booked", label: "Booked", color: "bg-emerald-600" },
  { value: "completed", label: "Completed", color: "bg-teal-700" },
  { value: "paid", label: "Paid ✓", color: "bg-emerald-700" },
  { value: "lost", label: "Lost", color: "bg-[#9CA3AF]" },
];

const STAGE_TRANSITIONS = {
  new_lead: ["contacted", "lost"],
  contacted: ["quoted", "lost"],
  quoted: ["booked", "lost"],
  booked: ["completed", "lost"],
  completed: ["paid", "lost"],
  paid: [],
  lost: [],
};

function StageBadge({ stage }) {
  const s = STAGES.find((x) => x.value === stage) || STAGES[0];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${s.color}`}>
      {s.label}
    </span>
  );
}

export default function AdminVADigital() {
  const nav = useNavigate();
  const [items, setItems] = useState(null);
  const [vas, setVas] = useState([]);
  const [pct, setPct] = useState(null);
  const [pctInput, setPctInput] = useState("");
  const [savingPct, setSavingPct] = useState(false);
  const [err, setErr] = useState("");
  const [jobValueMap, setJobValueMap] = useState({});

  const load = async () => {
    try {
      const [leadsRes, settingsRes, vasRes] = await Promise.all([
        api.get("/pm/leads?category=digital"),
        api.get("/pm/digital-settings"),
        api.get("/pm/vas"),
      ]);
      setItems(leadsRes.data.items || []);
      setPct(settingsRes.data.commission_pct);
      setPctInput(String(settingsRes.data.commission_pct));
      setVas((vasRes.data.items || []).filter((v) => v.va_status === "approved"));
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const savePct = async () => {
    const v = parseFloat(pctInput);
    if (!Number.isFinite(v) || v < 0 || v > 100) {
      toast.error("Commission rate must be between 0 and 100");
      return;
    }
    setSavingPct(true);
    try {
      const { data } = await api.put("/pm/digital-settings", { commission_pct: v });
      setPct(data.commission_pct);
      toast.success(`Digital commission rate saved: ${data.commission_pct}%`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingPct(false);
    }
  };

  const moveStage = async (lead, newStage) => {
    try {
      const payload = { stage: newStage };
      if (newStage === "paid") {
        const v = parseFloat(jobValueMap[lead.lead_id]);
        if (Number.isFinite(v) && v > 0) payload.job_value = v;
      }
      await api.put(`/pm/leads/${lead.lead_id}/stage`, payload);
      toast.success(`Moved to ${newStage.replace(/_/g, " ")}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const assignVA = async (lead, vaUserId) => {
    try {
      await api.post(`/pm/leads/${lead.lead_id}/assign-va`, { va_user_id: vaUserId || null });
      toast.success(vaUserId ? "Delivery VA assigned" : "Delivery VA cleared");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const active = items?.filter((l) => !["paid", "lost"].includes(l.stage)) || [];
  const closedValue = (items || [])
    .filter((l) => l.stage === "paid")
    .reduce((sum, l) => sum + Number(l.job_value || 0), 0);
  const pipelineValue = active.reduce(
    (sum, l) => sum + Number(l.job_value ?? l.estimated_budget ?? 0),
    0
  );

  return (
    <div className="p-6 md:p-10" data-testid="admin-va-digital">
      <div className="mb-6">
        <div className="font-mono-label">VA Commission Program</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Digital Services</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Web / app development, sourcing, and marketing leads. Same pipeline — commission is {pct != null ? `${pct}%` : "…"} of project value. Assign a VA to deliver each project.
        </p>
      </div>

      {/* KPIs + rate editor */}
      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <div className="border border-[#E5E7EB] bg-white p-4" data-testid="digital-kpi-total">
          <div className="font-mono-label">Digital leads</div>
          <div className="mt-1 font-display text-3xl font-black">{items?.length ?? "…"}</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4" data-testid="digital-kpi-active">
          <div className="font-mono-label">In pipeline</div>
          <div className="mt-1 font-display text-3xl font-black">{items ? active.length : "…"}</div>
          <div className="text-xs text-[#4B5563]">≈ ${pipelineValue.toFixed(0)} est. value</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4" data-testid="digital-kpi-closed">
          <div className="font-mono-label">Closed (paid) value</div>
          <div className="mt-1 font-display text-3xl font-black text-emerald-700">${closedValue.toFixed(0)}</div>
        </div>
        <div className="border-2 border-[#030712] bg-[#F0F4FF] p-4" data-testid="digital-rate-card">
          <div className="font-mono-label flex items-center gap-1">
            <Percent size={12} weight="bold" /> Commission rate
          </div>
          <div className="mt-2 flex items-center gap-2">
            <Input
              data-testid="digital-rate-input"
              type="number"
              min="0"
              max="100"
              step="0.5"
              value={pctInput}
              onChange={(e) => setPctInput(e.target.value)}
              className="h-9 w-20 rounded-none border-[#030712] bg-white text-sm"
            />
            <span className="text-sm font-bold">%</span>
            <Button
              data-testid="digital-rate-save"
              onClick={savePct}
              disabled={savingPct}
              className="h-9 rounded-none bg-[#030712] px-3 text-xs text-white"
            >
              <FloppyDisk size={12} className="mr-1" /> {savingPct ? "Saving…" : "Save"}
            </Button>
          </div>
          <div className="mt-1 text-[10px] text-[#4B5563]">Applied when a lead is marked paid</div>
        </div>
      </div>

      {err && <div className="mb-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]" data-testid="digital-empty">
          <Monitor size={28} weight="duotone" className="mx-auto mb-2 text-[#9CA3AF]" />
          No digital leads yet. VAs submit them from the <strong>Digital Services</strong> tab in their portal.
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm" data-testid="digital-leads-table">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">VA (sourced)</th>
                <th className="px-3 py-3">Prospect</th>
                <th className="px-3 py-3">Service</th>
                <th className="px-3 py-3">Budget / Value</th>
                <th className="px-3 py-3">Submitted</th>
                <th className="px-3 py-3">Stage</th>
                <th className="px-3 py-3">Delivery VA</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => {
                const nexts = STAGE_TRANSITIONS[l.stage] || [];
                return (
                  <tr
                    key={l.lead_id}
                    data-testid={`digital-row-${l.lead_id}`}
                    className="border-t border-[#E5E7EB] align-top hover:bg-[#F9FAFB]"
                  >
                    <td className="px-3 py-3 text-xs">
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold">{l.va_name || "—"}</div>
                        {l.va_user_id && (
                          <MessageUserButton
                            userId={l.va_user_id}
                            name={l.va_name}
                            variant="icon"
                            testId={`digital-message-va-${l.lead_id}`}
                          />
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        data-testid={`digital-lead-link-${l.lead_id}`}
                        onClick={() => nav(`/ops/va-program/pipeline/${l.lead_id}`)}
                        className="text-left hover:underline"
                      >
                        <div className="font-semibold text-[#0044FF]">{l.prospect_name}</div>
                        <div className="text-xs text-[#4B5563]">{l.prospect_phone}</div>
                      </button>
                    </td>
                    <td className="px-3 py-3 text-xs">{serviceTypeLabel(l.service_type)}</td>
                    <td className="px-3 py-3 text-xs">
                      {l.job_value != null ? (
                        <span className="font-semibold text-emerald-700">${Number(l.job_value).toFixed(0)}</span>
                      ) : l.estimated_budget != null ? (
                        <span>${Number(l.estimated_budget).toFixed(0)} est.</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs text-[#4B5563]">{(l.created_at || "").slice(0, 10)}</td>
                    <td className="px-3 py-3"><StageBadge stage={l.stage} /></td>
                    <td className="px-3 py-3">
                      <select
                        data-testid={`digital-assign-va-${l.lead_id}`}
                        value={l.assigned_va_id || ""}
                        onChange={(e) => assignVA(l, e.target.value)}
                        className="h-8 w-36 border border-[#030712] bg-white px-1 text-xs"
                      >
                        <option value="">— unassigned —</option>
                        {vas.map((v) => (
                          <option key={v.user_id} value={v.user_id}>{v.name || v.email}</option>
                        ))}
                      </select>
                      {l.assigned_at && (
                        <div className="mt-1 text-[10px] text-[#9CA3AF]">
                          Since {new Date(l.assigned_at).toLocaleDateString()}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {nexts.length === 0 ? (
                        <span className="text-xs text-[#9CA3AF]">—</span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {nexts.map((ns) => (
                            <div key={ns} className="flex items-center gap-1">
                              {ns === "paid" && (
                                <input
                                  type="number"
                                  placeholder="$ value"
                                  data-testid={`digital-job-value-${l.lead_id}`}
                                  value={jobValueMap[l.lead_id] || ""}
                                  onChange={(e) =>
                                    setJobValueMap({ ...jobValueMap, [l.lead_id]: e.target.value })
                                  }
                                  className="h-7 w-20 border border-[#E5E7EB] px-2 text-xs"
                                />
                              )}
                              <button
                                data-testid={`digital-move-${l.lead_id}-${ns}`}
                                onClick={() => moveStage(l, ns)}
                                className="inline-flex items-center gap-1 border border-[#030712] bg-white px-2 py-1 text-xs hover:bg-[#030712] hover:text-white"
                              >
                                <ArrowRight size={11} /> {ns.replace(/_/g, " ")}
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
