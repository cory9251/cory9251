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
  Sparkle,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

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
  const [previewRows, setPreviewRows] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [bypassCooldown, setBypassCooldown] = useState(false);

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
    if (!subject.trim() || !bodyHtml.trim()) {
      toast.error("Subject and body required");
      return;
    }
    setSending(true);
    try {
      await api.post("/admin/email-blast/send", {
        audience: audienceQuery,
        subject,
        body_html: bodyHtml,
        cta_label: ctaLabel,
        cta_path: ctaPath,
        template_key: templateKey,
        test_only: true,
      });
      toast.success("Test email sent — check your inbox");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test send failed");
    } finally {
      setSending(false);
    }
  };

  const sendBlast = async () => {
    if (!previewCount) {
      toast.error("No recipients match these filters");
      return;
    }
    const ok = window.confirm(
      `Send this email to ${previewCount} worker${previewCount === 1 ? "" : "s"} now? This cannot be undone.`
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
        test_only: false,
        bypass_cooldown: bypassCooldown,
      });
      toast.success(
        `Blast sent: ${r.data.sent} delivered${
          r.data.skipped_cooldown ? `, ${r.data.skipped_cooldown} skipped (3-day cooldown)` : ""
        }${r.data.failed ? `, ${r.data.failed} failed` : ""}`
      );
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
    document.title = "Email Blast — HCOB Ops";
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
            Email Blast
          </h1>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Send a mass email to any slice of your workforce. Pick a template,
          edit the copy, preview the audience, send a test, then ship it.
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
          />
        )}

        {step === 3 && (
          <ConfirmStep
            previewCount={previewCount}
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
              disabled={sending || !previewCount}
              data-testid="email-blast-send-btn"
              className="rounded-none bg-[#10B981] text-white hover:bg-[#059669]"
            >
              <PaperPlaneTilt size={14} className="mr-2" />
              {sending ? "Sending..." : `Send to ${previewCount || 0} worker${previewCount === 1 ? "" : "s"}`}
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

function AudienceStep({
  audience,
  setAudience,
  toggleArr,
  previewCount,
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
}) {
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
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

        <Section title="Subject">
          <Input
            data-testid="email-blast-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject line shown in their inbox"
            className="h-12 rounded-none border-[#030712] text-base"
          />
        </Section>

        <Section title="Body (HTML supported)">
          <Textarea
            data-testid="email-blast-body"
            value={bodyHtml}
            onChange={(e) => setBodyHtml(e.target.value)}
            placeholder="Write the email body. Supports basic HTML and merge tags."
            className="min-h-[260px] rounded-none border-[#030712] font-mono text-xs"
          />
          <div className="mt-2 flex items-start gap-2 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs">
            <Sparkle size={14} weight="fill" />
            <div>
              <div className="font-bold">Merge tags</div>
              <div className="text-[#4B5563]">
                <code className="bg-white px-1">{"{{first_name}}"}</code> · <code className="bg-white px-1">{"{{name}}"}</code> ·{" "}
                <code className="bg-white px-1">{"{{email}}"}</code> — substituted per recipient.
              </div>
            </div>
          </div>
        </Section>

        <Section title="Call-to-action button (optional)">
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
      </div>

      {/* Live email preview */}
      <div className="sticky top-6 h-fit border border-[#030712] bg-white p-5">
        <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          Live preview (sample recipient: &quot;Alex Smith&quot;)
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
            className="prose prose-sm mt-1 max-w-none text-sm"
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
    </div>
  );
}

function ConfirmStep({
  previewCount,
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
        <Section title="Final email">
          <div className="border border-[#030712] bg-white p-5">
            <div className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
              Subject
            </div>
            <div className="mb-3 font-display text-base font-bold">
              {renderPreview(subject)}
            </div>
            <div
              className="prose prose-sm max-w-none text-sm"
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

        <Section title="Safety checks">
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              <span>
                3-day per-template cooldown: workers who got this exact template
                in the last 3 days will be auto-skipped.
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

      <div className="sticky top-6 h-fit border border-[#030712] bg-[#F9FAFB] p-5">
        <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          Recipients
        </div>
        <div className="mt-1 font-display text-5xl font-bold leading-none">
          {previewCount ?? 0}
        </div>
        <div className="mt-1 text-xs text-[#4B5563]">
          worker{previewCount === 1 ? "" : "s"} will receive this email
        </div>
        {previewRows.length > 0 && (
          <ul className="mt-5 space-y-2 border-t border-[#E5E7EB] pt-4 text-xs">
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
