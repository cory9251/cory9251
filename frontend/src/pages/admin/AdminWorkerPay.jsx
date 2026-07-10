import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { HandCoins, CheckCircle } from "@phosphor-icons/react";

function fmt(n) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function PayDialog({ open, onClose, target, onDone }) {
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setMethod("");
      setReference("");
    }
  }, [open]);

  const confirm = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/admin/worker-payments/mark-paid", {
        acceptance_ids: target.ids,
        payout_method: method || null,
        payout_reference: reference || null,
      });
      toast.success(`Marked ${data.paid.length} payment${data.paid.length === 1 ? "" : "s"} paid — logged to payroll expenses`);
      onDone();
      onClose();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  if (!target) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="pay-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black">
            Pay {target.label}
          </DialogTitle>
          <DialogDescription>
            {target.ids.length} shift{target.ids.length === 1 ? "" : "s"} ·{" "}
            <span className="font-bold text-[#030712]">{fmt(target.total)}</span> — this
            stamps them paid, notifies the worker, and auto-logs a payroll expense.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Method (optional)</Label>
            <Input
              data-testid="pay-method-input"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              placeholder="zelle / cashapp / check"
            />
          </div>
          <div>
            <Label>Reference (optional)</Label>
            <Input
              data-testid="pay-reference-input"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="TX id / memo"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-testid="pay-confirm-btn"
            onClick={confirm}
            disabled={saving}
            className="bg-emerald-700 text-white hover:bg-emerald-800"
          >
            {saving ? "Paying…" : `Mark paid ${fmt(target.total)}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminWorkerPay() {
  const [items, setItems] = useState(null);
  const [summary, setSummary] = useState({});
  const [tab, setTab] = useState("unpaid");
  const [payTarget, setPayTarget] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/worker-payments");
      setItems(data.items || []);
      setSummary(data.summary || {});
    } catch (e) {
      toast.error(getErr(e));
      setItems([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const unpaid = (items || []).filter((i) => !i.paid_at);
  const paidList = (items || []).filter((i) => i.paid_at);

  // Group unpaid by worker
  const groups = useMemo(() => {
    const map = new Map();
    for (const i of unpaid) {
      if (!map.has(i.worker_id)) map.set(i.worker_id, { name: i.worker_name, rows: [], total: 0 });
      const g = map.get(i.worker_id);
      g.rows.push(i);
      g.total += i.amount;
    }
    return [...map.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [items]); // eslint-disable-line

  return (
    <div className="mx-auto max-w-5xl" data-testid="admin-worker-pay-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <HandCoins size={14} weight="fill" /> FINANCE · WORKER PAY
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        Worker pay tracker
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Every approved timesheet lands here. Mark shifts paid and they're
        auto-logged as payroll expenses in Bookkeeping — no manual entry.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">OWED NOW</div>
          <div data-testid="summary-unpaid-total" className="font-display mt-1 text-2xl font-black text-[#B91C1C]">
            {fmt(summary.unpaid_total)}
          </div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">UNPAID SHIFTS</div>
          <div className="font-display mt-1 text-2xl font-black">{summary.unpaid_count ?? "—"}</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">WORKERS OWED</div>
          <div className="font-display mt-1 text-2xl font-black">{summary.workers_owed ?? "—"}</div>
        </div>
        <div className="border border-[#E5E7EB] bg-white p-4">
          <div className="font-mono-label text-[#4B5563]">PAID OUT (ALL TIME)</div>
          <div className="font-display mt-1 text-2xl font-black text-emerald-700">
            {fmt(summary.paid_total)}
          </div>
        </div>
      </div>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          data-testid="pay-tab-unpaid"
          onClick={() => setTab("unpaid")}
          className={`px-4 py-2 text-sm font-bold ${tab === "unpaid" ? "bg-[#030712] text-white" : "border border-[#E5E7EB] bg-white"}`}
        >
          Unpaid ({unpaid.length})
        </button>
        <button
          type="button"
          data-testid="pay-tab-paid"
          onClick={() => setTab("paid")}
          className={`px-4 py-2 text-sm font-bold ${tab === "paid" ? "bg-[#030712] text-white" : "border border-[#E5E7EB] bg-white"}`}
        >
          Paid ({paidList.length})
        </button>
      </div>

      {items === null ? (
        <div className="mt-8 text-sm text-[#4B5563]">Loading…</div>
      ) : tab === "unpaid" ? (
        <div className="mt-5 space-y-4">
          {groups.length === 0 && (
            <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
              Nobody's waiting on a payment. Approved timesheets will appear here.
            </div>
          )}
          {groups.map(([workerId, g]) => (
            <div key={workerId} data-testid={`pay-group-${workerId}`} className="border border-[#E5E7EB] bg-white">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] px-4 py-3">
                <div>
                  <span className="font-display text-sm font-black">{g.name}</span>
                  <span className="ml-2 text-xs text-[#6B7280]">
                    {g.rows.length} shift{g.rows.length === 1 ? "" : "s"} · owed{" "}
                    <span className="font-bold text-[#B91C1C]">{fmt(g.total)}</span>
                  </span>
                </div>
                <Button
                  size="sm"
                  data-testid={`pay-all-${workerId}`}
                  onClick={() =>
                    setPayTarget({
                      label: g.name,
                      ids: g.rows.map((r) => r.acceptance_id),
                      total: g.total,
                    })
                  }
                  className="bg-emerald-700 text-white hover:bg-emerald-800"
                >
                  Pay all {fmt(g.total)}
                </Button>
              </div>
              <div className="divide-y divide-[#F3F4F6]">
                {g.rows.map((r) => (
                  <div key={r.acceptance_id} data-testid={`pay-row-${r.acceptance_id}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">{r.gig_title}</div>
                      <div className="text-xs text-[#6B7280]">
                        {r.gig_date || "—"} · {r.paid_hours ?? r.hours_worked ?? "—"} hrs · approved{" "}
                        {r.timesheet_approved_at ? new Date(r.timesheet_approved_at).toLocaleDateString() : "—"}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-display text-sm font-black">{fmt(r.amount)}</span>
                      <Button
                        size="sm"
                        variant="outline"
                        data-testid={`mark-paid-${r.acceptance_id}`}
                        onClick={() =>
                          setPayTarget({ label: r.worker_name, ids: [r.acceptance_id], total: r.amount })
                        }
                      >
                        Mark paid
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-5 space-y-2">
          {paidList.length === 0 && (
            <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
              No payments logged yet.
            </div>
          )}
          {paidList.map((r) => (
            <div key={r.acceptance_id} data-testid={`paid-row-${r.acceptance_id}`} className="flex flex-wrap items-center justify-between gap-2 border border-[#E5E7EB] bg-white px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <CheckCircle size={15} weight="fill" className="shrink-0 text-emerald-700" />
                  <span className="truncate text-sm font-semibold">
                    {r.worker_name} · {r.gig_title}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-[#6B7280]">
                  Paid {r.paid_at ? new Date(r.paid_at).toLocaleString() : "—"}
                  {r.payout_method ? ` · ${r.payout_method}` : ""}
                  {r.payout_reference ? ` · ${r.payout_reference}` : ""}
                  {r.paid_by ? ` · by ${r.paid_by}` : ""}
                </div>
              </div>
              <span className="font-display text-sm font-black text-emerald-700">{fmt(r.amount)}</span>
            </div>
          ))}
        </div>
      )}

      <PayDialog
        open={Boolean(payTarget)}
        onClose={() => setPayTarget(null)}
        target={payTarget}
        onDone={load}
      />
    </div>
  );
}
