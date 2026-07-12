import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Percent, FloppyDisk, ArrowCounterClockwise, Coins, UsersThree } from "@phosphor-icons/react";

const TIERED = ["A", "B", "C", "F"];
const TIER_COLS = ["agent", "senior", "elite"];
const D_COLS = [
  { key: "early", label: "Visits 1–3" },
  { key: "mid", label: "Visits 4–12" },
  { key: "lifetime", label: "Visit 13+ (lifetime)" },
];

function toEditable(poolRates) {
  const out = {};
  Object.entries(poolRates || {}).forEach(([cat, sub]) => {
    out[cat] = {};
    Object.entries(sub).forEach(([k, v]) => {
      out[cat][k] = String(v);
    });
  });
  return out;
}

export default function AdminVARates() {
  const [data, setData] = useState(null);
  const [rates, setRates] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data: d } = await api.get("/pm/commission-settings");
      setData(d);
      setRates(toEditable(d.pool_rates));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load(); // eslint-disable-line
  }, []);

  const upd = (cat, key, val) =>
    setRates((r) => ({ ...r, [cat]: { ...r[cat], [key]: val } }));

  const save = async () => {
    const pool_rates = {};
    for (const [cat, sub] of Object.entries(rates)) {
      pool_rates[cat] = {};
      for (const [k, v] of Object.entries(sub)) {
        const fv = parseFloat(v);
        if (!Number.isFinite(fv) || fv < 0 || fv > 100) {
          return toast.error(`${cat}.${k} must be a number between 0 and 100`);
        }
        pool_rates[cat][k] = fv;
      }
    }
    setSaving(true);
    try {
      await api.put("/pm/commission-settings", { pool_rates });
      toast.success("Pool rates saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  if (!data || !rates) return <div className="p-8 text-sm text-[#4B5563]">Loading…</div>;

  const labels = data.category_labels || {};
  const split = data.pool_split || { agent: 75, lead: 15, ops: 10 };
  const thresholds = data.tier_thresholds || { senior: 25, elite: 60 };

  const RateInput = ({ cat, k }) => (
    <div className="flex items-center gap-1">
      <Input
        data-testid={`rate-${cat}-${k}`}
        type="number"
        min="0"
        max="100"
        step="0.5"
        value={rates[cat]?.[k] ?? ""}
        onChange={(e) => upd(cat, k, e.target.value)}
        className="h-9 w-20 rounded-none"
      />
      <span className="text-xs font-bold">%</span>
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl p-6 md:p-10" data-testid="admin-va-rates-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <Percent size={14} weight="fill" /> VA PROGRAM · COMMISSION RATES
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        Fixed Pool Model
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Every closed + paid job generates exactly one commission pool: the pool rate below ×
        job profit (or × collected revenue for Commercial and Retainers). The pool then splits
        automatically — the Company never pays beyond the pool.
      </p>

      {/* Fixed split */}
      <div className="mt-6 grid grid-cols-3 gap-3" data-testid="pool-split-banner">
        {[
          { label: "PRODUCING AGENT", pct: split.agent, icon: Coins },
          { label: "TEAM LEAD", pct: split.lead, icon: UsersThree, note: "retained by Company if no qualified lead" },
          { label: "OPERATIONS MGR", pct: split.ops, icon: Percent },
        ].map((s) => (
          <div key={s.label} className="border border-[#030712] bg-[#F0F4FF] p-4">
            <div className="font-mono-label text-[#4B5563]">{s.label}</div>
            <div className="font-display mt-1 text-3xl font-black text-[#0044FF]">{s.pct}%</div>
            {s.note && <div className="mt-1 text-[10px] text-[#4B5563]">{s.note}</div>}
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-[#9CA3AF]">
        The 75 / 15 / 10 split is fixed per the commission structure doc — only category pool
        rates are editable below.
      </p>

      {/* Tier ladder */}
      <div className="mt-6 flex flex-wrap gap-3 text-xs" data-testid="tier-thresholds">
        <span className="border border-[#E5E7EB] bg-white px-3 py-1.5">
          <strong>AGENT</strong> — starting tier
        </span>
        <span className="border border-[#E5E7EB] bg-white px-3 py-1.5">
          <strong>SENIOR</strong> — {thresholds.senior} closed + paid jobs
        </span>
        <span className="border border-[#E5E7EB] bg-white px-3 py-1.5">
          <strong>ELITE</strong> — {thresholds.elite} closed + paid jobs
        </span>
        <span className="text-[#9CA3AF] self-center">Tiers never move backward.</span>
      </div>

      {/* Tiered categories (pool = % of job profit) */}
      <h2 className="font-display mt-8 text-lg font-black">
        Pool rates — % of job profit (by tier)
      </h2>
      <div className="mt-3 overflow-x-auto border border-[#E5E7EB] bg-white">
        <table className="w-full text-sm">
          <thead className="bg-[#F9FAFB]">
            <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
              <th className="px-4 py-3">Category</th>
              {TIER_COLS.map((t) => (
                <th key={t} className="px-4 py-3 capitalize">{t}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TIERED.map((cat) => (
              <tr key={cat} className="border-t border-[#E5E7EB]">
                <td className="px-4 py-3">
                  <span className="font-display font-black">{cat}</span>
                  <span className="ml-2 text-xs text-[#4B5563]">{labels[cat]}</span>
                </td>
                {TIER_COLS.map((t) => (
                  <td key={t} className="px-4 py-2">
                    <RateInput cat={cat} k={t} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Category D — recurring tail */}
      <h2 className="font-display mt-8 text-lg font-black">
        D · {labels.D} — lifetime tail (% of each visit&apos;s job profit)
      </h2>
      <div className="mt-3 border border-[#E5E7EB] bg-white p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {D_COLS.map((c) => (
            <div key={c.key}>
              <div className="font-mono-label text-[#4B5563]">{c.label}</div>
              <div className="mt-1.5">
                <RateInput cat="D" k={c.key} />
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-[#9CA3AF]">
          No cap — the visit-13+ rate continues for the life of the account. The tail pauses if
          the account goes inactive 30+ days and ends permanently after 90 days of inactivity.
        </p>
      </div>

      {/* E + G — revenue-based monthly */}
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {["E", "G"].map((cat) => (
          <div key={cat} className="border border-[#E5E7EB] bg-white p-4">
            <div className="font-display font-black">
              {cat} · {labels[cat]}
            </div>
            <div className="mt-2 flex items-center gap-3">
              <RateInput cat={cat} k="pct" />
              <span className="text-xs text-[#4B5563]">
                of monthly collected revenue — for the life of the {cat === "E" ? "account" : "retainer"}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex items-center gap-3">
        <Button
          data-testid="save-pool-rates"
          onClick={save}
          disabled={saving}
          className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
        >
          <FloppyDisk size={15} className="mr-1" /> Save pool rates
        </Button>
        <Button
          data-testid="reset-pool-rates"
          variant="outline"
          onClick={() => {
            setRates(toEditable(data.defaults?.pool_rates));
            toast.info("Restored doc defaults — hit Save to apply");
          }}
        >
          <ArrowCounterClockwise size={15} className="mr-1" /> Reset to doc defaults
        </Button>
      </div>
    </div>
  );
}
