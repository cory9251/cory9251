import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Check, Flag, X as XIcon } from "@phosphor-icons/react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

const STATUS_LABELS = {
  calculating: { label: "Calculating", color: "bg-[#9CA3AF] text-white" },
  pending_approval: { label: "Pending approval", color: "bg-amber-500 text-white" },
  pm_approved: { label: "PM approved", color: "bg-[#0044FF] text-white" },
  owner_approved: { label: "Owner approved", color: "bg-violet-600 text-white" },
  paid: { label: "Paid ✓", color: "bg-emerald-700 text-white" },
  flagged: { label: "Flagged", color: "bg-red-600 text-white" },
  rejected: { label: "Rejected", color: "bg-red-700 text-white" },
};
function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || STATUS_LABELS.calculating;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${s.color}`}>
      {s.label}
    </span>
  );
}

export default function AdminVACommissions() {
  const [items, setItems] = useState(null);
  const [filter, setFilter] = useState("queue"); // queue | all | pm_approved | paid | rejected
  const [err, setErr] = useState("");
  const [modal, setModal] = useState(null); // { kind: 'flag'|'reject'|'approve', commission }
  const [note, setNote] = useState("");

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (filter === "queue") {
        // default — pending+flagged
      } else if (filter === "all") {
        params.set("status", "");
      } else {
        params.set("status", filter);
      }
      const { data } = await api.get(`/pm/commissions?${params.toString()}`);
      setItems(data.items || []);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [filter]);

  const performAction = async () => {
    if (!modal) return;
    try {
      const path =
        modal.kind === "approve"
          ? `/pm/commissions/${modal.commission.commission_id}/approve`
          : modal.kind === "flag"
          ? `/pm/commissions/${modal.commission.commission_id}/flag`
          : `/pm/commissions/${modal.commission.commission_id}/reject`;
      await api.post(path, { note });
      toast.success(`Commission ${modal.kind === "approve" ? "approved" : modal.kind}`);
      setModal(null);
      setNote("");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const tabs = [
    { value: "queue", label: "Approval queue" },
    { value: "pm_approved", label: "PM approved" },
    { value: "owner_approved", label: "Owner approved" },
    { value: "paid", label: "Paid" },
    { value: "rejected", label: "Rejected" },
  ];

  return (
    <div className="p-6 md:p-10" data-testid="admin-va-commissions">
      <div className="mb-6">
        <div className="font-mono-label">VA Commission Program</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Commission approval queue</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Review every commission before it reaches the Owner for final payout sign-off. Job must be Completed AND Paid before a commission appears here.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.value}
            data-testid={`comm-tab-${t.value}`}
            onClick={() => setFilter(t.value)}
            className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
              filter === t.value
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          {filter === "queue" ? "Approval queue is empty — nothing pending. 🎉" : "No commissions in this state."}
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">VA</th>
                <th className="px-3 py-3">Lead</th>
                <th className="px-3 py-3">Service</th>
                <th className="px-3 py-3">Calc</th>
                <th className="px-3 py-3 text-right">Amount</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Created</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr
                  key={c.commission_id}
                  data-testid={`comm-row-${c.commission_id}`}
                  className="border-t border-[#E5E7EB] hover:bg-[#F9FAFB]"
                >
                  <td className="px-3 py-3 font-semibold">{c.va_name || "—"}</td>
                  <td className="px-3 py-3">
                    <div className="font-semibold">{c.prospect_name}</div>
                    <div className="text-[10px] text-[#4B5563] font-mono">{c.lead_id}</div>
                  </td>
                  <td className="px-3 py-3 capitalize">{c.service_type}</td>
                  <td className="px-3 py-3 text-xs text-[#4B5563]">{c.calc_notes}</td>
                  <td className="px-3 py-3 text-right font-mono font-semibold">{fmtMoney(c.amount)}</td>
                  <td className="px-3 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-3 py-3 text-xs text-[#4B5563]">{(c.created_at || "").slice(0, 10)}</td>
                  <td className="px-3 py-3">
                    {["pending_approval", "flagged"].includes(c.status) ? (
                      <div className="flex flex-wrap gap-1">
                        <button
                          data-testid={`comm-approve-${c.commission_id}`}
                          onClick={() => {
                            setModal({ kind: "approve", commission: c });
                            setNote("");
                          }}
                          className="inline-flex items-center gap-1 border border-emerald-700 bg-white px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-700 hover:text-white"
                        >
                          <Check size={11} weight="bold" /> Approve
                        </button>
                        <button
                          data-testid={`comm-flag-${c.commission_id}`}
                          onClick={() => {
                            setModal({ kind: "flag", commission: c });
                            setNote("");
                          }}
                          className="inline-flex items-center gap-1 border border-amber-600 bg-white px-2 py-1 text-xs text-amber-700 hover:bg-amber-600 hover:text-white"
                        >
                          <Flag size={11} weight="bold" /> Flag
                        </button>
                        <button
                          data-testid={`comm-reject-${c.commission_id}`}
                          onClick={() => {
                            setModal({ kind: "reject", commission: c });
                            setNote("");
                          }}
                          className="inline-flex items-center gap-1 border border-red-700 bg-white px-2 py-1 text-xs text-red-700 hover:bg-red-700 hover:text-white"
                        >
                          <XIcon size={11} weight="bold" /> Reject
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-[#9CA3AF]">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!modal} onOpenChange={(o) => { if (!o) { setModal(null); setNote(""); } }}>
        <DialogContent data-testid="comm-action-dialog">
          <DialogHeader>
            <DialogTitle>
              {modal?.kind === "approve"
                ? "Approve commission"
                : modal?.kind === "flag"
                ? "Flag commission"
                : "Reject commission"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm">
              <div className="font-semibold">{modal?.commission?.prospect_name}</div>
              <div className="text-xs text-[#4B5563]">
                {modal?.commission?.calc_notes} · {fmtMoney(modal?.commission?.amount)}
              </div>
            </div>
            <Textarea
              data-testid="comm-action-note"
              placeholder={
                modal?.kind === "flag"
                  ? "Required: why are you flagging this commission?"
                  : "Optional note"
              }
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              className="rounded-none"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setModal(null); setNote(""); }}
              className="rounded-none"
            >
              Cancel
            </Button>
            <Button
              data-testid="comm-action-confirm"
              onClick={performAction}
              disabled={modal?.kind === "flag" && !note.trim()}
              className={`rounded-none ${
                modal?.kind === "approve"
                  ? "bg-emerald-700 hover:bg-emerald-800"
                  : modal?.kind === "flag"
                  ? "bg-amber-600 hover:bg-amber-700"
                  : "bg-red-700 hover:bg-red-800"
              } text-white`}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
