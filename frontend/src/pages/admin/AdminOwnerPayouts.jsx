import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import {
  CurrencyDollar,
  CheckSquare,
  Lock,
  Stack,
} from "@phosphor-icons/react";
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

export default function AdminOwnerPayouts() {
  const { user } = useAuth();
  const [resp, setResp] = useState(null);
  const [err, setErr] = useState("");
  const [paidModal, setPaidModal] = useState(null); // commission
  const [payoutForm, setPayoutForm] = useState({ payout_reference: "", payout_method: "check" });
  const [paid, setPaid] = useState(null); // status filter — paid history
  const [activeTab, setActiveTab] = useState("queue"); // queue | history

  const load = async () => {
    if (activeTab === "queue") {
      try {
        const { data } = await api.get("/owner/payouts/queue");
        setResp(data);
      } catch (e) {
        setErr(getErr(e));
      }
    } else {
      try {
        const { data } = await api.get("/pm/commissions?status=paid");
        setPaid(data.items || []);
      } catch (e) {
        setErr(getErr(e));
      }
    }
  };
  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [activeTab]);

  if (!user?.is_owner) {
    return (
      <div className="p-10" data-testid="not-owner-block">
        <div className="border border-red-200 bg-red-50 p-6 text-sm">
          <div className="font-semibold text-red-900 mb-1 flex items-center gap-2">
            <Lock size={14} /> Owner access required
          </div>
          <p>This page is only accessible to the Owner (admin@hcobcleaners.com). Program Managers can review the approval queue under <strong>Commissions</strong>.</p>
        </div>
      </div>
    );
  }

  const approveOne = async (c) => {
    try {
      await api.post(`/owner/payouts/${c.commission_id}/approve`);
      toast.success("Signed off — moved to payable queue");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const bulkApprove = async (group) => {
    if (!window.confirm(`Sign off on ${group.items.length} commissions totaling ${fmtMoney(group.total)} for ${group.va_name}?`)) return;
    try {
      const { data } = await api.post(`/owner/payouts/bulk-approve`, { va_user_id: group.va_user_id });
      toast.success(`Approved ${data.approved_count} · ${fmtMoney(data.total)}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const markPaid = async () => {
    if (!paidModal) return;
    try {
      await api.post(`/owner/payouts/${paidModal.commission_id}/mark-paid`, payoutForm);
      toast.success(`Marked paid · ${fmtMoney(paidModal.amount)}`);
      setPaidModal(null);
      setPayoutForm({ payout_reference: "", payout_method: "check" });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="admin-owner-payouts">
      <div className="mb-6">
        <div className="font-mono-label">Owner only</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Payout sign-off</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Final approval gate for every commission. Sign off individually or use the bulk button to clear a whole VA in one click.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          data-testid="tab-queue"
          onClick={() => setActiveTab("queue")}
          className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
            activeTab === "queue" ? "border-[#030712] bg-[#030712] text-white" : "border-[#E5E7EB] bg-white"
          }`}
        >
          Awaiting sign-off
        </button>
        <button
          data-testid="tab-history"
          onClick={() => setActiveTab("history")}
          className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
            activeTab === "history" ? "border-[#030712] bg-[#030712] text-white" : "border-[#E5E7EB] bg-white"
          }`}
        >
          Paid history
        </button>
        <button
          data-testid="tab-approved"
          onClick={() => setActiveTab("approved")}
          className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
            activeTab === "approved" ? "border-[#030712] bg-[#030712] text-white" : "border-[#E5E7EB] bg-white"
          }`}
        >
          Approved (ready to pay)
        </button>
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {activeTab === "queue" && (
        <>
          {!resp ? (
            <div className="font-mono-label">Loading…</div>
          ) : resp.items.length === 0 ? (
            <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
              No commissions awaiting sign-off. ✅
            </div>
          ) : (
            <div className="space-y-4">
              {/* Bulk per-VA cards */}
              {resp.by_va.map((g) => (
                <div
                  key={g.va_user_id}
                  data-testid={`bulk-group-${g.va_user_id}`}
                  className="border border-[#E5E7EB] bg-white"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3">
                    <div>
                      <div className="font-semibold">{g.va_name}</div>
                      <div className="text-xs text-[#4B5563]">
                        {g.items.length} commission{g.items.length !== 1 && "s"} · {fmtMoney(g.total)}
                      </div>
                    </div>
                    <Button
                      data-testid={`bulk-approve-${g.va_user_id}`}
                      onClick={() => bulkApprove(g)}
                      className="rounded-none bg-violet-700 hover:bg-violet-800 text-white"
                    >
                      <Stack size={14} className="mr-2" /> Bulk approve this VA (this week)
                    </Button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                          <th className="px-3 py-2">Lead</th>
                          <th className="px-3 py-2">Service</th>
                          <th className="px-3 py-2">Calc</th>
                          <th className="px-3 py-2 text-right">Amount</th>
                          <th className="px-3 py-2">PM approved</th>
                          <th className="px-3 py-2">Sign-off</th>
                        </tr>
                      </thead>
                      <tbody>
                        {g.items.map((c) => (
                          <tr
                            key={c.commission_id}
                            data-testid={`queue-row-${c.commission_id}`}
                            className="border-t border-[#E5E7EB]"
                          >
                            <td className="px-3 py-2">{c.prospect_name}</td>
                            <td className="px-3 py-2 capitalize">{c.service_type}</td>
                            <td className="px-3 py-2 text-xs text-[#4B5563]">{c.calc_notes}</td>
                            <td className="px-3 py-2 text-right font-mono font-semibold">{fmtMoney(c.amount)}</td>
                            <td className="px-3 py-2 text-xs text-[#4B5563]">
                              {(c.pm_action_at || "").slice(0, 10)}
                            </td>
                            <td className="px-3 py-2">
                              <button
                                data-testid={`signoff-${c.commission_id}`}
                                onClick={() => approveOne(c)}
                                className="inline-flex items-center gap-1 border border-violet-700 bg-white px-2 py-1 text-xs text-violet-700 hover:bg-violet-700 hover:text-white"
                              >
                                <CheckSquare size={11} weight="bold" /> Sign off
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === "approved" && <OwnerApprovedView markPaidCb={(c) => setPaidModal(c)} />}
      {activeTab === "history" && (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          {paid === null ? (
            <div className="p-6 font-mono-label">Loading…</div>
          ) : paid.length === 0 ? (
            <div className="p-10 text-center text-sm text-[#4B5563]">No commissions paid yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                  <th className="px-3 py-3">VA</th>
                  <th className="px-3 py-3">Lead</th>
                  <th className="px-3 py-3 text-right">Amount</th>
                  <th className="px-3 py-3">Method</th>
                  <th className="px-3 py-3">Ref</th>
                  <th className="px-3 py-3">Paid on</th>
                </tr>
              </thead>
              <tbody>
                {paid.map((c) => (
                  <tr key={c.commission_id} className="border-t border-[#E5E7EB]">
                    <td className="px-3 py-3 font-semibold">{c.va_name}</td>
                    <td className="px-3 py-3">{c.prospect_name}</td>
                    <td className="px-3 py-3 text-right font-mono font-semibold">{fmtMoney(c.amount)}</td>
                    <td className="px-3 py-3 capitalize">{c.payout_method}</td>
                    <td className="px-3 py-3 font-mono text-xs">{c.payout_reference || "—"}</td>
                    <td className="px-3 py-3 text-xs text-[#4B5563]">{(c.paid_at || "").slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <Dialog open={!!paidModal} onOpenChange={(o) => !o && setPaidModal(null)}>
        <DialogContent data-testid="mark-paid-dialog">
          <DialogHeader>
            <DialogTitle>Mark commission as paid</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="font-semibold">{paidModal?.prospect_name}</div>
              <div className="text-xs text-[#4B5563]">{paidModal?.calc_notes}</div>
              <div className="mt-2 font-display text-2xl font-black">{fmtMoney(paidModal?.amount)}</div>
            </div>
            <div>
              <Label className="font-mono-label">Method</Label>
              <select
                data-testid="paid-method"
                value={payoutForm.payout_method}
                onChange={(e) => setPayoutForm({ ...payoutForm, payout_method: e.target.value })}
                className="mt-2 h-10 w-full border border-[#030712] bg-white px-3 text-sm"
              >
                <option value="cash">Cash</option>
                <option value="venmo">Venmo</option>
                <option value="zelle">Zelle</option>
                <option value="check">Check</option>
                <option value="ach">ACH</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <Label className="font-mono-label">Reference (optional)</Label>
              <Input
                data-testid="paid-reference"
                placeholder="check #, venmo username, transaction ID..."
                value={payoutForm.payout_reference}
                onChange={(e) => setPayoutForm({ ...payoutForm, payout_reference: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPaidModal(null)} className="rounded-none">
              Cancel
            </Button>
            <Button
              data-testid="confirm-mark-paid"
              onClick={markPaid}
              className="rounded-none bg-emerald-700 text-white hover:bg-emerald-800"
            >
              <CurrencyDollar size={14} className="mr-2" /> Mark paid
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function OwnerApprovedView({ markPaidCb }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/pm/commissions?status=owner_approved");
        setItems(data.items || []);
      } catch (e) {
        setItems([]);
      }
    })();
  }, []);
  if (items === null) return <div className="font-mono-label">Loading…</div>;
  if (items.length === 0)
    return (
      <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
        Nothing approved and waiting to be paid right now.
      </div>
    );
  return (
    <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#F9FAFB]">
          <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
            <th className="px-3 py-3">VA</th>
            <th className="px-3 py-3">Lead</th>
            <th className="px-3 py-3 text-right">Amount</th>
            <th className="px-3 py-3">Signed off</th>
            <th className="px-3 py-3">Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.commission_id} className="border-t border-[#E5E7EB]" data-testid={`approved-row-${c.commission_id}`}>
              <td className="px-3 py-3 font-semibold">{c.va_name}</td>
              <td className="px-3 py-3">{c.prospect_name}</td>
              <td className="px-3 py-3 text-right font-mono font-semibold">{fmtMoney(c.amount)}</td>
              <td className="px-3 py-3 text-xs text-[#4B5563]">{(c.owner_action_at || "").slice(0, 10)}</td>
              <td className="px-3 py-3">
                <button
                  data-testid={`open-mark-paid-${c.commission_id}`}
                  onClick={() => markPaidCb(c)}
                  className="inline-flex items-center gap-1 border border-emerald-700 bg-white px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-700 hover:text-white"
                >
                  <CurrencyDollar size={11} weight="bold" /> Mark paid
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
