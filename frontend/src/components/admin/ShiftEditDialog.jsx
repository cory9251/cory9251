import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CheckCircle,
  CheckSquareOffset,
  Trash,
  Warning,
} from "@phosphor-icons/react";

/** Convert an ISO timestamp to the `YYYY-MM-DDTHH:mm` format required by
 * <input type="datetime-local">. Returns "" if the input is empty/invalid. */
const isoToLocalInput = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return "";
  }
};

/** Convert a `datetime-local` value back to an ISO string the backend expects.
 * Returns null when the input is empty so we can `clear_clock_out`. */
const localInputToIso = (local) => {
  if (!local) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
};

/**
 * ShiftEditDialog — admin-only modal for editing a single worker acceptance.
 * Supports:
 *  - Editing clock-in / clock-out times (recomputes hours + earnings server-side)
 *  - Adding an admin note (audited)
 *  - Marking the shift as No-Show (with reason)
 *  - Force-marking the shift Completed (worker forgot to clock out)
 *  - Removing the worker from the gig entirely (releases the slot)
 *
 * @param {object} props
 * @param {object} props.acceptance - the acceptance row from the worker profile
 * @param {boolean} props.open
 * @param {function} props.onOpenChange
 * @param {function} props.onSaved - fires after any successful action
 */
export default function ShiftEditDialog({ acceptance, open, onOpenChange, onSaved }) {
  const [clockIn, setClockIn] = useState("");
  const [clockOut, setClockOut] = useState("");
  const [adminNote, setAdminNote] = useState("");
  const [noShowReason, setNoShowReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("edit"); // "edit" | "noshow" | "remove"

  const gigId = acceptance?.gig_id;
  const accId = acceptance?.acceptance_id;
  const title = acceptance?.gig_title || acceptance?.gig_id || "this shift";

  useEffect(() => {
    if (open && acceptance) {
      setClockIn(isoToLocalInput(acceptance.clock_in_at));
      setClockOut(isoToLocalInput(acceptance.clock_out_at));
      setAdminNote(acceptance.admin_note || "");
      setNoShowReason("");
      setView("edit");
    }
  }, [open, acceptance]);

  const dirty = useMemo(() => {
    if (!acceptance) return false;
    return (
      clockIn !== isoToLocalInput(acceptance.clock_in_at) ||
      clockOut !== isoToLocalInput(acceptance.clock_out_at) ||
      adminNote !== (acceptance.admin_note || "")
    );
  }, [acceptance, clockIn, clockOut, adminNote]);

  const close = () => {
    if (busy) return;
    onOpenChange?.(false);
  };

  const saveTimesheet = async () => {
    if (!gigId || !accId) return;
    setBusy(true);
    try {
      const body = {
        clock_in_at: clockIn ? localInputToIso(clockIn) : null,
        clock_out_at: clockOut ? localInputToIso(clockOut) : null,
        clear_clock_out: !clockOut && !!acceptance.clock_out_at,
        admin_note: adminNote,
      };
      await api.put(`/gigs/${gigId}/acceptances/${accId}/timesheet`, body);
      toast.success("Shift updated");
      onSaved?.();
      onOpenChange?.(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const markCompleted = async () => {
    if (!gigId || !accId) return;
    setBusy(true);
    try {
      const body = {
        clock_in_at: clockIn ? localInputToIso(clockIn) : null,
        clock_out_at: clockOut ? localInputToIso(clockOut) : null,
        admin_note: adminNote,
      };
      await api.post(`/gigs/${gigId}/acceptances/${accId}/mark-completed`, body);
      toast.success("Shift marked completed");
      onSaved?.();
      onOpenChange?.(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const markNoShow = async () => {
    if (!gigId || !accId) return;
    if (!noShowReason.trim()) {
      toast.error("Pick a reason");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/acceptances/${accId}/no-show`, {
        reason: noShowReason.trim(),
        admin_note: adminNote || null,
      });
      toast.success("Marked as no-show");
      onSaved?.();
      onOpenChange?.(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const removeWorker = async () => {
    if (!gigId || !accId) return;
    setBusy(true);
    try {
      await api.delete(`/gigs/${gigId}/acceptances/${accId}`);
      toast.success("Worker removed from gig");
      onSaved?.();
      onOpenChange?.(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        data-testid="shift-edit-dialog"
        className="max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black tracking-tight">
            Edit shift
          </DialogTitle>
          <p className="text-xs text-[#4B5563]">{title}</p>
        </DialogHeader>

        {/* Sub-view tabs */}
        <div className="mb-2 flex gap-1 border-b border-[#E5E7EB]">
          {[
            { k: "edit", l: "Edit times" },
            { k: "noshow", l: "No-show" },
            { k: "remove", l: "Remove" },
          ].map((t) => (
            <button
              key={t.k}
              data-testid={`shift-edit-tab-${t.k}`}
              onClick={() => setView(t.k)}
              className={`px-3 py-2 text-xs font-bold uppercase tracking-widest transition-colors ${
                view === t.k
                  ? "border-b-2 border-[#0044FF] text-[#0044FF]"
                  : "text-[#4B5563] hover:text-[#030712]"
              }`}
            >
              {t.l}
            </button>
          ))}
        </div>

        {view === "edit" && (
          <div className="space-y-4">
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Clock in
              </Label>
              <input
                data-testid="shift-edit-clock-in"
                type="datetime-local"
                value={clockIn}
                onChange={(e) => setClockIn(e.target.value)}
                className="mt-1 h-11 w-full rounded-lg border border-[#030712] bg-white px-3 text-sm"
              />
            </div>
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Clock out
              </Label>
              <input
                data-testid="shift-edit-clock-out"
                type="datetime-local"
                value={clockOut}
                onChange={(e) => setClockOut(e.target.value)}
                className="mt-1 h-11 w-full rounded-lg border border-[#030712] bg-white px-3 text-sm"
              />
              <div className="mt-1 text-[10px] text-[#4B5563]">
                Leave empty to clear clock-out (returns the shift to in-progress).
              </div>
            </div>
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Admin note (optional)
              </Label>
              <Textarea
                data-testid="shift-edit-admin-note"
                value={adminNote}
                onChange={(e) => setAdminNote(e.target.value)}
                placeholder="e.g. 15 min late but did great work"
                rows={3}
                className="mt-1 text-sm"
                maxLength={2000}
              />
            </div>
            <div className="flex flex-col gap-2 pt-2 sm:flex-row">
              <Button
                data-testid="shift-edit-save"
                disabled={busy || !dirty}
                onClick={saveTimesheet}
                className="h-11 flex-1 rounded-lg bg-[#0044FF] text-white hover:bg-[#0036cc] disabled:opacity-50"
              >
                {busy ? "Saving…" : "Save changes"}
              </Button>
              <Button
                data-testid="shift-edit-mark-completed"
                variant="outline"
                disabled={busy || !clockIn}
                onClick={markCompleted}
                className="h-11 flex-1 rounded-lg border-[#10B981] text-[#10B981] hover:bg-[#10B981]/10"
                title={!clockIn ? "Set a clock-in time first" : "Force-mark this shift as completed"}
              >
                <CheckCircle size={16} weight="fill" className="mr-2" />
                Mark completed
              </Button>
            </div>
          </div>
        )}

        {view === "noshow" && (
          <div className="space-y-4">
            <div className="border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
              <Warning weight="fill" className="-mt-0.5 mr-1 inline-block" size={14} />
              Marking as no-show clears clock-in/out and removes earnings. The worker is notified.
            </div>
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Reason
              </Label>
              <select
                data-testid="shift-edit-noshow-reason"
                value={noShowReason}
                onChange={(e) => setNoShowReason(e.target.value)}
                className="mt-1 h-11 w-full rounded-lg border border-[#030712] bg-white px-3 text-sm"
              >
                <option value="">Pick a reason…</option>
                <option value="Did not show up">Did not show up</option>
                <option value="Arrived too late to start">Arrived too late to start</option>
                <option value="Left before completing the shift">Left before completing the shift</option>
                <option value="Customer reported absence">Customer reported absence</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Admin note (optional)
              </Label>
              <Textarea
                data-testid="shift-edit-noshow-note"
                value={adminNote}
                onChange={(e) => setAdminNote(e.target.value)}
                placeholder="More context (e.g. customer's name, time observed)"
                rows={3}
                className="mt-1 text-sm"
                maxLength={2000}
              />
            </div>
            <Button
              data-testid="shift-edit-mark-noshow"
              disabled={busy || !noShowReason.trim()}
              onClick={markNoShow}
              className="h-11 w-full rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
            >
              <CheckSquareOffset size={16} weight="fill" className="mr-2" />
              {busy ? "Marking…" : "Mark as no-show"}
            </Button>
          </div>
        )}

        {view === "remove" && (
          <div className="space-y-4">
            <div className="border border-red-300 bg-red-50 p-3 text-xs text-red-900">
              <Warning weight="fill" className="-mt-0.5 mr-1 inline-block" size={14} />
              Removes the worker from this gig entirely. Frees up their slot (a backup may auto-promote). The worker is notified.
            </div>
            <div>
              <Label className="font-mono-label text-[10px] uppercase tracking-widest">
                Admin note (optional)
              </Label>
              <Textarea
                data-testid="shift-edit-remove-note"
                value={adminNote}
                onChange={(e) => setAdminNote(e.target.value)}
                placeholder="Why are you removing this worker?"
                rows={3}
                className="mt-1 text-sm"
                maxLength={2000}
              />
            </div>
            <Button
              data-testid="shift-edit-remove-worker"
              disabled={busy}
              onClick={removeWorker}
              className="h-11 w-full rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
            >
              <Trash size={16} weight="fill" className="mr-2" />
              {busy ? "Removing…" : "Remove worker from gig"}
            </Button>
          </div>
        )}

        <div className="pt-2">
          <Button
            data-testid="shift-edit-close"
            variant="ghost"
            onClick={close}
            disabled={busy}
            className="h-10 w-full text-xs text-[#4B5563]"
          >
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
