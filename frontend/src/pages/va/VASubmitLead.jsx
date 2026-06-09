import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { WarningCircle, PaperPlaneTilt } from "@phosphor-icons/react";

const SERVICE_TYPES = [
  { value: "routine", label: "Routine cleaning" },
  { value: "deep", label: "Deep cleaning" },
  { value: "moveout", label: "Move-out cleaning" },
  { value: "specialty", label: "Specialty cleaning" },
  { value: "commercial", label: "Commercial" },
  { value: "unknown", label: "Unknown / Other" },
];

const PROPERTY_SIZES = [
  { value: "studio", label: "Studio" },
  { value: "1br", label: "1 bedroom" },
  { value: "2br", label: "2 bedroom" },
  { value: "3br", label: "3 bedroom" },
  { value: "4br", label: "4 bedroom" },
  { value: "5br", label: "5 bedroom" },
  { value: "commercial", label: "Commercial" },
];

const SOURCES = [
  { value: "facebook_marketplace", label: "Facebook Marketplace" },
  { value: "facebook_groups", label: "Facebook Groups" },
  { value: "craigslist", label: "Craigslist" },
  { value: "direct_message", label: "Direct Message" },
  { value: "referral", label: "Referral" },
  { value: "other", label: "Other" },
];

export default function VASubmitLead() {
  const nav = useNavigate();
  const [form, setForm] = useState({
    prospect_name: "",
    prospect_phone: "",
    prospect_email: "",
    prospect_address: "",
    service_type: "routine",
    property_size: "1br",
    preferred_datetime: "",
    source: "facebook_marketplace",
    notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [dupeWarn, setDupeWarn] = useState(null);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    setDupeWarn(null);
    setLoading(true);
    try {
      const payload = { ...form };
      if (!payload.prospect_email) delete payload.prospect_email;
      if (!payload.prospect_address) delete payload.prospect_address;
      if (!payload.preferred_datetime) delete payload.preferred_datetime;
      if (!payload.notes) delete payload.notes;
      await api.post("/va/leads", payload);
      toast.success("Lead submitted — ownership locked to you.");
      nav("/va/leads", { replace: true });
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

  return (
    <div className="p-6 md:p-10 max-w-3xl" data-testid="va-submit-lead">
      <div className="mb-6">
        <div className="font-mono-label">Submit lead</div>
        <h1 className="font-display text-4xl font-black tracking-tight">New lead intake</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Timestamp ownership locks to you on submit. Leads submitted outside this form aren&apos;t eligible for commission.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-5 border border-[#E5E7EB] bg-white p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="prospect_name" className="font-mono-label">Prospect full name *</Label>
            <Input
              data-testid="lead-prospect-name"
              id="prospect_name"
              required
              minLength={2}
              value={form.prospect_name}
              onChange={(e) => upd("prospect_name", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label htmlFor="prospect_phone" className="font-mono-label">Phone number *</Label>
            <Input
              data-testid="lead-prospect-phone"
              id="prospect_phone"
              required
              type="tel"
              value={form.prospect_phone}
              onChange={(e) => upd("prospect_phone", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label htmlFor="prospect_email" className="font-mono-label">Email <span className="text-[#9CA3AF]">(optional)</span></Label>
            <Input
              data-testid="lead-prospect-email"
              id="prospect_email"
              type="email"
              value={form.prospect_email}
              onChange={(e) => upd("prospect_email", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label htmlFor="prospect_address" className="font-mono-label">Address <span className="text-[#9CA3AF]">(optional)</span></Label>
            <Input
              data-testid="lead-prospect-address"
              id="prospect_address"
              value={form.prospect_address}
              onChange={(e) => upd("prospect_address", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label htmlFor="service_type" className="font-mono-label">Service type *</Label>
            <select
              data-testid="lead-service-type"
              id="service_type"
              required
              value={form.service_type}
              onChange={(e) => upd("service_type", e.target.value)}
              className="mt-2 h-11 w-full border border-[#030712] bg-white px-3 text-sm"
            >
              {SERVICE_TYPES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="property_size" className="font-mono-label">Property size *</Label>
            <select
              data-testid="lead-property-size"
              id="property_size"
              required
              value={form.property_size}
              onChange={(e) => upd("property_size", e.target.value)}
              className="mt-2 h-11 w-full border border-[#030712] bg-white px-3 text-sm"
            >
              {PROPERTY_SIZES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="preferred_datetime" className="font-mono-label">Preferred date/time <span className="text-[#9CA3AF]">(optional)</span></Label>
            <Input
              data-testid="lead-preferred-datetime"
              id="preferred_datetime"
              type="datetime-local"
              value={form.preferred_datetime}
              onChange={(e) => upd("preferred_datetime", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label htmlFor="source" className="font-mono-label">How did you reach this lead? *</Label>
            <select
              data-testid="lead-source"
              id="source"
              required
              value={form.source}
              onChange={(e) => upd("source", e.target.value)}
              className="mt-2 h-11 w-full border border-[#030712] bg-white px-3 text-sm"
            >
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <Label htmlFor="notes" className="font-mono-label">Notes <span className="text-[#9CA3AF]">(optional)</span></Label>
          <Textarea
            data-testid="lead-notes"
            id="notes"
            rows={4}
            value={form.notes}
            onChange={(e) => upd("notes", e.target.value)}
            className="mt-2 rounded-none border-[#030712]"
            placeholder="Anything Ops should know — special requests, urgency, language, access details..."
          />
        </div>

        {dupeWarn && (
          <div
            data-testid="lead-duplicate-warning"
            className="flex items-start gap-3 border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
          >
            <WarningCircle size={20} weight="duotone" className="mt-0.5 shrink-0" />
            <div>
              <div className="font-semibold">Duplicate lead blocked</div>
              <div className="mt-1">{dupeWarn.message}</div>
              <div className="mt-2 text-xs">
                Original submission: {dupeWarn.original_va_name} on{" "}
                {(dupeWarn.original_date || "").slice(0, 10)} · stage:{" "}
                <span className="font-mono uppercase">{dupeWarn.original_stage}</span>
              </div>
            </div>
          </div>
        )}

        {err && (
          <div data-testid="lead-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {err}
          </div>
        )}

        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => nav("/va")}
            className="h-11 rounded-none border-[#030712]"
          >
            Cancel
          </Button>
          <Button
            data-testid="lead-submit-btn"
            type="submit"
            disabled={loading}
            className="h-11 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            <PaperPlaneTilt size={16} weight="bold" className="mr-2" />
            {loading ? "Submitting…" : "Submit lead"}
          </Button>
        </div>
      </form>
    </div>
  );
}
