import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { ALL_SERVICE_TYPES, isDigitalService } from "@/lib/leadOptions";
import { Calculator, ArrowUp } from "@phosphor-icons/react";

const BASE_CATEGORY = {
  routine: "A",
  deep: "B", moveout: "B", apartment_turnover: "B", estate_cleanout: "B",
  specialty: "B", specialty_construction: "B",
  handyman: "C", painting: "C", junk_removal: "C", pressure_washing: "C",
  carpet: "C", landscaping: "C", maintenance_bundle: "C",
  commercial: "E", specialty_medical: "E", specialty_funeral: "E",
};

const resolveCategory = (svc, isRec) => {
  if (["commercial", "specialty_medical", "specialty_funeral"].includes(svc)) return "E";
  if (isDigitalService(svc)) return isRec ? "G" : "F";
  if (isRec) return "D";
  return BASE_CATEGORY[svc] || null;
};

const money = (n) => `$${(Number(n) || 0).toFixed(2)}`;

export default function EarningsCalculator() {
  const [cfg, setCfg] = useState(null);
  const [svc, setSvc] = useState("deep");
  const [recurring, setRecurring] = useState(false);
  const [amount, setAmount] = useState("300");

  useEffect(() => {
    api.get("/va/pool-rates").then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const result = useMemo(() => {
    if (!cfg) return null;
    const base = parseFloat(amount);
    if (!Number.isFinite(base) || base <= 0) return null;
    const cat = resolveCategory(svc, recurring);
    if (!cat) return null;
    const rates = cfg.pool_rates || {};
    const agentPct = (cfg.pool_split?.agent ?? 75) / 100;
    const tier = cfg.agent_tier?.tier || "agent";

    if (cat === "D") {
      const d = rates.D || {};
      const per = (r) => (base * (r / 100)) * agentPct;
      return {
        cat, kind: "tail",
        rows: [
          { label: "Visits 1–3", rate: d.early, you: per(d.early) },
          { label: "Visits 4–12", rate: d.mid, you: per(d.mid) },
          { label: "Visit 13+ · for life", rate: d.lifetime, you: per(d.lifetime) },
        ],
      };
    }
    if (cat === "E" || cat === "G") {
      const rate = rates[cat]?.pct ?? 5;
      const pool = base * (rate / 100);
      return { cat, kind: "monthly", rate, pool, you: pool * agentPct };
    }
    const catRates = rates[cat] || {};
    const rate = catRates[tier];
    const pool = base * (rate / 100);
    const next = cfg.agent_tier?.next_tier;
    let nextRow = null;
    if (next && catRates[next] != null) {
      nextRow = {
        tier: next,
        you: base * (catRates[next] / 100) * agentPct,
        jobs: cfg.agent_tier?.jobs_to_next,
      };
    }
    return { cat, kind: "tiered", tier, rate, pool, you: pool * agentPct, nextRow };
  }, [cfg, svc, recurring, amount]);

  if (!cfg) return null;

  const cat = resolveCategory(svc, recurring);
  const revenueBased = cat === "E" || cat === "G";

  return (
    <div data-testid="earnings-calculator" className="mb-6 border border-[#E5E7EB] bg-white">
      <div className="flex items-center gap-2 border-b border-[#E5E7EB] px-5 py-3">
        <Calculator size={16} weight="duotone" className="text-[#0044FF]" />
        <span className="font-mono-label text-[#4B5563]">EARNINGS CALCULATOR</span>
        <span className="ml-auto bg-[#030712] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
          your tier: {cfg.agent_tier?.tier}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
        <div>
          <label className="font-mono-label text-[#4B5563]">SERVICE</label>
          <select
            data-testid="calc-service"
            value={svc}
            onChange={(e) => setSvc(e.target.value)}
            className="mt-1.5 h-10 w-full border border-[#030712] bg-white px-2 text-sm"
          >
            {ALL_SERVICE_TYPES.filter((s) => s.value !== "unknown").map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs text-[#4B5563]">
            <input
              type="checkbox"
              data-testid="calc-recurring"
              checked={recurring}
              onChange={(e) => setRecurring(e.target.checked)}
              className="h-4 w-4 accent-[#0044FF]"
            />
            Recurring account
          </label>
        </div>
        <div>
          <label className="font-mono-label text-[#4B5563]">
            {revenueBased ? "MONTHLY COLLECTED REVENUE ($)" : "EXPECTED JOB PROFIT ($)"}
          </label>
          <Input
            data-testid="calc-amount"
            type="number"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="mt-1.5 h-10 rounded-none border-[#030712]"
          />
          <p className="mt-2 text-[11px] text-[#9CA3AF]">
            Pool = rate × {revenueBased ? "revenue" : "profit"} · you keep {cfg.pool_split?.agent ?? 75}% of the pool.
          </p>
        </div>
        <div data-testid="calc-result" className="border border-[#030712] bg-[#F0F4FF] p-4">
          {!result ? (
            <div className="text-xs text-[#9CA3AF]">Enter an amount to see your cut.</div>
          ) : result.kind === "tail" ? (
            <div className="space-y-1.5">
              <div className="font-mono-label text-[#4B5563]">YOU EARN, EVERY VISIT</div>
              {result.rows.map((r) => (
                <div key={r.label} className="flex items-baseline justify-between text-sm">
                  <span className="text-[#4B5563]">{r.label} <span className="text-[10px]">({r.rate}%)</span></span>
                  <span className="font-display font-black text-[#0044FF]" data-testid={`calc-tail-${r.rate}`}>{money(r.you)}</span>
                </div>
              ))}
              <div className="pt-1 text-[10px] text-[#9CA3AF]">No cap — for as long as the client stays active.</div>
            </div>
          ) : result.kind === "monthly" ? (
            <div>
              <div className="font-mono-label text-[#4B5563]">YOU EARN, EVERY MONTH</div>
              <div className="font-display mt-1 text-3xl font-black text-[#0044FF]" data-testid="calc-you-earn">
                {money(result.you)}
              </div>
              <div className="mt-1 text-[11px] text-[#4B5563]">
                {result.rate}% pool of {money(parseFloat(amount))} = {money(result.pool)} · for the life of the account
              </div>
            </div>
          ) : (
            <div>
              <div className="font-mono-label text-[#4B5563]">YOU EARN</div>
              <div className="font-display mt-1 text-3xl font-black text-[#0044FF]" data-testid="calc-you-earn">
                {money(result.you)}
              </div>
              <div className="mt-1 text-[11px] text-[#4B5563]">
                Cat {result.cat} · {result.rate}% pool = {money(result.pool)} · your {cfg.pool_split?.agent ?? 75}%
              </div>
              {result.nextRow && (
                <div className="mt-2 flex items-center gap-1 border-t border-[#0044FF]/20 pt-2 text-[11px] font-semibold text-emerald-700" data-testid="calc-next-tier">
                  <ArrowUp size={12} weight="bold" />
                  {money(result.nextRow.you)} at {result.nextRow.tier.toUpperCase()} — {result.nextRow.jobs} more paid job{result.nextRow.jobs === 1 ? "" : "s"} to unlock
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
