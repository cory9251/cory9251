import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Percent, FloppyDisk, ArrowCounterClockwise } from "@phosphor-icons/react";
import { serviceTypeLabel } from "@/lib/leadOptions";

export default function AdminVARates() {
  const [data, setData] = useState(null);
  const [rates, setRates] = useState({});
  const [commercial, setCommercial] = useState("");
  const [digital, setDigital] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/pm/commission-settings");
      setData(data);
      setRates(Object.fromEntries(Object.entries(data.rates).map(([k, v]) => [k, String(v)])));
      setCommercial(String(data.commercial_pct));
      setDigital(String(data.digital_pct));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const save = async () => {
    const cleanRates = {};
    for (const [k, v] of Object.entries(rates)) {
      const fv = parseFloat(v);
      if (!Number.isFinite(fv) || fv < 0) return toast.error(`Invalid rate for ${serviceTypeLabel(k)}`);
      cleanRates[k] = fv;
    }
    const c = parseFloat(commercial);
    const d = parseFloat(digital);
    if (!Number.isFinite(c) || c < 0 || c > 100) return toast.error("Commercial % must be 0–100");
    if (!Number.isFinite(d) || d < 0 || d > 100) return toast.error("Digital % must be 0–100");
    setSaving(true);
    try {
      await api.put("/pm/commission-settings", { rates: cleanRates, commercial_pct: c, digital_pct: d });
      toast.success("Global commission rates saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const resetDefaults = () => {
    if (!data) return;
    setRates(Object.fromEntries(Object.entries(data.defaults.rates).map(([k, v]) => [k, String(v)])));
    setCommercial(String(data.defaults.commercial_pct));
    setDigital(String(data.defaults.digital_pct));
    toast.info("Reset to platform defaults — hit Save to apply");
  };

  if (!data) return <div className="p-6 md:p-10 font-mono-label">Loading…</div>;

  return (
    <div className="p-6 md:p-10 max-w-4xl" data-testid="admin-va-rates">
      <div className="mb-6">
        <div className="font-mono-label">VA Commission Program</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Commission Rates</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Platform-wide defaults for every VA. Need a special deal for one VA? Set per-VA overrides on
          their detail page — overrides always win over these defaults.
        </p>
      </div>

      <section className="border-2 border-[#030712] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="font-mono-label flex items-center gap-2">
            <Percent size={14} weight="bold" /> Global default rates
          </div>
          <div className="flex gap-2">
            <Button
              data-testid="rates-reset-defaults"
              variant="outline"
              onClick={resetDefaults}
              className="h-9 rounded-none border-[#030712] text-xs"
            >
              <ArrowCounterClockwise size={12} className="mr-1" /> Reset to defaults
            </Button>
            <Button
              data-testid="rates-save-btn"
              onClick={save}
              disabled={saving}
              className="h-9 rounded-none bg-[#030712] px-4 text-xs text-white"
            >
              <FloppyDisk size={12} className="mr-1" /> {saving ? "Saving…" : "Save rates"}
            </Button>
          </div>
        </div>

        <div className="mt-5">
          <div className="font-mono-label mb-2">Flat payouts per closed lead ($)</div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {Object.keys(rates).sort().map((k) => (
              <div key={k}>
                <div className="mb-1 text-[11px] font-semibold text-[#4B5563]">
                  {serviceTypeLabel(k)}
                  {data.defaults.rates[k] !== parseFloat(rates[k]) && Number.isFinite(parseFloat(rates[k])) && (
                    <span className="ml-1 text-[#0044FF]" title={`Default: $${data.defaults.rates[k]}`}>•</span>
                  )}
                </div>
                <Input
                  data-testid={`rate-input-${k}`}
                  type="number"
                  min="0"
                  step="1"
                  value={rates[k]}
                  onChange={(e) => setRates({ ...rates, [k]: e.target.value })}
                  className="h-9 rounded-none border-[#030712]"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="border border-[#E5E7EB] bg-[#F9FAFB] p-4">
            <div className="font-mono-label mb-1">Commercial deals (% of job value)</div>
            <div className="flex items-center gap-2">
              <Input
                data-testid="rate-commercial-pct"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={commercial}
                onChange={(e) => setCommercial(e.target.value)}
                className="h-10 w-24 rounded-none border-[#030712] bg-white"
              />
              <span className="font-bold">%</span>
              <span className="text-xs text-[#9CA3AF]">default {data.defaults.commercial_pct}%</span>
            </div>
            <p className="mt-1 text-[11px] text-[#9CA3AF]">
              Applies to commercial, medical/funeral/construction specialty + maintenance bundles.
            </p>
          </div>
          <div className="border border-[#E5E7EB] bg-[#F0F4FF] p-4">
            <div className="font-mono-label mb-1">Digital services (% of project value)</div>
            <div className="flex items-center gap-2">
              <Input
                data-testid="rate-digital-pct"
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={digital}
                onChange={(e) => setDigital(e.target.value)}
                className="h-10 w-24 rounded-none border-[#030712] bg-white"
              />
              <span className="font-bold">%</span>
              <span className="text-xs text-[#9CA3AF]">default {data.defaults.digital_pct}%</span>
            </div>
            <p className="mt-1 text-[11px] text-[#9CA3AF]">
              Web/app dev, sourcing, marketing — synced with the Digital Services page setting.
            </p>
          </div>
        </div>
      </section>

      <p className="mt-4 text-xs text-[#9CA3AF]">
        Rate changes apply to commissions calculated from now on (when leads are booked/paid). Already
        approved or paid commissions are never recalculated.
      </p>
    </div>
  );
}
