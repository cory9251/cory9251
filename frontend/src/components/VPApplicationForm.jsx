import React, { useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "sonner";
import { CheckCircle, PaperPlaneTilt } from "@phosphor-icons/react";

const COUNTRIES = [
  "United States", "Philippines", "Mexico", "Colombia", "Argentina", "Brazil",
  "Venezuela", "Peru", "Ecuador", "Bolivia", "Chile", "Guatemala", "Honduras",
  "El Salvador", "Nicaragua", "Costa Rica", "Panama", "Dominican Republic",
  "Jamaica", "India", "Pakistan", "Bangladesh", "Nigeria", "Kenya", "Ghana",
  "South Africa", "Egypt", "Canada", "United Kingdom", "Ireland", "Spain",
  "Portugal", "Poland", "Ukraine", "Romania", "Serbia", "Indonesia", "Vietnam",
  "Thailand", "Malaysia", "Australia", "New Zealand", "Other",
];

const STREAM_OPTIONS = [
  { value: "commission_agent", label: "Commission Agent" },
  { value: "gig_work", label: "Virtual Gig Work" },
  { value: "both", label: "Both" },
  { value: "not_sure", label: "Not sure yet" },
];

const SKILL_OPTIONS = [
  { value: "graphic_design", label: "Graphic Design" },
  { value: "web_development", label: "Web Development" },
  { value: "seo", label: "SEO" },
  { value: "social_media", label: "Social Media" },
  { value: "data_entry", label: "Data Entry" },
  { value: "admin_support", label: "Admin Support" },
  { value: "digital_products", label: "Digital Products" },
  { value: "marketing", label: "Marketing" },
  { value: "none_yet", label: "None yet" },
];

const EMPTY = {
  full_name: "",
  email: "",
  phone: "",
  country: "",
  streams: [],
  skills: [],
  portfolio_url: "",
  hours_per_day: "",
  sales_experience: "",
  why_join: "",
  heard_from: "",
  consent: false,
  website: "",
};

function ChipGroup({ options, selected, onToggle, testPrefix }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const active = selected.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            data-testid={`${testPrefix}-${o.value}`}
            onClick={() => onToggle(o.value)}
            className={`border px-3 py-2 text-sm font-semibold transition-colors ${
              active
                ? "border-[#0044FF] bg-[#0044FF] text-white"
                : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export const VPApplicationForm = () => {
  const [form, setForm] = useState(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const tz = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {
      return "";
    }
  }, []);
  const src = useMemo(
    () => new URLSearchParams(window.location.search).get("src") || "",
    []
  );

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggle = (k, v) =>
    setForm((f) => ({
      ...f,
      [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v],
    }));

  const hasRealSkill = form.skills.some((s) => s !== "none_yet");

  const submit = async (e) => {
    e.preventDefault();
    if (form.full_name.trim().split(/\s+/).length < 2)
      return toast.error("Please enter your full name (first and last).");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim()))
      return toast.error("Please enter a valid email address.");
    if (!form.phone.trim()) return toast.error("Phone / WhatsApp is required.");
    if (!form.country) return toast.error("Please select your country.");
    if (form.streams.length === 0)
      return toast.error("Select at least one stream that interests you.");
    if (!form.hours_per_day) return toast.error("Select your hours available per day.");
    if (!form.sales_experience) return toast.error("Select your sales or outreach experience.");
    if (!form.why_join.trim()) return toast.error("Tell us why you want to join.");
    if (!form.consent)
      return toast.error("Please check the acknowledgement box to submit.");
    setSubmitting(true);
    try {
      await api.post("/public/vp-applications", {
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        country: form.country,
        timezone: tz || null,
        streams: form.streams,
        skills: form.skills,
        portfolio_url: hasRealSkill ? form.portfolio_url.trim() || null : null,
        hours_per_day: form.hours_per_day,
        sales_experience: form.sales_experience,
        why_join: form.why_join.trim().slice(0, 500),
        heard_from: form.heard_from || null,
        consent: form.consent,
        src: src || null,
        website: form.website,
      });
      setDone(true);
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div
        data-testid="vp-form-confirmation"
        className="border-2 border-[#0044FF] bg-white p-8 text-center"
      >
        <div className="mx-auto grid h-14 w-14 place-items-center bg-[#0044FF] text-white">
          <CheckCircle size={30} weight="fill" />
        </div>
        <h3 className="mt-5 font-display text-2xl font-black">Application received!</h3>
        <p className="mx-auto mt-3 max-w-md text-sm text-[#4B5563] leading-relaxed">
          Our operations team reviews every application personally. If you&apos;re a fit,
          expect to hear from us within a few business days. Keep an eye on your email
          and WhatsApp.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6" data-testid="vp-application-form">
      {/* Honeypot */}
      <input
        type="text"
        name="website"
        value={form.website}
        onChange={(e) => upd("website", e.target.value)}
        className="hidden"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
      />

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div>
          <Label className="font-semibold">Full name *</Label>
          <Input
            data-testid="vp-form-full-name"
            className="mt-1.5 rounded-none"
            value={form.full_name}
            onChange={(e) => upd("full_name", e.target.value)}
            placeholder="First and last name"
          />
        </div>
        <div>
          <Label className="font-semibold">Email *</Label>
          <Input
            data-testid="vp-form-email"
            type="email"
            className="mt-1.5 rounded-none"
            value={form.email}
            onChange={(e) => upd("email", e.target.value)}
            placeholder="you@example.com"
          />
        </div>
        <div>
          <Label className="font-semibold">Phone / WhatsApp *</Label>
          <Input
            data-testid="vp-form-phone"
            className="mt-1.5 rounded-none"
            value={form.phone}
            onChange={(e) => upd("phone", e.target.value)}
            placeholder="Include country code, e.g. +63 917 123 4567"
          />
        </div>
        <div>
          <Label className="font-semibold">Country *</Label>
          <Select value={form.country} onValueChange={(v) => upd("country", v)}>
            <SelectTrigger data-testid="vp-form-country" className="mt-1.5 rounded-none">
              <SelectValue placeholder="Select your country" />
            </SelectTrigger>
            <SelectContent className="max-h-64">
              {COUNTRIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {tz && (
            <div className="mt-1 text-xs text-[#9CA3AF]">
              Time zone detected: {tz}
            </div>
          )}
        </div>
      </div>

      <div>
        <Label className="font-semibold">Which streams interest you? *</Label>
        <div className="mt-2">
          <ChipGroup
            options={STREAM_OPTIONS}
            selected={form.streams}
            onToggle={(v) => toggle("streams", v)}
            testPrefix="vp-form-stream"
          />
        </div>
      </div>

      <div>
        <Label className="font-semibold">Virtual skills you have (optional)</Label>
        <div className="mt-2">
          <ChipGroup
            options={SKILL_OPTIONS}
            selected={form.skills}
            onToggle={(v) => toggle("skills", v)}
            testPrefix="vp-form-skill"
          />
        </div>
      </div>

      {hasRealSkill && (
        <div>
          <Label className="font-semibold">Portfolio or sample link (optional)</Label>
          <Input
            data-testid="vp-form-portfolio"
            className="mt-1.5 rounded-none"
            value={form.portfolio_url}
            onChange={(e) => upd("portfolio_url", e.target.value)}
            placeholder="https://..."
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div>
          <Label className="font-semibold">Hours available per day *</Label>
          <Select value={form.hours_per_day} onValueChange={(v) => upd("hours_per_day", v)}>
            <SelectTrigger data-testid="vp-form-hours" className="mt-1.5 rounded-none">
              <SelectValue placeholder="Select hours" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="4-6">4–6 hours</SelectItem>
              <SelectItem value="6-8">6–8 hours</SelectItem>
              <SelectItem value="8+">8+ hours</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="font-semibold">Sales or outreach experience *</Label>
          <Select
            value={form.sales_experience}
            onValueChange={(v) => upd("sales_experience", v)}
          >
            <SelectTrigger data-testid="vp-form-sales-exp" className="mt-1.5 rounded-none">
              <SelectValue placeholder="Select experience level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="some">Some</SelectItem>
              <SelectItem value="experienced">Experienced</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label className="font-semibold">Why do you want to join? *</Label>
        <Textarea
          data-testid="vp-form-why-join"
          className="mt-1.5 rounded-none"
          rows={4}
          maxLength={500}
          value={form.why_join}
          onChange={(e) => upd("why_join", e.target.value)}
          placeholder="Tell us in your own words (max 500 characters)"
        />
        <div className="mt-1 text-right text-xs text-[#9CA3AF]">
          {form.why_join.length}/500
        </div>
      </div>

      <div>
        <Label className="font-semibold">How did you hear about us? (optional)</Label>
        <Select value={form.heard_from} onValueChange={(v) => upd("heard_from", v)}>
          <SelectTrigger data-testid="vp-form-heard-from" className="mt-1.5 rounded-none">
            <SelectValue placeholder="Select one" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="facebook">Facebook</SelectItem>
            <SelectItem value="linkedin">LinkedIn</SelectItem>
            <SelectItem value="referral">Referral</SelectItem>
            <SelectItem value="job_board">Job board</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <label
        className="flex cursor-pointer items-start gap-3 border border-[#E5E7EB] bg-[#F9FAFB] p-4"
        data-testid="vp-form-consent-row"
      >
        <Checkbox
          data-testid="vp-form-consent"
          checked={form.consent}
          onCheckedChange={(v) => upd("consent", Boolean(v))}
          className="mt-0.5"
        />
        <span className="text-sm text-[#4B5563] leading-relaxed">
          I understand this is a commission and project-based opportunity, not
          salaried employment. *
        </span>
      </label>

      <button
        type="submit"
        disabled={submitting}
        data-testid="vp-form-submit"
        className="inline-flex h-14 w-full items-center justify-center gap-2 bg-[#0044FF] px-6 text-base font-bold text-white hover:bg-[#0036cc] disabled:opacity-60 sm:w-auto"
      >
        <PaperPlaneTilt size={18} weight="fill" />
        {submitting ? "Submitting..." : "Submit My Application"}
      </button>
    </form>
  );
};
