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
import { Clock, Warning, ArrowClockwise } from "@phosphor-icons/react";

/**
 * Convert an ISO datetime (with tz) → value for <input type="datetime-local">
 * which expects "YYYY-MM-DDTHH:MM" in the user's local time zone.
 */
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Convert a "YYYY-MM-DDTHH:MM" local-time string from the input → full ISO
 * string with the browser's timezone offset baked in. Returns null if empty.
 */
function fromLocalInput(local) {
  if (!local) return null;
  // Construct a Date in the local zone, then emit ISO (UTC)
  const d = new Date(local);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

/**
 * Admin dialog to edit clock-in / clock-out times for a worker on a gig.
 * Supports: full manual entry, edit existing times, and clearing the clock-out
 * to put a worker back on the clock. Any change forces re-approval of the
 * timesheet on the backend.
 */
export default function EditTimesheetDialog({
  open,
  onOpenChange,
  gigId,
  acceptance,
  onSaved,
}) {
  const [clockIn, setClockIn] = useState("");
  const [clockOut, setClockOut] = useState("");
  const [clearOut, setClearOut] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && acceptance) {
      setClockIn(toLocalInput(acceptance.clock_in_at));
      setClockOut(toLocalInput(acceptance.clock_out_at));
      setClearOut(false);
    }
  }, [open, acceptance]);

  if (!acceptance) return null;

  const submit = async (e) => {
    e.preventDefault();

    if (!clockIn) {
      toast.error("Set a clock-in time first");
      return;
    }
    if (!clearOut && clockOut) {
      const inDt = new Date(clockIn);
      const outDt = new Date(clockOut);
      if (outDt <= inDt) {
        toast.error("Clock-out must be after clock-in");
        return;
      }
    }

    setSaving(true);
    try {
      const payload = {
        clock_in_at: fromLocalInput(clockIn),
      };
      if (clearOut) {
        payload.clear_clock_out = true;
      } else if (clockOut) {
        payload.clock_out_at = fromLocalInput(clockOut);
      } else {
        payload.clear_clock_out = true;
      }
      await api.put(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/timesheet`,
        payload
      );
      toast.success("Timesheet updated — needs re-approval");
      onSaved && onSaved();
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  // Live preview of hours + earnings based on current inputs
  const rate = acceptance.pay_rate_applied ?? acceptance.pay_rate_effective;
  const rateType = acceptance.pay_type_applied || acceptance.pay_type_effective;
  let previewHours = null;
  let previewEarnings = null;
  if (clockIn && !clearOut && clockOut) {
    const inDt = new Date(clockIn);
    const outDt = new Date(clockOut);
    if (outDt > inDt) {
      previewHours = (outDt - inDt) / 3600000;
      if (rate != null) {
        previewEarnings =
          rateType === "hourly"
            ? Number(rate) * previewHours
            : Number(rate);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md rounded-none border-[#030712]"
        data-testid="edit-timesheet-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black">
            Edit timesheet
          </DialogTitle>
          <DialogDescription>
            Correcting clock-in / clock-out for{" "}
            <span className="font-semibold">{acceptance.worker_name}</span>.
            Hours &amp; earnings auto-recompute and the timesheet will need
            re-approval.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label className="font-mono-label flex items-center gap-1.5">
              <Clock size={11} /> Clock-in (your local time)
            </Label>
            <Input
              data-testid="edit-clock-in"
              type="datetime-local"
              value={clockIn}
              onChange={(e) => setClockIn(e.target.value)}
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <Label className="font-mono-label flex items-center gap-1.5">
                <Clock size={11} /> Clock-out (your local time)
              </Label>
              <label className="flex cursor-pointer items-center gap-1.5 text-[10px] font-bold tracking-widest uppercase text-[#F59E0B]">
                <input
                  data-testid="edit-clear-out"
                  type="checkbox"
                  checked={clearOut}
                  onChange={(e) => setClearOut(e.target.checked)}
                  className="accent-[#F59E0B]"
                />
                Put back on clock
              </label>
            </div>
            <Input
              data-testid="edit-clock-out"
              type="datetime-local"
              value={clearOut ? "" : clockOut}
              onChange={(e) => setClockOut(e.target.value)}
              disabled={clearOut}
              className="mt-2 h-11 rounded-none border-[#030712] disabled:bg-[#F3F4F6]"
            />
            {clearOut && (
              <div className="mt-1 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#92400E]">
                <Warning size={10} weight="fill" /> Will erase clock-out and
                hours
              </div>
            )}
          </div>

          {/* Live preview */}
          <div className="grid grid-cols-2 gap-3 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs">
            <div>
              <div className="font-mono-label">Hours (preview)</div>
              <div className="mt-1 font-display text-lg font-black">
                {previewHours != null ? `${previewHours.toFixed(2)}h` : "—"}
              </div>
            </div>
            <div>
              <div className="font-mono-label">Earnings (preview)</div>
              <div className="mt-1 font-display text-lg font-black text-[#10B981]">
                {previewEarnings != null
                  ? `$${previewEarnings.toFixed(2)}`
                  : "—"}
              </div>
            </div>
            <div className="col-span-2 text-[10px] text-[#4B5563]">
              Rate applied:{" "}
              {rate != null
                ? `$${Number(rate).toFixed(2)} ${rateType === "hourly" ? "/hr" : "flat"}`
                : "—"}
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-[#E5E7EB] pt-3 text-[10px] text-[#4B5563]">
            <span className="inline-flex items-center gap-1">
              <ArrowClockwise size={10} /> Saving resets timesheet approval.
            </span>
          </div>

          <div className="flex justify-end gap-2">
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
              data-testid="save-edit-timesheet"
              disabled={saving}
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {saving ? "Saving…" : "Save timesheet"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
