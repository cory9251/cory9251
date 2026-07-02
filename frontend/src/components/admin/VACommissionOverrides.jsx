import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Percent, FloppyDisk, XCircle } from "@phosphor-icons/react";
import { serviceTypeLabel } from "@/lib/leadOptions";

/** Per-VA commission overrides card (admin VA detail page).
 *  Empty input = use global default. Filled = override for this VA only. */
export const VACommissionOverrides = ({ vaUserId }) => {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/pm/vas/${vaUserId}/commission-overrides`);
      setData(data);
      setDrafts(Object.fromEntries(Object.entries(data.overrides || {}).map(([k, v]) => [k, String(v)])));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [vaUserId]);

  const save = async () => {
    const overrides = {};
    for (const [k, v] of Object.entries(drafts)) {
      if (v === "" || v == null) continue;
      const fv = parseFloat(v);
      if (!Number.isFinite(fv) || fv < 0) return toast.error(`Invalid value for ${k}`);
      overrides[k] = fv;
    }
    setSaving(true);
    try {
      await api.put(`/pm/vas/${vaUserId}/commission-overrides`, { overrides });
      toast.success(Object.keys(overrides).length ? "Custom rates saved for this VA" : "All overrides cleared — using global rates");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const clearAll = () => setDrafts({});

  if (!data) return null;
  const globals = data.globals || {};
  const flatKeys = Object.keys(globals.rates || {}).sort();
  const overrideCount = Object.values(drafts).filter((v) => v !== "" && v != null).length;

  const row = (key, label, globalValue, isPct) => (
    <div key={key} className="flex items-center justify-between gap-3 border-b border-[#F3F4F6] py-1.5">
      <div className="min-w-0 text-xs font-semibold text-[#374151]">{label}</div>
      <div className="flex items-center gap-2">
        <span className="w-16 text-right text-xs text-[#9CA3AF]">
          {isPct ? `${globalValue}%` : `$${globalValue}`}
        </span>
        <Input
          data-testid={`override-input-${key}`}
          type="number"
          min="0"
          step={isPct ? "0.5" : "1"}
          placeholder="—"
          value={drafts[key] ?? ""}
          onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}
          className={`h-8 w-24 rounded-none text-xs ${drafts[key] ? "border-[#0044FF] bg-[#F0F4FF] font-bold" : "border-[#E5E7EB]"}`}
        />
      </div>
    </div>
  );

  return (
    <section className="mb-8 border border-[#E5E7EB] bg-white p-6" data-testid="va-commission-overrides">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-mono-label">
          <Percent size={14} weight="duotone" /> Custom commission rates
          {overrideCount > 0 && (
            <span data-testid="override-count-badge" className="bg-[#0044FF] px-1.5 py-0.5 text-[9px] font-bold text-white">
              {overrideCount} custom
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            data-testid="overrides-clear-btn"
            variant="outline"
            onClick={clearAll}
            className="h-9 rounded-none border-[#030712] text-xs"
          >
            <XCircle size={12} className="mr-1" /> Clear all
          </Button>
          <Button
            data-testid="overrides-save-btn"
            onClick={save}
            disabled={saving}
            className="h-9 rounded-none bg-[#030712] text-xs text-white"
          >
            <FloppyDisk size={12} className="mr-1" /> {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
      <p className="mt-2 text-xs text-[#9CA3AF]">
        Leave blank to use the global rate (grey). Fill a value to override for this VA only —
        applies to commissions calculated from now on.
      </p>
      <div className="mt-4 grid gap-x-8 md:grid-cols-2">
        <div>
          <div className="font-mono-label mb-1 flex justify-between">
            <span>Flat payouts</span>
            <span className="normal-case">global → this VA</span>
          </div>
          {flatKeys.slice(0, Math.ceil(flatKeys.length / 2)).map((k) => row(k, serviceTypeLabel(k), globals.rates[k], false))}
        </div>
        <div>
          <div className="font-mono-label mb-1 hidden md:flex justify-between">
            <span>&nbsp;</span>
            <span className="normal-case">global → this VA</span>
          </div>
          {flatKeys.slice(Math.ceil(flatKeys.length / 2)).map((k) => row(k, serviceTypeLabel(k), globals.rates[k], false))}
          {row("commercial_pct", "Commercial (% of job value)", globals.commercial_pct, true)}
          {row("digital_pct", "Digital services (% of project)", globals.digital_pct, true)}
        </div>
      </div>
    </section>
  );
};
