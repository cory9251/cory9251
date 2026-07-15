import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { ChatText, X, CaretRight } from "@phosphor-icons/react";

/**
 * Nudge banner on the worker dashboard prompting non-opted-in workers to
 * turn on SMS updates. Compliant with Twilio A2P 10DLC: the banner CTA
 * itself is the consent event (single tap = express opt-in), we stamp
 * `sms_opt_in_source: "dashboard_nudge"` server-side so the audit log
 * shows exactly where the consent came from.
 *
 * Dismissal writes a 7-day cooldown to localStorage so we don't nag on
 * every load. Workers without a phone number on file get a soft prompt
 * that deep-links to Profile → Basics instead of the opt-in button.
 */
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;
const DISMISS_KEY = "hcob_sms_nudge_dismissed_at";

export default function SmsOptInNudge() {
  const { user, checkAuth } = useAuth();
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(() => {
    const at = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
    return at && Date.now() - at < COOLDOWN_MS;
  });

  // Only worker accounts, and only if they haven't already consented.
  if (!user || user.role !== "worker") return null;
  if (user.sms_opt_in) return null;
  if (hidden) return null;

  const phone = (user.phone || "").trim();

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setHidden(true);
  };

  const optIn = async () => {
    if (!phone) {
      toast.error("Add a phone number to your profile first.");
      return;
    }
    setBusy(true);
    try {
      await api.put("/me/sms-opt-in", {
        opted_in: true,
        source: "dashboard_nudge",
      });
      await checkAuth?.();
      toast.success("You're in — we'll text you about new gigs.");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="sms-opt-in-nudge"
      className="relative mt-4 flex items-start gap-3 rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4 pr-10 text-left"
    >
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#10B981] text-white">
        <ChatText size={20} weight="fill" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-display text-sm font-bold text-[#065F46]">
          Get text alerts when new gigs drop
        </div>
        <div className="mt-0.5 text-xs leading-relaxed text-[#065F46]/85">
          One tap — we&apos;ll text you gig blasts, offers, and shift reminders.
          Msg &amp; data rates may apply. Reply <strong>STOP</strong> anytime.{" "}
          <Link to="/sms-terms" className="underline">Terms</Link>{" · "}
          <Link to="/privacy" className="underline">Privacy</Link>.
        </div>
        <div className="mt-3 flex items-center gap-2">
          {phone ? (
            <button
              type="button"
              data-testid="sms-opt-in-nudge-yes"
              onClick={optIn}
              disabled={busy}
              className="inline-flex h-9 items-center gap-1 rounded-xl bg-[#10B981] px-3 text-xs font-bold uppercase tracking-widest text-white hover:bg-[#059669] disabled:opacity-50"
            >
              Yes, text me <CaretRight size={12} weight="bold" />
            </button>
          ) : (
            <Link
              to="/crew/me"
              data-testid="sms-opt-in-nudge-add-phone"
              className="inline-flex h-9 items-center gap-1 rounded-xl bg-[#10B981] px-3 text-xs font-bold uppercase tracking-widest text-white hover:bg-[#059669]"
            >
              Add phone number <CaretRight size={12} weight="bold" />
            </Link>
          )}
          <button
            type="button"
            data-testid="sms-opt-in-nudge-later"
            onClick={dismiss}
            className="text-xs font-bold uppercase tracking-widest text-[#065F46]/70 hover:text-[#065F46]"
          >
            Not now
          </button>
        </div>
      </div>
      <button
        type="button"
        aria-label="Dismiss text updates nudge"
        data-testid="sms-opt-in-nudge-close"
        onClick={dismiss}
        className="absolute right-2 top-2 grid h-6 w-6 place-items-center text-[#065F46]/50 hover:text-[#065F46]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
