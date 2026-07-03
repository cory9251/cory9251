import React, { useState } from "react";
import axios from "axios";
import { BACKEND_URL } from "@/lib/api";
import {
  Phone,
  PaperPlaneTilt,
  CheckCircle,
  ShieldCheck,
} from "@phosphor-icons/react";

const SERVICES = [
  "Residential Cleaning",
  "Commercial & Office Cleaning",
  "Move-Out Cleaning",
  "Apartment Turnovers",
  "Junk Removal",
  "Estate Cleanouts",
  "Pressure Washing",
  "Carpet Cleaning",
  "Landscaping & Yard Cleanup",
  "Handyman Services",
  "Painting",
  "Property Maintenance",
  "Specialty Property Services",
  "Other (I'll explain in notes)",
];

const TIMELINES = [
  { v: "ASAP / same week", urgent: true },
  { v: "Within 2 weeks" },
  { v: "This month" },
  { v: "Next month or later" },
  { v: "Flexible — best price" },
];

const PHONE_HREF = "tel:+14108709347";
const PHONE_DISPLAY = "(410) 870-9347";

export default function QuoteRequestForm() {
  const apiBase = BACKEND_URL;
  const [f, setF] = useState({
    name: "",
    phone: "",
    email: "",
    services: [], // multi-select
    timeline: "",
    address: "",
    message: "",
    website: "", // honeypot
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null); // { name } on success

  const update = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  const toggleService = (label) => {
    setF((s) => {
      const has = s.services.includes(label);
      return {
        ...s,
        services: has
          ? s.services.filter((x) => x !== label)
          : [...s.services, label],
      };
    });
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.name.trim() || f.name.trim().length < 2) {
      setError("Please enter your name.");
      return;
    }
    if (!f.phone.trim() || f.phone.replace(/\D/g, "").length < 7) {
      setError("Please enter a valid phone number we can reach you at.");
      return;
    }
    if (!f.services.length) {
      setError("Pick at least one service you need.");
      return;
    }
    if (!f.timeline) {
      setError("Let us know how soon you need this.");
      return;
    }
    setSubmitting(true);
    try {
      // Backend keeps a single `service` string — join the selections so the
      // admin inbox + lead email read naturally.
      const { services, ...rest } = f;
      const payload = { ...rest, service: services.join(" · ") };
      await axios.post(`${apiBase}/api/public/quote-requests`, payload);
      setDone({ name: f.name.trim().split(/\s+/)[0] });
    } catch (err) {
      const msg =
        err?.response?.data?.detail?.[0]?.msg ||
        err?.response?.data?.detail ||
        err?.message ||
        "Something went wrong. Please call us.";
      setError(typeof msg === "string" ? msg : "Something went wrong. Please call us.");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div
        data-testid="quote-form-success"
        className="border border-[#030712] bg-white p-6 md:p-8 gb-tactile"
      >
        <div className="flex items-center gap-2">
          <CheckCircle size={22} weight="fill" className="text-[#22C55E]" />
          <div className="font-mono-label text-[10px] text-[#22C55E]">
            Request received
          </div>
        </div>
        <h3 className="mt-3 font-display text-2xl sm:text-3xl font-black tracking-tight">
          Thanks, {done.name}. We&apos;re on it.
        </h3>
        <p className="mt-3 text-sm text-[#4B5563]">
          We just texted the HCOB team your request. Someone will text or call
          you back shortly. For anything urgent, ring us directly.
        </p>
        <a
          href={PHONE_HREF}
          className="mt-5 inline-flex items-center gap-2 bg-[#030712] px-5 py-3 text-sm font-bold text-white hover:bg-[#1f2937]"
        >
          <Phone size={14} weight="fill" /> Call {PHONE_DISPLAY}
        </a>
      </div>
    );
  }

  return (
    <form
      onSubmit={submit}
      data-testid="quote-form"
      className="border border-[#030712] bg-white p-5 sm:p-6 md:p-7 gb-tactile"
      noValidate
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="font-mono-label text-[10px] text-[#0044FF]">
            Request a quote
          </div>
          <h3 className="mt-1 font-display text-2xl sm:text-3xl font-black tracking-tight leading-tight">
            Tell us about your project.
          </h3>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-[#4B5563]">
          <ShieldCheck size={12} weight="fill" className="text-[#0044FF]" />
          We never share your info.
        </div>
      </div>
      <p className="mt-2 text-xs sm:text-sm text-[#4B5563]">
        We&apos;ll text or call you back. For urgent needs, dial{" "}
        <a className="font-bold text-[#030712]" href={PHONE_HREF}>
          {PHONE_DISPLAY}
        </a>
        .
      </p>

      {/* Honeypot — visually hidden, screen-reader hidden, no tab stop. */}
      <div
        aria-hidden="true"
        style={{ position: "absolute", left: "-10000px", top: "auto" }}
      >
        <label>
          Don&apos;t fill this in
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={f.website}
            onChange={update("website")}
          />
        </label>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Your name" required>
          <input
            data-testid="quote-input-name"
            value={f.name}
            onChange={update("name")}
            placeholder="Jane Smith"
            className="quote-input"
            autoComplete="name"
            required
          />
        </Field>
        <Field label="Phone" required>
          <input
            data-testid="quote-input-phone"
            type="tel"
            inputMode="tel"
            value={f.phone}
            onChange={update("phone")}
            placeholder="(443) 555-1234"
            className="quote-input"
            autoComplete="tel"
            required
          />
        </Field>
        <Field label="Email (optional)" full>
          <input
            data-testid="quote-input-email"
            type="email"
            value={f.email}
            onChange={update("email")}
            placeholder="jane@example.com"
            className="quote-input"
            autoComplete="email"
          />
        </Field>
        <Field
          label={`What do you need?${
            f.services.length ? ` · ${f.services.length} selected` : ""
          }`}
          required
          full
        >
          <div
            role="group"
            aria-label="Services needed"
            data-testid="quote-services-grid"
            className="grid grid-cols-1 gap-1.5 sm:grid-cols-2"
          >
            {SERVICES.map((s) => {
              const checked = f.services.includes(s);
              return (
                <label
                  key={s}
                  data-testid={`quote-service-option-${s.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 30)}`}
                  className={`flex cursor-pointer items-start gap-2.5 border px-3 py-2.5 text-sm transition-colors ${
                    checked
                      ? "border-[#030712] bg-[#030712] text-white"
                      : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleService(s)}
                    className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-[#0044FF]"
                    aria-label={s}
                  />
                  <span className="leading-snug">{s}</span>
                </label>
              );
            })}
          </div>
          {f.services.length > 0 && (
            <button
              type="button"
              data-testid="quote-services-clear"
              onClick={() => setF((s) => ({ ...s, services: [] }))}
              className="mt-2 inline-flex items-center text-[11px] font-semibold text-[#4B5563] hover:text-[#EF4444]"
            >
              Clear all
            </button>
          )}
        </Field>
        <Field label="How soon?" required full>
          <div className="flex flex-wrap gap-2">
            {TIMELINES.map((t) => (
              <button
                key={t.v}
                type="button"
                data-testid={`quote-timeline-${t.v.toLowerCase().replace(/\s+/g, "-").slice(0, 24)}`}
                onClick={() => setF((s) => ({ ...s, timeline: t.v }))}
                className={`border px-3 py-2 text-xs font-semibold transition-colors ${
                  f.timeline === t.v
                    ? "border-[#030712] bg-[#030712] text-white"
                    : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
                }`}
              >
                {t.urgent && f.timeline !== t.v ? (
                  <span className="mr-1 text-[#EF4444]">●</span>
                ) : null}
                {t.v}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Property address (optional)" full>
          <input
            data-testid="quote-input-address"
            value={f.address}
            onChange={update("address")}
            placeholder="123 Main St, Baltimore, MD 21201"
            className="quote-input"
            autoComplete="street-address"
          />
        </Field>
        <Field label="Anything else? (square footage, units, frequency…)" full>
          <textarea
            data-testid="quote-input-message"
            value={f.message}
            onChange={update("message")}
            placeholder="2BR apartment, need by Saturday. Roughly 900 sqft."
            rows={3}
            className="quote-input resize-y"
          />
        </Field>
      </div>

      {error && (
        <div
          data-testid="quote-form-error"
          className="mt-4 border border-[#EF4444] bg-[#FEF2F2] px-3 py-2 text-xs font-semibold text-[#EF4444]"
        >
          {error}
        </div>
      )}

      <div className="mt-5 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <a
          href={PHONE_HREF}
          className="inline-flex items-center justify-center gap-2 text-xs font-semibold text-[#4B5563] hover:text-[#030712]"
        >
          <Phone size={12} weight="fill" /> Prefer a call? {PHONE_DISPLAY}
        </a>
        <button
          type="submit"
          data-testid="quote-form-submit"
          disabled={submitting}
          className="inline-flex h-12 items-center justify-center gap-2 bg-[#0044FF] px-6 text-sm font-bold text-white hover:bg-[#0036cc] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? (
            "Sending…"
          ) : (
            <>
              <PaperPlaneTilt size={14} weight="fill" /> Send request
            </>
          )}
        </button>
      </div>

      <style>{`
        .quote-input {
          width: 100%;
          background: white;
          border: 1px solid #E5E7EB;
          padding: 12px 12px;
          font-size: 14px;
          color: #030712;
          outline: none;
          border-radius: 0;
          transition: border-color 0.15s ease;
        }
        .quote-input:focus { border-color: #030712; }
        .quote-input::placeholder { color: #9CA3AF; }
      `}</style>
    </form>
  );
}

function Field({ label, children, required, full }) {
  return (
    <label className={`flex flex-col gap-1 ${full ? "sm:col-span-2" : ""}`}>
      <span className="font-mono-label text-[10px] text-[#4B5563]">
        {label}
        {required && <span className="text-[#EF4444]"> *</span>}
      </span>
      {children}
    </label>
  );
}
