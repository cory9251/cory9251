import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  PaperPlaneTilt,
  ArrowRight,
  ArrowLeft,
  CheckCircle,
  Warning,
  Users,
  EnvelopeSimple,
  ChatText,
  Sparkle,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import RichEmailEditor from "@/components/admin/RichEmailEditor";

const SKILL_OPTIONS = [
  { value: "deep_cleaning", label: "Deep cleaning" },
  { value: "routine_cleaning", label: "Routine cleaning" },
  { value: "moveouts", label: "Move-outs" },
  { value: "detailing", label: "Detailing" },
  { value: "window_cleaning", label: "Window cleaning" },
  { value: "carpet_cleaning", label: "Carpet cleaning" },
  { value: "post_construction", label: "Post-construction" },
  { value: "hourly_labor", label: "Hourly labor" },
  { value: "heavy_lifting", label: "Heavy lifting" },
  { value: "forklift", label: "Forklift" },
  { value: "moving", label: "Moving" },
  { value: "warehouse", label: "Warehouse" },
  { value: "landscaping", label: "Landscaping" },
  { value: "painting", label: "Painting" },
  { value: "driving", label: "Driving" },
  { value: "delivery", label: "Delivery" },
  { value: "cdl", label: "CDL" },
  { value: "fast_learner", label: "Fast learner" },
  { value: "bilingual", label: "Bilingual" },
  { value: "team_lead", label: "Team lead" },
];

const AVAIL_OPTIONS = [
  { value: "weekdays", label: "Weekdays" },
  { value: "weekends", label: "Weekends" },
  { value: "mornings", label: "Mornings" },
  { value: "evenings", label: "Evenings" },
  { value: "overnight", label: "Overnight" },
  { value: "full_time", label: "Full-time" },
];

const EMPTY_AUDIENCE = {
  status: "approved",
  skills: [],
  availability: [],
  zip_code: "",
  zip_prefix: "",
  vehicle: "",
  profile_complete: "",
  min_rating: "",
  available_now: false,
  payout_status: "",
  id_status: "",
  search: "",
};

export default function AdminEmailBlast() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [audience, setAudience] = useState(() => {
    // Allow deep-linking from the dashboard strip
    const presetPayout = params.get("payout_status");
    const presetId = params.get("id_status");
    return {
      ...EMPTY_AUDIENCE,
      payout_status: presetPayout || "",
      id_status: presetId || "",
    };
  });
  const [templates, setTemplates] = useState([]);
  const [templateKey, setTemplateKey] = useState("payout_request");
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [ctaLabel, setCtaLabel] = useState("");
  const [ctaPath, setCtaPath] = useState("/crew/me");
  const [previewCount, setPreviewCount] = useState(null);
  const [smsCount, setSmsCount] = useState(null);
  const [previewRows, setPreviewRows] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [bypassCooldown, setBypassCooldown] = useState(false);
  // Multi-channel state (default = email only, matches back-compat backend)
  const [channels, setChannels] = useState(["email"]);
  const [smsBody, setSmsBody] = useState("");

  // Load templates and apply the default one
  useEffect(() => {
    api.get("/admin/email-templates").then((r) => {
      setTemplates(r.data?.templates || []);
      const first = (r.data?.templates || []).find((t) => t.key === "payout_request");
      if (first) applyTemplate(first);
    });
  }, []);

  const applyTemplate = (t) => {
    setTemplateKey(t.key);
    setSubject(t.subject || "");
    setBodyHtml(t.body_html || "");
    setCtaLabel(t.cta_label || "");
    setCtaPath(t.cta_path || "/crew/me");
    // SMS body — only overwrite when the template has one AND the user's
    // current sms_body is empty or was pulled from a previous template
    // (i.e. don't clobber a custom text they've already typed unless they
    // click "Custom" which explicitly wipes fields).
    if (t.key === "custom") {
      setSmsBody("");
    } else if (typeof t.sms_body === "string") {
      setSmsBody(t.sms_body);
    }
  };

  // Live preview — fires whenever audience filter changes (debounced)
  const audienceQuery = useMemo(
    () => ({
      ...audience,
      skills: audience.skills.join(",") || undefined,
      availability: audience.availability.join(",") || undefined,
      profile_complete:
        audience.profile_complete === "yes"
          ? true
          : audience.profile_complete === "no"
          ? false
          : undefined,
      min_rating: audience.min_rating ? Number(audience.min_rating) : undefined,
      available_now: audience.available_now || undefined,
      zip_code: audience.zip_code || undefined,
      zip_prefix: audience.zip_prefix || undefined,
      vehicle: audience.vehicle || undefined,
      payout_status: audience.payout_status || undefined,
      id_status: audience.id_status || undefined,
      status: audience.status || undefined,
      search: audience.search || undefined,
    }),
    [audience]
  );

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    const handle = setTimeout(async () => {
      try {
        const r = await api.post("/admin/email-blast/preview", {
          audience: audienceQuery,
        });
        if (cancelled) return;
        setPreviewCount(r.data?.count ?? 0);
        setSmsCount(r.data?.sms_count ?? 0);
        setPreviewRows(r.data?.preview || []);
      } catch (e) {
        if (!cancelled) {
          toast.error(e.response?.data?.detail || "Could not load preview");
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [audienceQuery]);

  const toggleArr = (key, val) => {
    setAudience((a) => {
      const cur = a[key] || [];
      return {
        ...a,
        [key]: cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val],
      };
    });
  };

  const sendTest = async () => {
    if (channels.includes("email") && (!subject.trim() || !bodyHtml.trim())) {
      toast.error("Subject and email body required");
      return;
    }
    if (channels.includes("sms") && !smsBody.trim()) {
      toast.error("SMS body required");
      return;
    }
    setSending(true);
    try {
      const r = await api.post("/admin/email-blast/send", {
        audience: audienceQuery,
        subject,
        body_html: bodyHtml,
        cta_label: ctaLabel,
        cta_path: ctaPath,
        template_key: templateKey,
        channels,
        sms_body: smsBody,
        test_only: true,
      });
      const bits = [];
      if (channels.includes("email"))
        bits.push(`email ${r.data?.email?.sent ? "sent" : "skipped"}`);
      if (channels.includes("sms"))
        bits.push(
          r.data?.sms?.skipped
            ? `sms ${r.data.sms.skipped.replace(/_/g, " ")}`
            : `sms ${r.data?.sms?.sent ? "sent" : "not delivered"}`
        );
      toast.success(`Test: ${bits.join(" · ")}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test send failed");
    } finally {
      setSending(false);
    }
  };

  const sendBlast = async () => {
    if (channels.length === 0) {
      toast.error("Pick at least one channel (email or SMS).");
      return;
    }
    const emailRecipients = channels.includes("email") ? (previewCount || 0) : 0;
    const smsRecipients = channels.includes("sms") ? (smsCount || 0) : 0;
    if (emailRecipients === 0 && smsRecipients === 0) {
      toast.error("No recipients match — check filters and channel selection.");
      return;
    }
    const confirmParts = [];
    if (channels.includes("email")) confirmParts.push(`${emailRecipients} email`);
    if (channels.includes("sms")) confirmParts.push(`${smsRecipients} text`);
    const ok = window.confirm(
      `Send blast to ${confirmParts.join(" + ")} recipient${
        emailRecipients + smsRecipients === 1 ? "" : "s"
      } now? This cannot be undone.`
    );
    if (!ok) return;
    setSending(true);
    try {
      const r = await api.post("/admin/email-blast/send", {
        audience: audienceQuery,
        subject,
        body_html: bodyHtml,
        cta_label: ctaLabel,
        cta_path: ctaPath,
        template_key: templateKey,
        channels,
        sms_body: smsBody,
        test_only: false,
        bypass_cooldown: bypassCooldown,
      });
      const em = r.data?.email || {};
      const sm = r.data?.sms || {};
      const summary = [];
      if (channels.includes("email"))
        summary.push(
          `${em.sent || 0} email` +
            (em.skipped_cooldown ? ` · ${em.skipped_cooldown} cooldown` : "") +
            (em.failed ? ` · ${em.failed} failed` : "")
        );
      if (channels.includes("sms"))
        summary.push(
          `${sm.sent || 0} SMS` +
            (sm.skipped_consent ? ` · ${sm.skipped_consent} no consent` : "") +
            (sm.skipped_cooldown ? ` · ${sm.skipped_cooldown} cooldown` : "") +
            (sm.failed ? ` · ${sm.failed} failed` : "")
        );
      toast.success(`Blast sent — ${summary.join(" ; ")}`);
      setStep(1);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Blast failed");
    } finally {
      setSending(false);
    }
  };

  // Apply page title
  useEffect(() => {
    const prev = document.title;
    document.title = "Blast — HCOB Ops";
    return () => {
      document.title = prev;
    };
  }, []);

  return (
    <div className="min-h-screen bg-white" data-testid="admin-email-blast-page">

      {/* Header */}
      <div className="border-b border-[#030712] bg-white px-6 py-6 md:px-10">
        <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          Operations
        </div>
        <div className="mt-1 flex items-center gap-3">
          <PaperPlaneTilt size={28} weight="fill" />
          <h1 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
            Blast
          </h1>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Send an email, a text, or both to any slice of your workforce. Pick a
          template, edit the copy, preview the audience, send a test, then ship it.
        </p>
        <StepBar step={step} setStep={setStep} />
      </div>

      <div className="px-6 py-8 md:px-10">
        {step === 1 && (
          <AudienceStep
            audience={audience}
            setAudience={setAudience}
            toggleArr={toggleArr}
            previewCount={previewCount}
            smsCount={smsCount}
            channels={channels}
            previewRows={previewRows}
            previewLoading={previewLoading}
          />
        )}

        {step === 2 && (
          <ComposeStep
            templates={templates}
            templateKey={templateKey}
            applyTemplate={(t) => applyTemplate(t)}
            subject={subject}
            setSubject={setSubject}
            bodyHtml={bodyHtml}
            setBodyHtml={setBodyHtml}
            ctaLabel={ctaLabel}
            setCtaLabel={setCtaLabel}
            ctaPath={ctaPath}
            setCtaPath={setCtaPath}
            channels={channels}
            setChannels={setChannels}
            smsBody={smsBody}
            setSmsBody={setSmsBody}
          />
        )}

        {step === 3 && (
          <ConfirmStep
            previewCount={previewCount}
            smsCount={smsCount}
            channels={channels}
            smsBody={smsBody}
            previewRows={previewRows}
            subject={subject}
            bodyHtml={bodyHtml}
            ctaLabel={ctaLabel}
            ctaPath={ctaPath}
            sendTest={sendTest}
            sendBlast={sendBlast}
            sending={sending}
            bypassCooldown={bypassCooldown}
            setBypassCooldown={setBypassCooldown}
          />
        )}

        {/* Footer nav */}
        <div className="mt-8 flex items-center justify-between border-t border-[#E5E7EB] pt-4">
          <Button
            variant="outline"
            disabled={step === 1}
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            data-testid="email-blast-back-btn"
            className="rounded-none border-[#030712]"
          >
            <ArrowLeft size={14} className="mr-2" /> Back
          </Button>
          {step < 3 ? (
            <Button
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 1 && !previewCount}
              data-testid="email-blast-next-btn"
              className="rounded-none bg-[#030712] text-white hover:bg-[#1F2937]"
            >
              Next <ArrowRight size={14} className="ml-2" />
            </Button>
          ) : (
            <Button
              onClick={sendBlast}
              disabled={sending || channels.length === 0 || (
                (channels.includes("email") ? (previewCount || 0) : 0) +
                (channels.includes("sms") ? (smsCount || 0) : 0)
              ) === 0}
              data-testid="email-blast-send-btn"
              className="rounded-none bg-[#10B981] text-white hover:bg-[#059669]"
            >
              <PaperPlaneTilt size={14} className="mr-2" />
              {sending ? "Sending..." : `Send${(() => {
                const em = channels.includes("email") ? (previewCount || 0) : 0;
                const sm = channels.includes("sms") ? (smsCount || 0) : 0;
                const parts = [];
                if (channels.includes("email")) parts.push(`${em} email`);
                if (channels.includes("sms")) parts.push(`${sm} SMS`);
                return parts.length ? ` — ${parts.join(" + ")}` : "";
              })()}`}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function StepBar({ step, setStep }) {
  const steps = [
    { n: 1, label: "Audience", icon: Users },
    { n: 2, label: "Compose", icon: EnvelopeSimple },
    { n: 3, label: "Review & send", icon: PaperPlaneTilt },
  ];
  return (
    <div className="mt-6 flex items-center gap-3">
      {steps.map((s, i) => {
        const Icon = s.icon;
        const active = step === s.n;
        const done = step > s.n;
        return (
          <React.Fragment key={s.n}>
            <button
              type="button"
              onClick={() => (done ? setStep(s.n) : null)}
              data-testid={`email-blast-step-${s.n}`}
              className={`inline-flex items-center gap-2 border px-3 py-2 text-[11px] font-bold uppercase tracking-widest transition-colors ${
                active
                  ? "border-[#030712] bg-[#030712] text-white"
                  : done
                  ? "border-[#10B981] text-[#10B981] hover:bg-[#10B981]/10"
                  : "border-[#E5E7EB] text-[#9CA3AF]"
              }`}
            >
              <Icon size={12} weight="fill" /> {s.n}. {s.label}
            </button>
            {i < steps.length - 1 && (
              <div className="h-px w-6 bg-[#E5E7EB]" />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// GSM-7 vs UCS-2 SMS segment counter. Emojis or non-Latin characters flip
// the encoding to UCS-2 (70-char segments) — we can't reliably detect that
// per-char without a full table, so we do a fast heuristic: if the body
// contains any code point outside basic Latin+extras, we assume UCS-2.
function smsSegments(body) {
  const len = (body || "").length;
  if (len === 0) return { len: 0, segments: 0, encoding: "GSM-7", perSegment: 160 };
  const isUnicode = /[^\u0000-\u007E]/.test(body || "");
  const perSegment = isUnicode ? 67 : 153;
  const singleMax = isUnicode ? 70 : 160;
  const segments = len <= singleMax ? 1 : Math.ceil(len / perSegment);
  return { len, segments, encoding: isUnicode ? "UCS-2" : "GSM-7", perSegment: singleMax };
}

function AudienceStep({
  audience,
  setAudience,
  toggleArr,
  previewCount,
  smsCount,
  channels,
  previewRows,
  previewLoading,
}) {
  const set = (k, v) => setAudience((a) => ({ ...a, [k]: v }));
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <Section title="Status">
          <div className="flex flex-wrap gap-2">
            {[
              ["", "All"],
              ["approved", "Approved (active)"],
              ["pending", "Pending review"],
              ["rejected", "Rejected"],
              ["suspended", "Suspended"],
            ].map(([v, l]) => (
              <Pill
                key={v || "all"}
                active={audience.status === v}
                onClick={() => set("status", v)}
                testid={`audience-status-${v || "all"}`}
              >
                {l}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Payout method">
          <div className="flex flex-wrap gap-2">
            {[
              ["", "Any"],
              ["missing", "Missing payout"],
              ["set", "Has payout"],
            ].map(([v, l]) => (
              <Pill
                key={v || "any"}
                active={audience.payout_status === v}
                onClick={() => set("payout_status", v)}
                testid={`audience-payout-${v || "any"}`}
              >
                {l}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="ID verification">
          <div className="flex flex-wrap gap-2">
            {[
              ["", "Any"],
              ["missing", "Missing ID"],
              ["submitted", "Submitted, not verified"],
              ["verified", "Verified"],
            ].map(([v, l]) => (
              <Pill
                key={v || "any"}
                active={audience.id_status === v}
                onClick={() => set("id_status", v)}
                testid={`audience-id-${v || "any"}`}
              >
                {l}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Profile complete">
          <div className="flex flex-wrap gap-2">
            {[
              ["", "Any"],
              ["yes", "Complete"],
              ["no", "Incomplete"],
            ].map(([v, l]) => (
              <Pill
                key={v || "any"}
                active={audience.profile_complete === v}
                onClick={() => set("profile_complete", v)}
                testid={`audience-profile-${v || "any"}`}
              >
                {l}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Skills (any of)">
          <div className="flex flex-wrap gap-2">
            {SKILL_OPTIONS.map((s) => (
              <Pill
                key={s.value}
                active={audience.skills.includes(s.value)}
                onClick={() => toggleArr("skills", s.value)}
                testid={`audience-skill-${s.value}`}
              >
                {s.label}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Availability">
          <div className="flex flex-wrap gap-2">
            {AVAIL_OPTIONS.map((a) => (
              <Pill
                key={a.value}
                active={audience.availability.includes(a.value)}
                onClick={() => toggleArr("availability", a.value)}
                testid={`audience-avail-${a.value}`}
              >
                {a.label}
              </Pill>
            ))}
          </div>
        </Section>

        <Section title="Location & rating">
          <div className="grid grid-cols-2 gap-3">
            <Input
              data-testid="audience-zip-code"
              placeholder="Exact ZIP (5 digits)"
              value={audience.zip_code}
              onChange={(e) => set("zip_code", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
            <Input
              data-testid="audience-zip-prefix"
              placeholder="Zone (ZIP prefix, e.g. 212)"
              value={audience.zip_prefix}
              onChange={(e) => set("zip_prefix", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
            <select
              data-testid="audience-vehicle"
              value={audience.vehicle}
              onChange={(e) => set("vehicle", e.target.value)}
              className="h-10 rounded-none border border-[#030712] bg-white px-3 text-sm"
            >
              <option value="">Any vehicle</option>
              <option value="any">Any vehicle (has one)</option>
              <option value="car">Car</option>
              <option value="truck">Truck</option>
              <option value="cdl">CDL</option>
            </select>
            <select
              data-testid="audience-min-rating"
              value={audience.min_rating}
              onChange={(e) => set("min_rating", e.target.value)}
              className="h-10 rounded-none border border-[#030712] bg-white px-3 text-sm"
            >
              <option value="">Any rating</option>
              <option value="3">3+ ⭐</option>
              <option value="4">4+ ⭐</option>
              <option value="4.5">4.5+ ⭐</option>
            </select>
          </div>
        </Section>

        <Section title="Free-text search (name / email / phone)">
          <Input
            data-testid="audience-search"
            placeholder="e.g. 'maria' or 'baltimore'"
            value={audience.search}
            onChange={(e) => set("search", e.target.value)}
            className="h-10 rounded-none border-[#030712]"
          />
        </Section>
      </div>

      {/* Live preview pane */}
      <div className="sticky top-6 h-fit border border-[#030712] bg-[#F9FAFB] p-5">
        <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          Live audience
        </div>
        <div
          className="mt-1 font-display text-5xl font-bold leading-none"
          data-testid="audience-preview-count"
        >
          {previewLoading ? "..." : previewCount ?? "—"}
        </div>
        <div className="mt-1 text-xs text-[#4B5563]">
          {previewCount === 1 ? "worker matches" : "workers match"}
        </div>

        {/* Per-channel counts. SMS is always gated by opt-in + phone. */}
        <div className="mt-4 grid grid-cols-2 gap-2 border-t border-[#E5E7EB] pt-4">
          <div
            data-testid="audience-email-count"
            className={`border px-3 py-2 ${
              (channels || []).includes("email")
                ? "border-[#0044FF] bg-[#F0F4FF]"
                : "border-[#E5E7EB] bg-white"
            }`}
          >
            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
              <EnvelopeSimple size={11} weight="fill" /> Email
            </div>
            <div className="mt-0.5 font-display text-2xl font-bold leading-none">
              {previewCount ?? "—"}
            </div>
          </div>
          <div
            data-testid="audience-sms-count"
            className={`border px-3 py-2 ${
              (channels || []).includes("sms")
                ? "border-[#10B981] bg-[#ECFDF5]"
                : "border-[#E5E7EB] bg-white"
            }`}
          >
            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#065F46]">
              <ChatText size={11} weight="fill" /> SMS opted in
            </div>
            <div className="mt-0.5 font-display text-2xl font-bold leading-none">
              {smsCount ?? "—"}
            </div>
          </div>
        </div>

        {previewRows.length > 0 && (
          <>
            <div className="mt-5 border-t border-[#E5E7EB] pt-4 text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
              First {previewRows.length}
            </div>
            <ul className="mt-2 space-y-2">
              {previewRows.map((p) => (
                <li
                  key={p.user_id}
                  className="text-xs"
                  data-testid={`audience-preview-row-${p.user_id}`}
                >
                  <div className="font-bold">{p.name}</div>
                  <div className="text-[#4B5563]">{p.email}</div>
                </li>
              ))}
            </ul>
          </>
        )}
        {previewCount === 0 && (
          <div className="mt-4 flex items-start gap-2 border border-[#F59E0B] bg-[#FFFBEB] p-3 text-xs text-[#92400E]">
            <Warning size={14} weight="fill" />
            <span>No workers match these filters. Loosen one or two.</span>
          </div>
        )}
      </div>
    </div>
  );
}

function ComposeStep({
  templates,
  templateKey,
  applyTemplate,
  subject,
  setSubject,
  bodyHtml,
  setBodyHtml,
  ctaLabel,
  setCtaLabel,
  ctaPath,
  setCtaPath,
  channels,
  setChannels,
  smsBody,
  setSmsBody,
}) {
  const toggleChannel = (c) => {
    setChannels((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  };
  const seg = smsSegments(smsBody || "");
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <Section title="Channels">
          <div className="flex flex-wrap gap-2">
            <Pill
              testid="channel-email"
              active={channels.includes("email")}
              onClick={() => toggleChannel("email")}
            >
              <EnvelopeSimple size={12} weight="fill" className="mr-1 inline" />
              Email
            </Pill>
            <Pill
              testid="channel-sms"
              active={channels.includes("sms")}
              onClick={() => toggleChannel("sms")}
            >
              <ChatText size={12} weight="fill" className="mr-1 inline" />
              SMS (text)
            </Pill>
          </div>
          <div className="mt-2 text-[11px] text-[#4B5563]">
            SMS is sent only to workers who have opted in to text updates AND have a phone number on file. &ldquo;Reply STOP to opt out.&rdquo; is appended automatically.
          </div>
        </Section>

        <Section title="Start from a template">
          <div className="flex flex-wrap gap-2">
            {templates.map((t) => (
              <Pill
                key={t.key}
                active={templateKey === t.key}
                onClick={() => applyTemplate(t)}
                testid={`template-${t.key}`}
              >
                {t.title}
              </Pill>
            ))}
          </div>
        </Section>

        {channels.includes("email") && (
          <>
            <Section title="Email subject">
              <Input
                data-testid="email-blast-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject line shown in their inbox"
                className="h-12 rounded-none border-[#030712] text-base"
              />
            </Section>

            <Section title="Email body">
              <RichEmailEditor
                value={bodyHtml}
                onChange={setBodyHtml}
                placeholder="Write your message. Use the toolbar for bold, lists, links."
                testid="email-blast-body"
              />
              <div className="mt-2 flex items-start gap-2 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs">
                <Sparkle size={14} weight="fill" />
                <div>
                  <div className="font-bold">Merge tags</div>
                  <div className="text-[#4B5563]">
                    Type these literally — they swap in per recipient:{" "}
                    <code className="bg-white px-1">{"{{first_name}}"}</code> ·{" "}
                    <code className="bg-white px-1">{"{{name}}"}</code> ·{" "}
                    <code className="bg-white px-1">{"{{email}}"}</code>
                  </div>
                </div>
              </div>
            </Section>

            <Section title="Call-to-action button (optional, email only)">
              <div className="grid grid-cols-2 gap-3">
                <Input
                  data-testid="email-blast-cta-label"
                  value={ctaLabel}
                  onChange={(e) => setCtaLabel(e.target.value)}
                  placeholder='Button text (e.g. "Add my payment")'
                  className="h-10 rounded-none border-[#030712]"
                />
                <Input
                  data-testid="email-blast-cta-path"
                  value={ctaPath}
                  onChange={(e) => setCtaPath(e.target.value)}
                  placeholder='Path (e.g. "/crew/me")'
                  className="h-10 rounded-none border-[#030712]"
                />
              </div>
              <div className="mt-1 text-[10px] tracking-widest text-[#4B5563]">
                Leave blank to send a plain-text email with no button.
              </div>
            </Section>
          </>
        )}

        {channels.includes("sms") && (
          <Section title="Text message body">
            <Textarea
              data-testid="sms-blast-body"
              value={smsBody}
              onChange={(e) => setSmsBody(e.target.value)}
              rows={4}
              placeholder="Hey {{first_name}}, new gig just dropped in your area. Open the app to claim →"
              className="rounded-none border-[#030712]"
              maxLength={1400}
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-[11px]">
              <div className="text-[#4B5563]">
                Merge tags:{" "}
                <code className="bg-[#F9FAFB] px-1">{"{{first_name}}"}</code>{" · "}
                <code className="bg-[#F9FAFB] px-1">{"{{name}}"}</code>
              </div>
              <div
                data-testid="sms-blast-counter"
                className="font-mono-label"
              >
                {seg.len} chars · {seg.segments} segment{seg.segments === 1 ? "" : "s"} ({seg.encoding})
              </div>
            </div>
            <div className="mt-2 text-[11px] text-[#92400E]">
              Each segment past the first is billed separately. Keep it under {seg.perSegment} for a single-segment text.
            </div>
          </Section>
        )}
      </div>

      {/* Live preview */}
      <div className="sticky top-6 h-fit space-y-4">
        {channels.includes("email") && (
          <div className="border border-[#030712] bg-white p-5">
            <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
              Email preview (sample recipient: &quot;Alex Smith&quot;)
            </div>
            <div className="mt-3 border border-[#E5E7EB] bg-[#F9FAFB] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
                Subject
              </div>
              <div className="mb-3 font-display text-base font-bold">
                {renderPreview(subject) || <span className="text-[#9CA3AF]">(empty)</span>}
              </div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
                Body
              </div>
              <div
                className="email-preview-html mt-1 max-w-none"
                dangerouslySetInnerHTML={{
                  __html:
                    renderPreview(bodyHtml) ||
                    '<span style="color:#9CA3AF">(empty)</span>',
                }}
              />
              {ctaLabel && ctaPath && (
                <div className="mt-3">
                  <div className="inline-block bg-[#030712] px-5 py-2 text-xs font-bold uppercase tracking-widest text-white">
                    {ctaLabel} →
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        {channels.includes("sms") && (
          <div className="border border-[#10B981] bg-white p-5">
            <div className="font-mono-label text-[10px] tracking-widest text-[#065F46]">
              SMS preview
            </div>
            <div className="mt-3 max-w-[280px] rounded-2xl rounded-bl-sm bg-[#ECFDF5] p-3 text-sm text-[#065F46]">
              {renderPreview(smsBody) || <span className="text-[#9CA3AF]">(empty)</span>}
              {smsBody?.trim() && (
                <div className="mt-2 text-[10px] text-[#065F46]/70">
                  Reply STOP to opt out.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ConfirmStep({
  previewCount,
  smsCount,
  channels,
  smsBody,
  previewRows,
  subject,
  bodyHtml,
  ctaLabel,
  ctaPath,
  sendTest,
  sendBlast,
  sending,
  bypassCooldown,
  setBypassCooldown,
}) {
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        {channels.includes("email") && (
          <Section title="Final email">
            <div className="border border-[#030712] bg-white p-5">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
                Subject
              </div>
              <div className="mb-3 font-display text-base font-bold">
                {renderPreview(subject)}
              </div>
              <div
                className="email-preview-html max-w-none"
                dangerouslySetInnerHTML={{ __html: renderPreview(bodyHtml) }}
              />
              {ctaLabel && (
                <div className="mt-4">
                  <div className="inline-block bg-[#030712] px-5 py-2 text-xs font-bold uppercase tracking-widest text-white">
                    {ctaLabel} →
                  </div>
                  <div className="mt-1 text-[10px] tracking-widest text-[#4B5563]">
                    Links to: {ctaPath}
                  </div>
                </div>
              )}
            </div>
          </Section>
        )}

        {channels.includes("sms") && (
          <Section title="Final text message">
            <div className="border border-[#10B981] bg-white p-5">
              <div className="max-w-[320px] rounded-2xl rounded-bl-sm bg-[#ECFDF5] p-3 text-sm text-[#065F46]">
                {renderPreview(smsBody)}
                <div className="mt-2 text-[10px] text-[#065F46]/70">
                  Reply STOP to opt out.
                </div>
              </div>
            </div>
          </Section>
        )}

        <Section title="Safety checks">
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              <span>
                3-day per-template cooldown, tracked per channel: workers who
                got this exact template on the same channel in the last 3 days
                will be auto-skipped.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              <span>
                SMS is delivered only to workers who opted in AND have a phone
                on file. &ldquo;Reply STOP to opt out&rdquo; is appended
                automatically for A2P 10DLC compliance.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              <span>Global blast kill-switch (Settings) is respected.</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              <span>You can send a test to yourself before firing the blast.</span>
            </li>
          </ul>
          <label className="mt-4 flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              data-testid="email-blast-bypass-cooldown"
              checked={bypassCooldown}
              onChange={(e) => setBypassCooldown(e.target.checked)}
            />
            Bypass cooldown (only check for emergency reminders)
          </label>
        </Section>

        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={sendTest}
            disabled={sending}
            data-testid="email-blast-test-btn"
            className="rounded-none border-[#030712]"
          >
            <EnvelopeSimple size={14} className="mr-2" /> Send test to me
          </Button>
        </div>
      </div>

      <div className="sticky top-6 h-fit space-y-3">
        <div className="border border-[#030712] bg-[#F9FAFB] p-5">
          <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
            Recipients
          </div>
          {channels.includes("email") && (
            <div className="mt-2 flex items-baseline justify-between">
              <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-widest text-[#4B5563]">
                <EnvelopeSimple size={11} weight="fill" /> Email
              </span>
              <span
                data-testid="confirm-email-count"
                className="font-display text-3xl font-bold"
              >
                {previewCount ?? 0}
              </span>
            </div>
          )}
          {channels.includes("sms") && (
            <div className="mt-2 flex items-baseline justify-between">
              <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-widest text-[#065F46]">
                <ChatText size={11} weight="fill" /> SMS
              </span>
              <span
                data-testid="confirm-sms-count"
                className="font-display text-3xl font-bold text-[#065F46]"
              >
                {smsCount ?? 0}
              </span>
            </div>
          )}
          {previewRows.length > 0 && (
            <ul className="mt-4 space-y-2 border-t border-[#E5E7EB] pt-4 text-xs">
              {previewRows.map((p) => (
                <li key={p.user_id}>
                  <div className="font-bold">{p.name}</div>
                  <div className="text-[#4B5563]">{p.email}</div>
                </li>
              ))}
              <li className="text-[#9CA3AF]">
                {previewCount > previewRows.length
                  ? `+ ${previewCount - previewRows.length} more`
                  : ""}
              </li>
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
        {title}
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Pill({ active, onClick, children, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={`inline-flex items-center border px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors ${
        active
          ? "border-[#030712] bg-[#030712] text-white"
          : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712] hover:bg-[#F9FAFB]"
      }`}
    >
      {children}
    </button>
  );
}

function renderPreview(t) {
  // Sample render so admins can see what merge tags resolve to in the preview.
  return (t || "")
    .replace(/\{\{first_name\}\}/g, "Alex")
    .replace(/\{\{name\}\}/g, "Alex Smith")
    .replace(/\{\{email\}\}/g, "alex@example.com");
}
