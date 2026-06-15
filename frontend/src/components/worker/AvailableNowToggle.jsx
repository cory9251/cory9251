import React, { useState, useEffect } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { Lightning, Clock } from "@phosphor-icons/react";
import { format, differenceInMinutes } from "date-fns";

/**
 * Worker-facing toggle: "I'm available right now".
 *
 * When ON:
 *   - Pulses a green banner with a countdown ("Available until 9:30 PM").
 *   - Admins searching for same-day RUSH coverage see the worker in the
 *     `/ops/workers?available_now=true` filter.
 *   - Auto-expires at end-of-day (site TZ).
 *
 * When OFF:
 *   - Single tap brings it back; admin filter hides the worker.
 *
 * Variant `compact` is for use inside the bottom nav / header. Variant
 * `card` is the full call-to-action used on the feed top.
 */
export default function AvailableNowToggle({ variant = "card", className = "" }) {
  const { user, setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  // For the live countdown re-render
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!user?.available_now || !user?.available_until) return;
    const t = setInterval(() => setTick((v) => v + 1), 60_000);
    return () => clearInterval(t);
  }, [user?.available_now, user?.available_until]);

  if (!user || user.role !== "worker") return null;
  // Pending / blocked workers can't claim gigs anyway — hide the toggle.
  const status = user.worker_status || "approved";
  if (status === "pending" || status === "rejected" || status === "suspended") {
    return null;
  }

  const isOn = !!user.available_now;
  const until = user.available_until ? new Date(user.available_until) : null;
  const minsLeft = until ? Math.max(0, differenceInMinutes(until, new Date())) : 0;

  const toggle = async () => {
    setBusy(true);
    try {
      const { data } = await api.put("/me/availability", {
        available: !isOn,
      });
      setUser((u) => ({
        ...(u || {}),
        available_now: !!data.available_now,
        available_until: data.available_until,
      }));
      toast.success(
        data.available_now
          ? "You're available — admins can ping you for same-day gigs"
          : "You're off the radar"
      );
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (variant === "compact") {
    return (
      <button
        type="button"
        data-testid="available-now-toggle-compact"
        onClick={toggle}
        disabled={busy}
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors ${
          isOn
            ? "bg-[#10B981] text-white"
            : "border border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#10B981] hover:text-[#10B981]"
        } ${className}`}
        title={isOn ? "Tap to turn off" : "Tap to broadcast 'I'm available'"}
      >
        <Lightning size={11} weight="fill" />
        {isOn ? "AVAILABLE" : "OFF"}
      </button>
    );
  }

  // Full card variant — used on the worker feed.
  return (
    <button
      type="button"
      data-testid="available-now-toggle"
      data-state={isOn ? "on" : "off"}
      onClick={toggle}
      disabled={busy}
      className={`group relative mt-4 flex w-full items-center gap-3 overflow-hidden rounded-2xl border-2 px-4 py-3 text-left transition-all ${
        isOn
          ? "border-[#10B981] bg-[#ECFDF5] hover:bg-[#D1FAE5]"
          : "border-[#E5E7EB] bg-white hover:border-[#10B981]/40 hover:bg-[#F0FDF4]"
      } ${className}`}
    >
      <div
        className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white transition-transform group-hover:scale-105 ${
          isOn ? "bg-[#10B981]" : "bg-[#9CA3AF]"
        }`}
      >
        <Lightning
          size={20}
          weight="fill"
          className={isOn ? "animate-pulse" : ""}
        />
      </div>
      <div className="min-w-0 flex-1">
        <div
          className={`font-display text-sm font-bold ${
            isOn ? "text-[#065F46]" : "text-[#030712]"
          }`}
        >
          {isOn
            ? "You're available right now"
            : "I'm available now — show me same-day gigs"}
        </div>
        <div
          className={`mt-0.5 flex items-center gap-1 text-[11px] ${
            isOn ? "text-[#065F46]/80" : "text-[#4B5563]"
          }`}
        >
          {isOn && until ? (
            <>
              <Clock size={11} weight="duotone" />
              <span data-testid="available-until">
                Until {format(until, "h:mm a")}
              </span>
              {minsLeft > 0 && minsLeft < 60 && (
                <span className="ml-1 rounded-full bg-[#10B981]/10 px-1.5 text-[9px] font-bold uppercase tracking-widest text-[#065F46]">
                  {minsLeft}m left
                </span>
              )}
            </>
          ) : (
            <span>
              Tap to broadcast — HCOB admins can call you for RUSH coverage.
            </span>
          )}
        </div>
      </div>
      <div
        className={`shrink-0 rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${
          isOn
            ? "bg-[#10B981] text-white"
            : "bg-[#030712] text-white group-hover:bg-[#10B981]"
        }`}
      >
        {isOn ? "ON" : "TAP"}
      </div>
    </button>
  );
}
