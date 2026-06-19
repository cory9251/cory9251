import React, { useEffect, useState } from "react";
import { CurrencyDollar, TrendUp, Flame, Trophy } from "@phosphor-icons/react";

/**
 * Big "money on the screen" header for the VA Dashboard.
 *
 * Props:
 *   - mtdAmount: number (this month's paid commission $ — main hero number)
 *   - pendingAmount: number (commissions in pipeline)
 *   - tier: {
 *       current: {key, label},
 *       next:    {key, label, at_amount} | null,
 *       progress_pct: number 0..100,
 *       amount_needed_to_next: number,
 *       ladder: [{key, label, min}]
 *     }
 */
export default function EarningsTicker({ mtdAmount = 0, pendingAmount = 0, tier }) {
  const [animated, setAnimated] = useState(0);

  // Count-up animation on mount / when mtdAmount changes.
  // ~1.2s ease-out — pleasing tick without dragging the whole page.
  useEffect(() => {
    const target = Number(mtdAmount || 0);
    if (target === 0) {
      setAnimated(0);
      return;
    }
    const start = performance.now();
    const duration = 1200;
    let frame;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setAnimated(Math.round(target * eased * 100) / 100);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [mtdAmount]);

  const currentLabel = tier?.current?.label || "Hustler";
  const nextLabel = tier?.next?.label;
  const pct = Math.max(0, Math.min(100, tier?.progress_pct ?? 0));
  const needed = Number(tier?.amount_needed_to_next || 0);
  const isLegend = !tier?.next;

  return (
    <div
      data-testid="earnings-ticker"
      className="relative mb-8 overflow-hidden border border-[#030712] bg-gradient-to-br from-[#030712] to-[#1F2937] p-6 text-white sm:p-8"
    >
      {/* Decorative grain dots */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.25) 1px, transparent 0)",
          backgroundSize: "16px 16px",
        }}
      />

      <div className="relative flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-end">
        {/* Left — big number */}
        <div>
          <div className="font-mono-label flex items-center gap-2 text-[10px] tracking-widest text-white/60">
            <CurrencyDollar size={12} weight="fill" /> This month — paid commissions
          </div>
          <div
            data-testid="earnings-ticker-amount"
            className="mt-2 flex items-baseline font-display text-5xl font-black leading-none tracking-tight sm:text-7xl"
          >
            <span className="text-white/40">$</span>
            <span className="text-white">{formatNumber(animated)}</span>
            <span
              aria-hidden
              className="ml-3 inline-block h-3 w-3 animate-pulse rounded-full bg-[#10B981]"
            />
          </div>
          {pendingAmount > 0 && (
            <div
              data-testid="earnings-ticker-pending"
              className="mt-2 inline-flex items-center gap-1.5 border border-white/15 bg-white/5 px-2 py-1 text-[11px] font-semibold text-white/80"
            >
              <TrendUp size={11} weight="fill" />
              +${formatNumber(pendingAmount)} pending — approval in flight
            </div>
          )}
        </div>

        {/* Right — tier card */}
        <div className="w-full sm:w-80">
          <div className="font-mono-label flex items-center justify-between text-[10px] tracking-widest text-white/60">
            <span className="flex items-center gap-1.5">
              {isLegend ? (
                <Trophy size={11} weight="fill" />
              ) : (
                <Flame size={11} weight="fill" />
              )}
              Tier
            </span>
            <span>{currentLabel.toUpperCase()}</span>
          </div>
          <div className="mt-2 h-3 w-full overflow-hidden border border-white/20 bg-white/5">
            <div
              data-testid="earnings-ticker-progress"
              style={{ width: `${pct}%` }}
              className="h-full bg-gradient-to-r from-[#0044FF] to-[#10B981] transition-all duration-1000 ease-out"
            />
          </div>
          {isLegend ? (
            <div className="mt-2 text-xs text-white/80">
              <strong>Legend tier reached.</strong> You&apos;ve hit the top rung this month.
            </div>
          ) : (
            <div className="mt-2 flex items-baseline justify-between text-[11px] text-white/70">
              <span>
                ${formatNumber(needed)} to{" "}
                <strong className="text-white">{nextLabel}</strong>
              </span>
              <span data-testid="earnings-ticker-progress-label">{pct}%</span>
            </div>
          )}
          {/* Mini ladder — visualizes where the VA is in the climb */}
          <div className="mt-3 flex items-center gap-1">
            {(tier?.ladder || []).map((rung) => {
              const isCurrent = rung.key === tier?.current?.key;
              const isPast =
                (tier?.ladder || []).findIndex((r) => r.key === tier?.current?.key) >
                (tier?.ladder || []).findIndex((r) => r.key === rung.key);
              return (
                <div
                  key={rung.key}
                  data-testid={`tier-rung-${rung.key}`}
                  className={`flex flex-1 flex-col items-center gap-1 text-[8px] tracking-widest ${
                    isCurrent
                      ? "text-white"
                      : isPast
                      ? "text-white/60"
                      : "text-white/30"
                  }`}
                  title={`${rung.label} — $${rung.min}/mo`}
                >
                  <div
                    className={`h-1 w-full ${
                      isCurrent || isPast ? "bg-[#10B981]" : "bg-white/15"
                    }`}
                  />
                  <span className="uppercase">{rung.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatNumber(n) {
  const v = Number(n || 0);
  // Show cents only when relevant (under $100), otherwise drop cents for legibility.
  if (v < 100) return v.toFixed(2);
  return Math.round(v).toLocaleString("en-US");
}
