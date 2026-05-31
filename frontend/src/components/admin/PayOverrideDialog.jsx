import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

/**
 * Per-gig pay override dialog. Lets the admin set a custom rate/type for a
 * specific worker on a specific gig. Sending null/empty clears the override
 * (falls back to worker default → gig posted).
 */
export default function PayOverrideDialog({
  open,
  onOpenChange,
  gigId,
  acceptance,
  onSaved,
}) {
  const [rate, setRate] = useState("");
  const [type, setType] = useState("hourly");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && acceptance) {
      setRate(
        acceptance.pay_rate_override != null
          ? String(acceptance.pay_rate_override)
          : ""
      );
      setType(
        acceptance.pay_type_override ||
          acceptance.pay_type_applied ||
          acceptance.pay_type_effective ||
          "hourly"
      );
    }
  }, [open, acceptance]);

  if (!acceptance) return null;

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {};
      const trimmed = String(rate).trim();
      if (trimmed === "") {
        payload.clear_rate = true;
      } else {
        const n = Number(trimmed);
        if (!Number.isFinite(n) || n < 0) {
          toast.error("Enter a non-negative number for the rate");
          setSaving(false);
          return;
        }
        payload.pay_rate_override = n;
      }
      payload.pay_type_override = type;
      await api.put(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/pay`,
        payload
      );
      toast.success("Pay override saved");
      onSaved && onSaved();
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  const clearOverride = async () => {
    setSaving(true);
    try {
      await api.put(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/pay`,
        { clear_rate: true, clear_type: true }
      );
      toast.success("Override cleared — using fallback rate");
      onSaved && onSaved();
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  const effective = acceptance.pay_rate_applied ?? acceptance.pay_rate_effective;
  const effectiveType = acceptance.pay_type_applied || acceptance.pay_type_effective;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md rounded-none border-[#030712]"
        data-testid="pay-override-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black">
            Pay override
          </DialogTitle>
          <DialogDescription>
            Set a custom rate for{" "}
            <span className="font-semibold">{acceptance.worker_name}</span> on
            this gig only. Leave blank to use the fallback rate.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={save} className="space-y-4">
          <div className="grid grid-cols-2 gap-3 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs">
            <div>
              <div className="font-mono-label">Worker default</div>
              <div className="mt-1 font-semibold">
                {acceptance.worker_default_pay_rate != null
                  ? `$${Number(acceptance.worker_default_pay_rate).toFixed(2)} ${
                      acceptance.worker_default_pay_type === "hourly" ? "/hr" : acceptance.worker_default_pay_type === "flat" ? "flat" : ""
                    }`
                  : "—"}
              </div>
            </div>
            <div>
              <div className="font-mono-label">Currently effective</div>
              <div className="mt-1 font-semibold text-[#0044FF]">
                {effective != null
                  ? `$${Number(effective).toFixed(2)} ${effectiveType === "hourly" ? "/hr" : "flat"}`
                  : "—"}
              </div>
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Pay rate ($)</Label>
            <Input
              data-testid="pay-rate-input"
              type="number"
              step="0.01"
              min="0"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              placeholder="Leave blank to clear override"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Pay type</Label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {["hourly", "flat"].map((t) => (
                <button
                  key={t}
                  type="button"
                  data-testid={`pay-type-${t}`}
                  onClick={() => setType(t)}
                  className={`h-11 border text-sm font-bold tracking-widest uppercase ${
                    type === t
                      ? "border-[#0044FF] bg-[#0044FF] text-white"
                      : "border-[#030712] bg-white text-[#030712]"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              data-testid="clear-override-btn"
              onClick={clearOverride}
              disabled={saving}
              className="rounded-none border-[#4B5563] text-xs"
            >
              Clear override
            </Button>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="rounded-none"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                data-testid="save-pay-override"
                disabled={saving}
                className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              >
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
