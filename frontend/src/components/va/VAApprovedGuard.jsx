import React from "react";
import { Link } from "react-router-dom";
import { LockKey, ArrowRight, WarningCircle } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";

/**
 * Wraps a VA route element. If the signed-in VA is not yet `approved`, renders
 * a locked-state placeholder instead of the child page. Approved VAs see the
 * children unchanged. Used to defense-in-depth gate routes that pending VAs
 * shouldn't be able to access by typing the URL directly — the sidebar already
 * hides these tabs, but the route must also be gated.
 */
export default function VAApprovedGuard({ children, featureLabel }) {
  const { user } = useAuth();
  const status = user?.va_status || "pending";
  if (status === "approved") return children;

  const isSuspended = status === "suspended";

  return (
    <div className="mx-auto max-w-2xl px-6 py-16" data-testid="va-locked-placeholder">
      <div className="border border-[#E5E7EB] bg-white p-8">
        <div className="mb-6 inline-flex items-center gap-2 border border-amber-200 bg-amber-50 px-3 py-1.5">
          {isSuspended ? (
            <WarningCircle size={16} weight="duotone" className="text-red-700" />
          ) : (
            <LockKey size={16} weight="duotone" className="text-amber-700" />
          )}
          <span className="font-mono-label text-[10px] uppercase tracking-widest text-amber-900">
            {isSuspended ? "Account suspended" : "Locked · pending approval"}
          </span>
        </div>
        <h1 className="font-display text-3xl font-black tracking-tight text-[#030712]">
          {featureLabel || "This feature"} unlocks once you're approved
        </h1>
        <p className="mt-4 text-sm leading-relaxed text-[#4B5563]">
          {isSuspended
            ? "Your VA account is currently suspended. Please contact the Program Manager to reinstate access."
            : "While we review your application, you have access to the Training playbook, the Templates library, the Leaderboard, and your Dashboard. The revenue-generating features will activate the moment your Program Manager approves your account."}
        </p>
        <div className="mt-8 space-y-3">
          <div className="font-mono-label text-[10px] uppercase tracking-widest text-[#4B5563]">
            Make your wait count
          </div>
          <Link
            to="/va/training"
            data-testid="locked-cta-training"
            className="group flex items-center justify-between border border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3 transition-colors hover:bg-[#F0F4FF]"
          >
            <div>
              <div className="text-sm font-semibold text-[#030712]">Read the Training playbook</div>
              <div className="text-xs text-[#4B5563]">The 5 required fields, brand rules, marketing outlets</div>
            </div>
            <ArrowRight size={16} className="text-[#0044FF] transition-transform group-hover:translate-x-1" />
          </Link>
          <Link
            to="/va/templates"
            data-testid="locked-cta-templates"
            className="group flex items-center justify-between border border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3 transition-colors hover:bg-[#F0F4FF]"
          >
            <div>
              <div className="text-sm font-semibold text-[#030712]">Study the 80+ Pitch Templates</div>
              <div className="text-xs text-[#4B5563]">Cold posts, objection handlers, follow-ups for every channel</div>
            </div>
            <ArrowRight size={16} className="text-[#0044FF] transition-transform group-hover:translate-x-1" />
          </Link>
          <Link
            to="/va/leaderboard"
            data-testid="locked-cta-leaderboard"
            className="group flex items-center justify-between border border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3 transition-colors hover:bg-[#F0F4FF]"
          >
            <div>
              <div className="text-sm font-semibold text-[#030712]">See where you'll rank</div>
              <div className="text-xs text-[#4B5563]">Live VA Leaderboard — top performers + their cadence</div>
            </div>
            <ArrowRight size={16} className="text-[#0044FF] transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </div>
    </div>
  );
}
