import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Monitor, PaperPlaneTilt, WarningCircle, Percent, Briefcase, Plus, X } from "@phosphor-icons/react";
import { DIGITAL_SERVICE_TYPES, LEAD_SOURCES, serviceTypeLabel, isDigitalService } from "@/lib/leadOptions";

const STAGE_STYLES = {
  new_lead: "bg-[#0044FF]",
  contacted: "bg-violet-600",
  quoted: "bg-amber-500",
  booked: "bg-emerald-600",
  completed: "bg-teal-700",
  paid: "bg-emerald-700",
  lost: "bg-[#9CA3AF]",
};

function StageBadge({ stage }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${STAGE_STYLES[stage] || "bg-[#9CA3AF]"}`}>
      {(stage || "—").replace(/_/g, " ")}
    </span>
  );
}

const EMPTY_FORM = {
  prospect_name: "",
  prospect_phone: "",
  prospect_email: "",
  prospect_address: "",
  service_type: "web_development",
  estimated_budget: "",
  preferred_datetime: "",
  source: "linkedin",
  notes: "",
};

export default function VADigitalServices() {
  const nav = useNavigate();
  const [pct, setPct] = useState(null);
  const [leads, setLeads] = useState(null);
  const [projects, setProjects] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [dupeWarn, setDupeWarn] = useState(null);
  const [err, setErr] = useState(null);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const load = async () => {
    try {
      const [settings, allLeads, myProjects] = await Promise.all([
        api.get("/va/digital-settings"),
        api.get("/va/leads"),
        api.get("/va/projects"),
      ]);
      setPct(settings.data.commission_pct);
      setLeads((allLeads.data.items || []).filter((l) => isDigitalService(l.service_type)));
      setProjects(myProjects.data.items || []);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    setDupeWarn(null);
    setLoading(true);
    try {
      const payload = { ...form };
      ["prospect_email", "prospect_address", "preferred_datetime", "notes"].forEach((k) => {
        if (!payload[k]) delete payload[k];
      });
      if (payload.estimated_budget) {
        payload.estimated_budget = parseFloat(payload.estimated_budget);
      } else {
        delete payload.estimated_budget;
      }
      await api.post("/va/leads", payload);
      toast.success("Digital lead submitted — ownership locked to you.");
      setForm(EMPTY_FORM);
      setShowForm(false);
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      if (e?.response?.status === 409 && detail?.code === "duplicate_lead") {
        setDupeWarn(detail);
      } else {
        setErr(getErr(e));
      }
    } finally {
      setLoading(false);
    }
  };

  const estCommission = (l) => {
    const value = l.job_value ?? l.estimated_budget;
    if (value == null || pct == null) return null;
    return (Number(value) * pct) / 100;
  };

  return (
    <div className="p-6 md:p-10 max-w-5xl" data-testid="va-digital-services">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono-label">Digital services</div>
          <h1 className="font-display text-4xl font-black tracking-tight">Digital Services</h1>
          <p className="mt-2 text-sm text-[#4B5563]">
            Web &amp; app development, sourcing, marketing — submit prospects and deliver assigned projects.
          </p>
        </div>
        <Button
          data-testid="digital-new-lead-btn"
          onClick={() => setShowForm((v) => !v)}
          className="h-11 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
        >
          {showForm ? <X size={16} className="mr-2" /> : <Plus size={16} className="mr-2" />}
          {showForm ? "Close form" : "New digital lead"}
        </Button>
      </div>

      {/* Commission rate banner */}
      <div
        data-testid="digital-commission-banner"
        className="mb-6 flex items-center gap-3 border-2 border-[#030712] bg-[#F0F4FF] p-4"
      >
        <div className="grid h-10 w-10 shrink-0 place-items-center bg-[#0044FF] text-white">
          <Percent size={20} weight="bold" />
        </div>
        <div>
          <div className="font-bold text-[#030712]">
            You earn {pct != null ? `${pct}%` : "…"} of the project value on every closed digital deal.
          </div>
          <div className="text-xs text-[#4B5563]">
            Commission is calculated when your Program Manager marks the project as paid.
          </div>
        </div>
      </div>

      {err && (
        <div data-testid="digital-error" className="mb-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {err}
        </div>
      )}

      {/* Submit form */}
      {showForm && (
        <form onSubmit={submit} className="mb-8 space-y-5 border border-[#E5E7EB] bg-white p-6" data-testid="digital-lead-form">
          <div className="font-mono-label flex items-center gap-2">
            <Monitor size={14} /> New digital lead
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="d_name" className="font-mono-label">Prospect / company name *</Label>
              <Input
                data-testid="digital-prospect-name"
                id="d_name"
                required
                minLength={2}
                value={form.prospect_name}
                onChange={(e) => upd("prospect_name", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label htmlFor="d_phone" className="font-mono-label">Phone number *</Label>
              <Input
                data-testid="digital-prospect-phone"
                id="d_phone"
                required
                type="tel"
                value={form.prospect_phone}
                onChange={(e) => upd("prospect_phone", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label htmlFor="d_email" className="font-mono-label">Email <span className="text-[#9CA3AF]">(optional)</span></Label>
              <Input
                data-testid="digital-prospect-email"
                id="d_email"
                type="email"
                value={form.prospect_email}
                onChange={(e) => upd("prospect_email", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label htmlFor="d_address" className="font-mono-label">Address / website <span className="text-[#9CA3AF]">(optional)</span></Label>
              <Input
                data-testid="digital-prospect-address"
                id="d_address"
                value={form.prospect_address}
                onChange={(e) => upd("prospect_address", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label htmlFor="d_service" className="font-mono-label">Digital service *</Label>
              <select
                data-testid="digital-service-type"
                id="d_service"
                required
                value={form.service_type}
                onChange={(e) => upd("service_type", e.target.value)}
                className="mt-2 h-11 w-full border border-[#030712] bg-white px-3 text-sm"
              >
                {DIGITAL_SERVICE_TYPES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="d_budget" className="font-mono-label">Estimated budget ($) <span className="text-[#9CA3AF]">(optional)</span></Label>
              <Input
                data-testid="digital-estimated-budget"
                id="d_budget"
                type="number"
                min="0"
                step="0.01"
                value={form.estimated_budget}
                onChange={(e) => upd("estimated_budget", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
              {form.estimated_budget && pct != null && (
                <div className="mt-1 text-[11px] text-emerald-700">
                  ≈ ${((parseFloat(form.estimated_budget) || 0) * pct / 100).toFixed(2)} potential commission at {pct}%
                </div>
              )}
            </div>
            <div>
              <Label htmlFor="d_datetime" className="font-mono-label">Preferred start / timeline <span className="text-[#9CA3AF]">(optional)</span></Label>
              <Input
                data-testid="digital-preferred-datetime"
                id="d_datetime"
                type="datetime-local"
                value={form.preferred_datetime}
                onChange={(e) => upd("preferred_datetime", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label htmlFor="d_source" className="font-mono-label">How did you reach this lead? *</Label>
              <select
                data-testid="digital-source"
                id="d_source"
                required
                value={form.source}
                onChange={(e) => upd("source", e.target.value)}
                className="mt-2 h-11 w-full border border-[#030712] bg-white px-3 text-sm"
              >
                {LEAD_SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label htmlFor="d_notes" className="font-mono-label">Project brief <span className="text-[#9CA3AF]">(optional)</span></Label>
            <Textarea
              data-testid="digital-notes"
              id="d_notes"
              rows={4}
              value={form.notes}
              onChange={(e) => upd("notes", e.target.value)}
              className="mt-2 rounded-none border-[#030712]"
              placeholder="Scope, deliverables, tech stack, timeline expectations…"
            />
          </div>

          {dupeWarn && (
            <div
              data-testid="digital-duplicate-warning"
              className="flex items-start gap-3 border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
            >
              <WarningCircle size={20} weight="duotone" className="mt-0.5 shrink-0" />
              <div>
                <div className="font-semibold">Duplicate lead blocked</div>
                <div className="mt-1">{dupeWarn.message}</div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowForm(false)}
              className="h-11 rounded-none border-[#030712]"
            >
              Cancel
            </Button>
            <Button
              data-testid="digital-submit-btn"
              type="submit"
              disabled={loading}
              className="h-11 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
            >
              <PaperPlaneTilt size={16} weight="bold" className="mr-2" />
              {loading ? "Submitting…" : "Submit digital lead"}
            </Button>
          </div>
        </form>
      )}

      {/* Delivery projects assigned to me */}
      <section className="mb-8">
        <div className="mb-3 flex items-center gap-2">
          <Briefcase size={16} weight="duotone" />
          <h2 className="font-display text-lg font-black">My delivery projects</h2>
          <span className="font-mono-label">{projects?.length ?? "…"}</span>
        </div>
        {projects === null ? (
          <div className="font-mono-label">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] bg-white p-6 text-sm text-[#4B5563]" data-testid="digital-projects-empty">
            No delivery projects assigned to you yet. When your Program Manager assigns you a digital project, it appears here.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2" data-testid="digital-projects-list">
            {projects.map((p) => (
              <button
                key={p.lead_id}
                type="button"
                data-testid={`digital-project-${p.lead_id}`}
                onClick={() => nav(`/va/leads/${p.lead_id}`)}
                className="border border-[#030712] bg-white p-4 text-left transition-colors hover:bg-[#F9FAFB]"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-bold">{p.prospect_name}</div>
                  <StageBadge stage={p.stage} />
                </div>
                <div className="mt-1 text-xs text-[#4B5563]">{serviceTypeLabel(p.service_type)}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {(p.job_value ?? p.estimated_budget) != null && (
                    <span className="font-semibold">
                      ${Number(p.job_value ?? p.estimated_budget).toFixed(0)} {p.job_value == null ? "est." : "value"}
                    </span>
                  )}
                  {p.assigned_at && (
                    <span className="text-[#9CA3AF]">Assigned {new Date(p.assigned_at).toLocaleDateString()}</span>
                  )}
                  {p.va_name && <span className="text-[#9CA3AF]">Sourced by {p.va_name}</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* My digital leads */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <Monitor size={16} weight="duotone" />
          <h2 className="font-display text-lg font-black">My digital leads</h2>
          <span className="font-mono-label">{leads?.length ?? "…"}</span>
        </div>
        {leads === null ? (
          <div className="font-mono-label">Loading…</div>
        ) : leads.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] bg-white p-6 text-sm text-[#4B5563]" data-testid="digital-leads-empty">
            No digital leads yet. Hit &ldquo;New digital lead&rdquo; to submit your first web / app / sourcing prospect.
          </div>
        ) : (
          <div className="border border-[#E5E7EB] bg-white overflow-x-auto" data-testid="digital-leads-table">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                  <th className="px-3 py-3">Prospect</th>
                  <th className="px-3 py-3">Service</th>
                  <th className="px-3 py-3">Budget</th>
                  <th className="px-3 py-3">Est. commission</th>
                  <th className="px-3 py-3">Submitted</th>
                  <th className="px-3 py-3">Stage</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((l) => {
                  const comm = estCommission(l);
                  return (
                    <tr
                      key={l.lead_id}
                      data-testid={`digital-lead-row-${l.lead_id}`}
                      onClick={() => nav(`/va/leads/${l.lead_id}`)}
                      className="cursor-pointer border-t border-[#E5E7EB] hover:bg-[#F9FAFB]"
                    >
                      <td className="px-3 py-3">
                        <div className="font-semibold text-[#0044FF]">{l.prospect_name}</div>
                        <div className="text-xs text-[#4B5563]">{l.prospect_phone}</div>
                      </td>
                      <td className="px-3 py-3 text-xs">{serviceTypeLabel(l.service_type)}</td>
                      <td className="px-3 py-3 text-xs">
                        {(l.job_value ?? l.estimated_budget) != null
                          ? `$${Number(l.job_value ?? l.estimated_budget).toFixed(0)}`
                          : "—"}
                      </td>
                      <td className="px-3 py-3 text-xs font-semibold text-emerald-700">
                        {comm != null ? `$${comm.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-3 py-3 text-xs text-[#4B5563]">{(l.created_at || "").slice(0, 10)}</td>
                      <td className="px-3 py-3"><StageBadge stage={l.stage} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
