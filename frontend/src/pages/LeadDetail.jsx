import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  Pencil,
  Trash,
  ArrowCounterClockwise,
  Clock,
  CurrencyDollar,
  FloppyDisk,
  X,
} from "@phosphor-icons/react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import MessageUserButton from "@/components/messages/MessageUserButton";
import { SERVICE_TYPES, DIGITAL_SERVICE_TYPES, PROPERTY_SIZES, LEAD_SOURCES, serviceTypeLabel, leadSourceLabel, isDigitalService } from "@/lib/leadOptions";

/**
 * Lead detail page — shared by admin (/ops/va-program/leads/:id) and VA
 * (/va/leads/:id) views. Backend access control means each role gets data
 * appropriate to them (VAs only see their own).
 *
 * Props:
 *   - scope: 'admin' (PM/Owner edit anything) | 'va' (VA edits own while stage='new_lead')
 *
 * The component is intentionally not split into 3 files — the shared
 * form layout + activity timeline is exactly the same for both roles,
 * and the only divergence is the edit-permission check + a couple of
 * admin-only fields (job_value, owner reassign). Two-component split
 * would mean ~400 lines of duplication.
 */
export default function LeadDetail({ scope = "admin" }) {
  const { leadId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const apiBase = scope === "va" ? `/va/leads/${leadId}` : `/pm/leads/${leadId}`;
  const backHref = scope === "va" ? "/va/leads" : "/ops/va-program/pipeline";

  const load = async () => {
    try {
      const { data } = await api.get(apiBase);
      setData(data);
      setForm({
        prospect_name: data.lead.prospect_name || "",
        prospect_phone: data.lead.prospect_phone || "",
        prospect_email: data.lead.prospect_email || "",
        prospect_address: data.lead.prospect_address || "",
        service_type: data.lead.service_type || "",
        property_size: data.lead.property_size || "",
        preferred_datetime: data.lead.preferred_datetime || "",
        source: data.lead.source || "",
        notes: data.lead.notes || "",
        estimated_budget: data.lead.estimated_budget ?? "",
        job_value: data.lead.job_value ?? "",
        reason: "",
      });
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [leadId]);

  const lead = data?.lead;
  const activity = data?.activity || [];
  const commission = data?.commission;

  // VA edit rule mirrors backend: VA can edit ONLY while stage='new_lead'
  const canEdit =
    scope === "admin"
      ? !lead?.deleted_at
      : lead?.stage === "new_lead" && !lead?.deleted_at;

  const canDelete =
    scope === "admin"
      ? !lead?.deleted_at
      : lead?.stage === "new_lead" && !lead?.deleted_at && !commission;

  const save = async () => {
    setSaving(true);
    try {
      // Only send fields that changed — keeps activity log clean.
      const payload = {};
      Object.entries(form).forEach(([k, v]) => {
        if (k === "reason") return;
        const orig = lead?.[k];
        if (v !== "" && v !== orig) payload[k] = v;
      });
      if (Object.keys(payload).length === 0) {
        toast.info("No changes");
        setEditing(false);
        return;
      }
      if (form.reason) payload.reason = form.reason;
      // Numeric fields
      if ("job_value" in payload) {
        payload.job_value = parseFloat(payload.job_value);
      }
      if ("estimated_budget" in payload) {
        payload.estimated_budget = parseFloat(payload.estimated_budget);
      }
      await api.patch(apiBase, payload);
      toast.success("Lead updated");
      setEditing(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const trash = async () => {
    const reason = window.prompt(
      `Move "${lead.prospect_name}" to Trash?\n\nKept restorable for 30 days. Reason (optional):`,
      ""
    );
    if (reason === null) return;
    try {
      await api.delete(apiBase, { data: { reason } });
      toast.success("Moved to Trash");
      if (scope === "va") {
        nav("/va/leads");
      } else {
        load();
      }
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const restore = async () => {
    try {
      await api.post(`/pm/leads/${leadId}/restore`);
      toast.success("Lead restored");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (err) {
    return (
      <div className="p-6 md:p-10">
        <button onClick={() => nav(backHref)} className="font-mono-label hover:underline">
          ← Back
        </button>
        <div className="mt-4 border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>
      </div>
    );
  }

  if (!data) {
    return <div className="p-6 md:p-10 font-mono-label">Loading…</div>;
  }

  return (
    <div className="p-6 md:p-10" data-testid="lead-detail">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => nav(backHref)}
          data-testid="lead-detail-back"
          className="font-mono-label flex items-center gap-1 hover:underline"
        >
          <ArrowLeft size={12} /> Back to {scope === "va" ? "my leads" : "pipeline"}
        </button>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="font-mono-label">
              Lead · {lead.lead_id}
              {lead.deleted_at && (
                <span className="ml-2 inline-block bg-[#DC2626] px-2 py-0.5 text-[9px] uppercase tracking-widest text-white">
                  In Trash
                </span>
              )}
            </div>
            <h1 className="font-display text-4xl font-black tracking-tight">
              {lead.prospect_name}
            </h1>
            <div className="mt-1 text-sm text-[#4B5563]">
              {lead.va_name && (
                <>
                  Submitted by <strong>{lead.va_name}</strong>
                  {scope === "admin" && lead.va_user_id && (
                    <span className="ml-2 inline-block align-middle">
                      <MessageUserButton
                        userId={lead.va_user_id}
                        name={lead.va_name}
                        variant="compact"
                        label="Message VA"
                        testId="lead-detail-message-va"
                      />
                    </span>
                  )}
                  {" · "}
                </>
              )}
              {(lead.created_at || "").slice(0, 10)}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            {lead.deleted_at && scope === "admin" && (
              <Button
                data-testid="lead-detail-restore"
                onClick={restore}
                className="h-10 rounded-none bg-[#10B981] text-white hover:bg-[#059669]"
              >
                <ArrowCounterClockwise size={14} className="mr-1" weight="bold" /> Restore
              </Button>
            )}
            {!editing && canEdit && (
              <Button
                data-testid="lead-detail-edit-btn"
                onClick={() => setEditing(true)}
                variant="outline"
                className="h-10 rounded-none border-[#030712]"
              >
                <Pencil size={14} className="mr-1" /> Edit
              </Button>
            )}
            {!editing && canDelete && (
              <Button
                data-testid="lead-detail-trash-btn"
                onClick={trash}
                variant="outline"
                className="h-10 rounded-none border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white"
              >
                <Trash size={14} className="mr-1" /> Move to Trash
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Lead info card / form */}
          <section className="border border-[#E5E7EB] bg-white">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-3">
              <div className="font-mono-label">Prospect info</div>
              {editing && (
                <div className="flex gap-2">
                  <Button
                    data-testid="lead-detail-cancel"
                    onClick={() => {
                      setEditing(false);
                      load();
                    }}
                    variant="ghost"
                    className="h-8 rounded-none px-3 text-xs"
                  >
                    <X size={12} className="mr-1" /> Cancel
                  </Button>
                  <Button
                    data-testid="lead-detail-save"
                    onClick={save}
                    disabled={saving}
                    className="h-8 rounded-none bg-[#030712] px-3 text-xs text-white"
                  >
                    <FloppyDisk size={12} className="mr-1" /> {saving ? "Saving…" : "Save"}
                  </Button>
                </div>
              )}
            </div>
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <Field label="Name">
                {editing ? (
                  <Input
                    data-testid="field-prospect_name"
                    value={form.prospect_name}
                    onChange={(e) => setForm({ ...form, prospect_name: e.target.value })}
                    className="h-9 rounded-none border-[#030712]"
                  />
                ) : (
                  <span>{lead.prospect_name}</span>
                )}
              </Field>
              <Field label="Phone">
                {editing ? (
                  <Input
                    data-testid="field-prospect_phone"
                    value={form.prospect_phone}
                    onChange={(e) => setForm({ ...form, prospect_phone: e.target.value })}
                    className="h-9 rounded-none border-[#030712]"
                  />
                ) : (
                  <a href={`tel:${lead.prospect_phone}`} className="text-[#0044FF] hover:underline">
                    {lead.prospect_phone}
                  </a>
                )}
              </Field>
              <Field label="Email">
                {editing ? (
                  <Input
                    data-testid="field-prospect_email"
                    value={form.prospect_email}
                    onChange={(e) => setForm({ ...form, prospect_email: e.target.value })}
                    className="h-9 rounded-none border-[#030712]"
                  />
                ) : lead.prospect_email ? (
                  <a href={`mailto:${lead.prospect_email}`} className="text-[#0044FF] hover:underline">
                    {lead.prospect_email}
                  </a>
                ) : (
                  <span className="text-[#9CA3AF]">—</span>
                )}
              </Field>
              <Field label="Address">
                {editing ? (
                  <Input
                    data-testid="field-prospect_address"
                    value={form.prospect_address}
                    onChange={(e) => setForm({ ...form, prospect_address: e.target.value })}
                    className="h-9 rounded-none border-[#030712]"
                  />
                ) : (
                  <span>{lead.prospect_address || "—"}</span>
                )}
              </Field>
              <Field label="Service">
                {editing ? (
                  <select
                    data-testid="field-service_type"
                    value={form.service_type}
                    onChange={(e) => setForm({ ...form, service_type: e.target.value })}
                    className="h-9 border border-[#030712] bg-white px-2 text-sm"
                  >
                    <optgroup label="Field services">
                      {SERVICE_TYPES.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Digital services">
                      {DIGITAL_SERVICE_TYPES.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </optgroup>
                  </select>
                ) : (
                  <span>{serviceTypeLabel(lead.service_type)}</span>
                )}
              </Field>
              {!isDigitalService(editing ? form.service_type : lead.service_type) && (
              <Field label="Size">
                {editing ? (
                  <select
                    data-testid="field-property_size"
                    value={form.property_size}
                    onChange={(e) => setForm({ ...form, property_size: e.target.value })}
                    className="h-9 border border-[#030712] bg-white px-2 text-sm"
                  >
                    {PROPERTY_SIZES.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                ) : (
                  <span className="uppercase font-mono text-xs">{lead.property_size || "—"}</span>
                )}
              </Field>
              )}
              <Field label="Source">
                {editing ? (
                  <select
                    data-testid="field-source"
                    value={form.source}
                    onChange={(e) => setForm({ ...form, source: e.target.value })}
                    className="h-9 border border-[#030712] bg-white px-2 text-sm"
                  >
                    {LEAD_SOURCES.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                ) : (
                  <span className="text-xs">{leadSourceLabel(lead.source)}</span>
                )}
              </Field>
              <Field label="Preferred datetime">
                {editing ? (
                  <Input
                    data-testid="field-preferred_datetime"
                    placeholder="e.g. 2026-03-15 14:00"
                    value={form.preferred_datetime}
                    onChange={(e) => setForm({ ...form, preferred_datetime: e.target.value })}
                    className="h-9 rounded-none border-[#030712]"
                  />
                ) : (
                  <span>{lead.preferred_datetime || "—"}</span>
                )}
              </Field>
              {isDigitalService(lead.service_type) && (
                <Field label="Estimated budget ($)">
                  {editing ? (
                    <Input
                      data-testid="field-estimated_budget"
                      type="number"
                      value={form.estimated_budget}
                      onChange={(e) => setForm({ ...form, estimated_budget: e.target.value })}
                      className="h-9 rounded-none border-[#030712]"
                    />
                  ) : (
                    <span>
                      {lead.estimated_budget != null ? `$${Number(lead.estimated_budget).toFixed(2)}` : "—"}
                    </span>
                  )}
                </Field>
              )}
              {scope === "admin" && (
                <Field label="Job value ($)">
                  {editing ? (
                    <Input
                      data-testid="field-job_value"
                      type="number"
                      value={form.job_value}
                      onChange={(e) => setForm({ ...form, job_value: e.target.value })}
                      className="h-9 rounded-none border-[#030712]"
                    />
                  ) : (
                    <span>
                      {lead.job_value != null ? `$${Number(lead.job_value).toFixed(2)}` : "—"}
                    </span>
                  )}
                </Field>
              )}
              <div className="md:col-span-2">
                <Field label="Notes">
                  {editing ? (
                    <Textarea
                      data-testid="field-notes"
                      value={form.notes}
                      onChange={(e) => setForm({ ...form, notes: e.target.value })}
                      rows={4}
                      className="rounded-none border-[#030712]"
                    />
                  ) : (
                    <p className="whitespace-pre-wrap text-sm">{lead.notes || "—"}</p>
                  )}
                </Field>
              </div>
              {editing && (
                <div className="md:col-span-2">
                  <Field label="Why are you editing this lead? (optional, logged)">
                    <Input
                      data-testid="field-reason"
                      value={form.reason}
                      onChange={(e) => setForm({ ...form, reason: e.target.value })}
                      placeholder="e.g. Corrected phone typo"
                      className="h-9 rounded-none border-[#030712]"
                    />
                  </Field>
                </div>
              )}
            </div>
          </section>

          {/* Activity timeline */}
          <section className="border border-[#E5E7EB] bg-white">
            <div className="border-b border-[#E5E7EB] px-5 py-3">
              <div className="font-mono-label flex items-center gap-2">
                <Clock size={12} /> Activity timeline · {activity.length}
              </div>
            </div>
            {activity.length === 0 ? (
              <div className="p-5 text-sm text-[#9CA3AF]">No activity yet.</div>
            ) : (
              <ol className="divide-y divide-[#F3F4F6]" data-testid="activity-timeline">
                {activity.map((a) => (
                  <li key={a.activity_id} className="px-5 py-3" data-testid={`activity-${a.kind}`}>
                    <ActivityRow event={a} />
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <section className="border border-[#E5E7EB] bg-white p-5">
            <div className="font-mono-label">Pipeline stage</div>
            <div className="mt-2 text-lg font-bold uppercase tracking-widest">
              {(lead.stage || "—").replace(/_/g, " ")}
            </div>
            {lead.stage_changed_at && (
              <div className="mt-1 text-xs text-[#4B5563]">
                Updated {new Date(lead.stage_changed_at).toLocaleString()}
              </div>
            )}
            {scope === "admin" && (
              <Button
                onClick={() => nav("/ops/va-program/pipeline")}
                variant="outline"
                className="mt-4 h-9 w-full rounded-none border-[#030712] text-xs"
              >
                Change stage on pipeline →
              </Button>
            )}
          </section>

          {lead.assigned_va_id && (
            <section className="border border-[#E5E7EB] bg-white p-5" data-testid="lead-assigned-va-card">
              <div className="font-mono-label">Delivery VA</div>
              <div className="mt-2 text-sm font-semibold">{lead.assigned_va_name || lead.assigned_va_id}</div>
              {lead.assigned_at && (
                <div className="mt-1 text-xs text-[#4B5563]">
                  Assigned {new Date(lead.assigned_at).toLocaleDateString()}
                </div>
              )}
            </section>
          )}

          {commission && (
            <section className="border border-[#E5E7EB] bg-white p-5">
              <div className="font-mono-label flex items-center gap-1">
                <CurrencyDollar size={12} /> Commission
              </div>
              <div className="mt-2 text-2xl font-bold">
                ${Number(commission.amount || 0).toFixed(2)}
              </div>
              <div className="mt-1 text-xs uppercase tracking-widest text-[#4B5563]">
                {commission.status?.replace(/_/g, " ")}
              </div>
              {commission.calc_notes && (
                <p className="mt-1 text-[11px] text-[#9CA3AF]" data-testid="commission-calc-notes">{commission.calc_notes}</p>
              )}
              {commission.notes && (
                <p className="mt-2 text-xs text-[#4B5563]">{commission.notes}</p>
              )}
            </section>
          )}

          {lead.deleted_at && (
            <section className="border border-[#FCA5A5] bg-[#FEF2F2] p-5">
              <div className="font-mono-label text-[#DC2626]">In Trash</div>
              <div className="mt-2 text-xs">
                Deleted {new Date(lead.deleted_at).toLocaleString()}
                {lead.deleted_reason && (
                  <>
                    <br />
                    Reason: <strong>{lead.deleted_reason}</strong>
                  </>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="font-mono-label mb-1">{label}</div>
      <div className="text-sm">{children}</div>
    </label>
  );
}

function ActivityRow({ event }) {
  const date = event.created_at
    ? new Date(event.created_at).toLocaleString()
    : "";
  const role = event.actor_role || "system";
  const who = event.actor_name || event.actor_user_id || "system";
  const kindLabel = {
    edited: "Edited",
    stage_changed: "Stage changed",
    deleted: "Moved to Trash",
    restored: "Restored from Trash",
    reassigned: "Reassigned",
    note_added: "Note added",
    delivery_assigned: "Delivery VA assigned",
    delivery_unassigned: "Delivery VA removed",
  }[event.kind] || event.kind;

  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-bold text-sm">{kindLabel}</span>
        <span className="text-xs text-[#4B5563]">
          by {who} <em className="text-[#9CA3AF]">({role})</em>
        </span>
        <span className="ml-auto text-[10px] text-[#9CA3AF]">{date}</span>
      </div>
      <ActivityDetail event={event} />
    </div>
  );
}

function ActivityDetail({ event }) {
  const d = event.detail || {};
  if (event.kind === "stage_changed") {
    return (
      <div className="mt-1 text-xs">
        <span className="uppercase tracking-wide text-[#9CA3AF]">{d.from || "—"}</span>
        <span className="mx-1">→</span>
        <span className="font-semibold uppercase tracking-wide">{d.to}</span>
        {d.job_value != null && (
          <span className="ml-2 text-[#10B981]">${Number(d.job_value).toFixed(2)}</span>
        )}
        {d.note && <div className="mt-1 italic text-[#4B5563]">&ldquo;{d.note}&rdquo;</div>}
      </div>
    );
  }
  if (event.kind === "edited" && d.changes) {
    return (
      <ul className="mt-1 space-y-0.5 text-xs">
        {Object.entries(d.changes).map(([field, val]) => (
          <li key={field}>
            <span className="font-mono text-[#9CA3AF]">{field}:</span>{" "}
            <span className="line-through text-[#9CA3AF]">{String(val?.from ?? "—").slice(0, 40)}</span>
            <span className="mx-1">→</span>
            <span className="text-[#030712] font-medium">{String(val?.to ?? "—").slice(0, 80)}</span>
          </li>
        ))}
        {d.reason && <li className="italic text-[#4B5563]">&ldquo;{d.reason}&rdquo;</li>}
      </ul>
    );
  }
  if (event.kind === "delivery_assigned" || event.kind === "delivery_unassigned") {
    return (
      <div className="mt-1 text-xs">
        <span className="text-[#9CA3AF]">{d.from || "—"}</span>
        <span className="mx-1">→</span>
        <span className="font-semibold">{d.to || "—"}</span>
      </div>
    );
  }
  if (event.kind === "deleted" && d.reason) {
    return <div className="mt-1 text-xs italic text-[#4B5563]">&ldquo;{d.reason}&rdquo;</div>;
  }
  return null;
}
