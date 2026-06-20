import React, { useEffect, useState } from "react";
import {
  Handshake,
  PlusCircle,
  MapPin,
  CurrencyDollar,
  CheckCircle,
  Clock,
  WarningCircle,
  X,
  Camera,
  CaretRight,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";

// Map service-category enum → human label (matches backend SERVICE_CATEGORIES).
const CATEGORY_LABELS = {
  carpet_cleaning: "Carpet cleaning",
  junk_removal: "Junk removal",
  painting: "Painting",
  handyman: "Handyman",
  landscaping: "Landscaping",
  moving: "Moving",
  window_cleaning: "Window cleaning",
  pressure_washing: "Pressure washing",
  pest_control: "Pest control",
  appliance_repair: "Appliance repair",
  commercial_account: "Commercial / recurring",
  other: "Other",
};

// Status pills — worker-friendly labels (different from internal enum).
const STATUS_VIEW = {
  submitted: { label: "Submitted", tone: "neutral" },
  under_review: { label: "Mechie reviewing", tone: "info" },
  quoted: { label: "Quote sent", tone: "info" },
  scheduled: { label: "Job scheduled", tone: "info" },
  in_progress: { label: "Job in progress", tone: "info" },
  completed: { label: "Job completed", tone: "info" },
  invoiced: { label: "Invoiced", tone: "info" },
  paid: { label: "Customer paid · commission eligible", tone: "success" },
  commission_released: { label: "Commission paid to you", tone: "success" },
  void: { label: "Voided", tone: "void" },
  self_fulfilled: { label: "Self-fulfilled · no commission", tone: "void" },
};

const TONE_CLASSES = {
  neutral: "bg-[#E5E7EB] text-[#374151] border-[#E5E7EB]",
  info: "bg-[#F0F4FF] text-[#0044FF] border-[#0044FF]",
  success: "bg-[#D1FAE5] text-[#065F46] border-[#10B981]",
  void: "bg-[#FEE2E2] text-[#991B1B] border-[#EF4444]",
};

export default function WorkerReferrals() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [err, setErr] = useState("");

  const load = async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await api.get("/worker/referrals");
      setData(r.data);
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="p-6 md:p-10" data-testid="worker-referrals-page">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label flex items-center gap-1.5">
            <Handshake size={14} weight="fill" /> Network referrals
          </div>
          <h1 className="font-display text-4xl font-black tracking-tight">
            Refer a lead. Earn 10%.
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
            Spotted a property that needs something outside your trade?
            Drop the lead here. We&apos;ll quote it, dispatch the right contractor,
            and pay you <strong>10% of the invoice</strong> once the job&apos;s done and the
            customer pays. You don&apos;t sell. You don&apos;t quote. You just spot.
          </p>
        </div>
        <Button
          data-testid="open-submit-referral"
          onClick={() => setSubmitOpen(true)}
          className="h-12 rounded-none bg-[#0044FF] px-5 text-white hover:bg-[#0036cc]"
        >
          <PlusCircle size={18} className="mr-2" weight="fill" /> Submit a lead
        </Button>
      </div>

      {/* Earnings rollup */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="referral-rollup">
        <RollupCard
          label="Commission pending"
          value={data?.totals?.commission_pending}
          sub="Quoted, awaiting customer payment"
          icon={Clock}
          color="text-[#4B5563]"
        />
        <RollupCard
          label="Eligible"
          value={data?.totals?.commission_eligible}
          sub="Customer paid · you'll see it on next payout"
          icon={CurrencyDollar}
          color="text-[#0044FF]"
        />
        <RollupCard
          label="Paid to you"
          value={data?.totals?.commission_paid}
          sub="Lifetime via this program"
          icon={CheckCircle}
          color="text-[#10B981]"
        />
      </div>

      {err && (
        <div className="mb-4 border border-[#EF4444] bg-[#FEE2E2] p-3 text-sm text-[#991B1B]">
          {err}
        </div>
      )}

      {/* List */}
      {loading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 animate-pulse border border-[#E5E7EB] bg-white" />
          ))}
        </div>
      )}
      {!loading && (data?.items?.length || 0) === 0 && (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center">
          <Handshake size={36} weight="duotone" className="mx-auto text-[#9CA3AF]" />
          <div className="mt-3 font-display text-lg font-bold">No referrals yet.</div>
          <div className="mt-1 text-sm text-[#4B5563]">
            Spot something out of your scope on the next job?
            Drop it here and we&apos;ll take it from there.
          </div>
          <Button
            data-testid="empty-state-submit-cta"
            onClick={() => setSubmitOpen(true)}
            className="mt-5 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            <PlusCircle size={16} className="mr-2" /> Submit your first
          </Button>
        </div>
      )}
      {!loading && data?.items?.length > 0 && (
        <div className="space-y-3">
          {data.items.map((r) => (
            <ReferralCard key={r.referral_id} r={r} />
          ))}
        </div>
      )}

      {submitOpen && (
        <SubmitReferralModal
          categories={data?.service_categories || Object.keys(CATEGORY_LABELS)}
          onClose={() => setSubmitOpen(false)}
          onSubmitted={() => {
            setSubmitOpen(false);
            load();
            toast.success("Lead submitted. Mechie will review and follow up.");
          }}
        />
      )}
    </div>
  );
}

function RollupCard({ label, value, sub, icon: Icon, color }) {
  return (
    <div className="border border-[#030712] bg-white p-5">
      <div className="font-mono-label flex items-center gap-1.5 text-[10px] tracking-widest text-[#4B5563]">
        <Icon size={12} weight="fill" className={color} /> {label}
      </div>
      <div className="mt-2 font-display text-3xl font-black leading-none">
        ${Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </div>
      <div className="mt-1.5 text-[11px] text-[#4B5563]">{sub}</div>
    </div>
  );
}

function ReferralCard({ r }) {
  const view = STATUS_VIEW[r.status] || { label: r.status, tone: "neutral" };
  const isVoid = view.tone === "void";
  const isWin = view.tone === "success";
  return (
    <div
      data-testid={`referral-card-${r.referral_id}`}
      className={`border bg-white p-4 ${
        isVoid ? "border-[#EF4444]/40" : isWin ? "border-[#10B981]/40" : "border-[#E5E7EB]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 border px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                TONE_CLASSES[view.tone]
              }`}
            >
              {view.tone === "success" && <CheckCircle size={10} weight="fill" />}
              {view.tone === "void" && <WarningCircle size={10} weight="fill" />}
              {view.label}
            </span>
            <span className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
              {CATEGORY_LABELS[r.service_category] || r.service_category}
            </span>
            {r.intent === "for_self" && (
              <span className="inline-flex items-center gap-1 border border-[#F59E0B] bg-[#FFFBEB] px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-[#92400E]">
                For yourself
              </span>
            )}
          </div>
          <div className="mt-2 flex items-start gap-2 font-display text-base font-bold">
            <MapPin size={14} className="mt-1 shrink-0" /> {r.property_address}
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-[#4B5563]">
            {r.opportunity_description}
          </div>
        </div>
        <div className="text-right">
          {r.commission_amount > 0 && (
            <>
              <div className="font-mono-label text-[10px] text-[#4B5563]">
                Your cut
              </div>
              <div
                className={`font-display text-2xl font-black ${
                  isWin ? "text-[#10B981]" : "text-[#030712]"
                }`}
              >
                ${Number(r.commission_amount).toLocaleString("en-US")}
              </div>
            </>
          )}
          {r.quoted_amount && !r.commission_amount && (
            <>
              <div className="font-mono-label text-[10px] text-[#4B5563]">
                Quoted
              </div>
              <div className="font-display text-lg font-bold text-[#0044FF]">
                ${Number(r.quoted_amount).toLocaleString("en-US")}
              </div>
              <div className="font-mono-label text-[9px] text-[#4B5563]">
                10% if it closes
              </div>
            </>
          )}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-[#E5E7EB] pt-2 text-[11px] text-[#4B5563]">
        <span>Submitted {timeAgo(r.created_at)}</span>
        {r.commission_paid_date && (
          <span className="text-[#10B981]">Paid {timeAgo(r.commission_paid_date)}</span>
        )}
      </div>
    </div>
  );
}

function SubmitReferralModal({ categories, onClose, onSubmitted }) {
  const [form, setForm] = useState({
    property_address: "",
    opportunity_description: "",
    service_category: "carpet_cleaning",
    intent: "for_another",
    contact_name: "",
    contact_phone: "",
    contact_email: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.property_address.trim() || form.property_address.trim().length < 4) {
      toast.error("Property address is required");
      return;
    }
    if (
      !form.opportunity_description.trim() ||
      form.opportunity_description.trim().length < 4
    ) {
      toast.error("Tell us what you spotted");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/worker/referrals", form);
      onSubmitted();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      data-testid="submit-referral-modal"
    >
      <div
        className="flex w-full max-w-2xl flex-col border border-[#030712] bg-white shadow-2xl sm:max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#030712] bg-[#030712] px-5 py-3 text-white">
          <div className="flex items-center gap-2">
            <Handshake size={20} weight="fill" />
            <div>
              <div className="font-display text-lg font-bold">Submit a referral</div>
              <div className="font-mono-label text-[10px] text-white/70">
                Earn 10% when it closes
              </div>
            </div>
          </div>
          <button
            data-testid="close-submit"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center text-white hover:bg-white/10"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {/* Intent toggle — explicit so Mechie sees it */}
          <div>
            <Label className="font-mono-label">For yourself or another contractor?</Label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <button
                type="button"
                data-testid="intent-for_another"
                onClick={() => set("intent", "for_another")}
                className={`border p-3 text-left text-sm ${
                  form.intent === "for_another"
                    ? "border-[#030712] bg-[#030712] text-white"
                    : "border-[#E5E7EB] bg-white hover:border-[#030712]"
                }`}
              >
                <div className="font-display font-bold">For another contractor</div>
                <div
                  className={`mt-1 text-[11px] ${
                    form.intent === "for_another" ? "text-white/70" : "text-[#4B5563]"
                  }`}
                >
                  HCOB dispatches it · you earn 10%
                </div>
              </button>
              <button
                type="button"
                data-testid="intent-for_self"
                onClick={() => set("intent", "for_self")}
                className={`border p-3 text-left text-sm ${
                  form.intent === "for_self"
                    ? "border-[#F59E0B] bg-[#FFFBEB] text-[#92400E]"
                    : "border-[#E5E7EB] bg-white hover:border-[#F59E0B]"
                }`}
              >
                <div className="font-display font-bold">For yourself</div>
                <div className="mt-1 text-[11px]">
                  You want to take the job · no commission, but the gig is yours
                </div>
              </button>
            </div>
          </div>

          <div>
            <Label htmlFor="ref-addr" className="font-mono-label">
              Property address <span className="text-[#EF4444]">*</span>
            </Label>
            <Input
              id="ref-addr"
              data-testid="referral-address"
              value={form.property_address}
              onChange={(e) => set("property_address", e.target.value)}
              placeholder="123 Main St, Baltimore, MD 21201"
              className="mt-1 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">
              What did you spot? <span className="text-[#EF4444]">*</span>
            </Label>
            <Textarea
              data-testid="referral-description"
              value={form.opportunity_description}
              onChange={(e) => set("opportunity_description", e.target.value)}
              placeholder='e.g. "Living room carpet looks soaked and stained — owner mentioned they have no one to clean it. Two-story townhouse."'
              rows={4}
              className="mt-1 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">
              Category <span className="text-[#EF4444]">*</span>
            </Label>
            <select
              data-testid="referral-category"
              value={form.service_category}
              onChange={(e) => set("service_category", e.target.value)}
              className="mt-1 h-11 w-full rounded-none border border-[#030712] bg-white px-3 text-sm"
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c] || c}
                </option>
              ))}
            </select>
          </div>

          <div className="border-t border-[#E5E7EB] pt-4">
            <Label className="font-mono-label">
              Contact (optional — helps Mechie reach out)
            </Label>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Input
                data-testid="referral-contact-name"
                value={form.contact_name}
                onChange={(e) => set("contact_name", e.target.value)}
                placeholder="Their name"
                className="h-10 rounded-none border-[#E5E7EB]"
              />
              <Input
                data-testid="referral-contact-phone"
                value={form.contact_phone}
                onChange={(e) => set("contact_phone", e.target.value)}
                placeholder="Phone"
                className="h-10 rounded-none border-[#E5E7EB]"
              />
              <Input
                data-testid="referral-contact-email"
                value={form.contact_email}
                onChange={(e) => set("contact_email", e.target.value)}
                placeholder="Email"
                className="h-10 rounded-none border-[#E5E7EB]"
              />
            </div>
          </div>

          {/* Tip box */}
          <div className="flex items-start gap-2 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs text-[#4B5563]">
            <Camera size={14} weight="fill" className="mt-0.5 shrink-0" />
            <span>
              For commercial leads, drop photos in the description for now —
              file upload is coming next. Better photos = faster, more accurate
              quote = more deals closing = more commission to you.
            </span>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[#E5E7EB] bg-white p-4">
          <Button
            variant="outline"
            onClick={onClose}
            data-testid="cancel-submit"
            className="rounded-none border-[#030712]"
          >
            Cancel
          </Button>
          <Button
            data-testid="confirm-submit-referral"
            onClick={submit}
            disabled={submitting}
            className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            {submitting ? (
              "Submitting…"
            ) : (
              <>
                <CaretRight size={14} className="mr-1" /> Submit referral
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

function timeAgo(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  return `${d}d ago`;
}
