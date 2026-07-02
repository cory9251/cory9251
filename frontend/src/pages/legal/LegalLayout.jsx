import React from "react";
import { Link } from "react-router-dom";
import { Lightning, ArrowLeft } from "@phosphor-icons/react";

/**
 * Shared layout for public legal pages (Privacy Policy, Terms, SMS Terms).
 *
 * Design goals:
 * - Clean, printable, brand-consistent with the rest of HCOB Network
 * - Anchor-able section headings so Twilio/regulators can deep-link
 * - Cross-links between all three legal docs at top and bottom
 */
export default function LegalLayout({ title, effectiveDate, testId, children }) {
  return (
    <div
      className="min-h-screen bg-white text-[#030712]"
      data-testid={testId || "legal-page"}
    >
      {/* Top bar */}
      <header className="border-b border-[#E5E7EB]">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link
            to="/"
            className="flex items-center gap-2 hover:opacity-80"
            data-testid="legal-home-link"
          >
            <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={18} />
            </div>
            <div>
              <div className="font-display text-base font-black leading-none">
                HCOB Network
              </div>
              <div className="font-mono-label text-[10px]">
                hcobnetwork.com
              </div>
            </div>
          </Link>
          <Link
            to="/"
            className="flex items-center gap-1 text-xs text-[#4B5563] hover:text-[#030712]"
            data-testid="legal-back-link"
          >
            <ArrowLeft size={14} /> Back to site
          </Link>
        </div>
      </header>

      {/* Cross-link nav */}
      <div className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
        <div className="mx-auto flex max-w-4xl flex-wrap gap-x-6 gap-y-2 px-6 py-3 text-xs font-mono-label">
          <LegalNavLink to="/privacy" label="Privacy Policy" testId="legal-nav-privacy" />
          <LegalNavLink to="/terms" label="Terms & Conditions" testId="legal-nav-terms" />
          <LegalNavLink to="/sms-terms" label="SMS Messaging Terms" testId="legal-nav-sms" />
        </div>
      </div>

      {/* Content */}
      <main className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="font-display text-4xl font-black leading-tight sm:text-5xl">
          {title}
        </h1>
        {effectiveDate && (
          <div className="mt-3 font-mono-label text-xs text-[#4B5563]">
            Effective Date: {effectiveDate}
          </div>
        )}
        <div className="mt-10 space-y-8 text-[15px] leading-relaxed text-[#1F2937]">
          {children}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#E5E7EB] px-6 py-8 text-xs text-[#4B5563]">
        <div className="mx-auto flex max-w-4xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="font-mono-label">
            © HCOB Network / Home Cleaners of Baltimore
          </div>
          <div className="flex flex-wrap gap-4">
            <Link to="/privacy" className="hover:text-[#030712]">
              Privacy Policy
            </Link>
            <Link to="/terms" className="hover:text-[#030712]">
              Terms & Conditions
            </Link>
            <Link to="/sms-terms" className="hover:text-[#030712]">
              SMS Messaging Terms
            </Link>
            <a
              href="https://hcobcleaners.com"
              target="_blank"
              rel="noreferrer"
              className="hover:text-[#030712]"
            >
              hcobcleaners.com
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function LegalNavLink({ to, label, testId }) {
  return (
    <Link
      to={to}
      className="text-[#4B5563] hover:text-[#0044FF]"
      data-testid={testId}
    >
      {label}
    </Link>
  );
}

/**
 * Small section heading used inside legal pages.
 * Renders as an anchor-able h2 so Twilio/regulators can deep-link.
 */
export function LegalSection({ id, title, children }) {
  return (
    <section id={id} data-testid={id ? `legal-section-${id}` : undefined}>
      <h2 className="mb-3 font-display text-xl font-black text-[#030712]">
        {title}
      </h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
