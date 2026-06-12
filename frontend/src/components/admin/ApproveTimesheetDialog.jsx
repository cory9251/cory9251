import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { CheckCircle } from "@phosphor-icons/react";
import WorkerLink from "@/components/admin/WorkerLink";

/**
 * Approve a worker's clocked-out timesheet. Optionally lets the admin tweak
 * hours_worked and earnings before releasing it to the worker's earnings view.
 */
export default function ApproveTimesheetDialog({
  open,
  onOpenChange,
  gigId,
  acceptance,
  onSaved,
}) {
  const [hours, setHours] = useState("");
  const [earnings, setEarnings] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && acceptance) {
      setHours(
        acceptance.hours_worked != null ? String(acceptance.hours_worked) : ""
      );
      setEarnings(
        acceptance.earnings != null ? String(acceptance.earnings) : ""
      );
      setNote("");
    }
  }, [open, acceptance]);

  if (!acceptance) return null;

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {};
      const h = String(hours).trim();
      if (h !== "" && Number(h) !== acceptance.hours_worked) {
        const n = Number(h);
        if (!Number.isFinite(n) || n < 0) {
          toast.error("Hours must be a non-negative number");
          setSaving(false);
          return;
        }
        payload.hours_worked = n;
      }
      const ee = String(earnings).trim();
      if (ee !== "" && Number(ee) !== acceptance.earnings) {
        const n = Number(ee);
        if (!Number.isFinite(n) || n < 0) {
          toast.error("Earnings must be a non-negative number");
          setSaving(false);
          return;
        }
        payload.earnings = n;
      }
      if (note.trim()) payload.note = note.trim();
      await api.post(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/approve-timesheet`,
        payload
      );
      toast.success("Timesheet approved");
      onSaved && onSaved();
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  const rate = acceptance.pay_rate_applied ?? acceptance.pay_rate_effective;
  const rateType = acceptance.pay_type_applied || acceptance.pay_type_effective;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md rounded-none border-[#030712]"
        data-testid="approve-timesheet-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black">
            Approve timesheet
          </DialogTitle>
          <DialogDescription>
            Release earnings to{" "}
            <span className="font-semibold">
              <WorkerLink workerId={acceptance.worker_id} name={acceptance.worker_name} />
            </span>.
            Edit hours or earnings below if you need to correct them.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div className="border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs">
            <div className="font-mono-label">Rate applied</div>
            <div className="mt-1 font-semibold text-[#0044FF]">
              {rate != null
                ? `$${Number(rate).toFixed(2)} ${rateType === "hourly" ? "/hr" : "flat"}`
                : "—"}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="font-mono-label">Hours worked</Label>
              <Input
                data-testid="approve-hours-input"
                type="number"
                step="0.01"
                min="0"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Earnings ($)</Label>
              <Input
                data-testid="approve-earnings-input"
                type="number"
                step="0.01"
                min="0"
                value={earnings}
                onChange={(e) => setEarnings(e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
              <div className="mt-1 text-[10px] text-[#4B5563]">
                Leave to auto-compute from hours × rate.
              </div>
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Internal note (optional)</Label>
            <Textarea
              data-testid="approve-note-input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="e.g. confirmed by phone, trimmed 15 min lunch…"
              className="mt-2 rounded-none border-[#030712]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
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
              data-testid="confirm-approve-timesheet"
              disabled={saving}
              className="rounded-none bg-[#10B981] text-white hover:bg-[#0e9971]"
            >
              <CheckCircle size={14} weight="fill" className="mr-2" />
              {saving ? "Approving…" : "Approve & release"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
