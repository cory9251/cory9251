import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Buildings, Plus, CurrencyDollar } from "@phosphor-icons/react";
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

export default function AdminCommercialAccounts() {
  const [items, setItems] = useState(null);
  const [vas, setVas] = useState([]);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);
  const [revOpen, setRevOpen] = useState(null);
  const [form, setForm] = useState({
    account_name: "",
    va_user_id: "",
    monthly_revenue: "",
    notes: "",
  });
  const [revForm, setRevForm] = useState({ revenue: "", period: "" });

  const load = async () => {
    try {
      const { data } = await api.get("/pm/commercial-accounts");
      setItems(data.items || []);
      const vaResp = await api.get("/pm/vas");
      setVas((vaResp.data.items || []).filter((u) => u.va_status === "approved"));
    } catch (e) {
      setErr(getErr(e));
    }
  };
  useEffect(() => {
    load(); // eslint-disable-line
  }, []);

  const create = async () => {
    try {
      const payload = { ...form, monthly_revenue: parseFloat(form.monthly_revenue || 0) };
      if (!payload.notes) delete payload.notes;
      await api.post("/pm/commercial-accounts", payload);
      toast.success("Commercial account created");
      setOpen(false);
      setForm({ account_name: "", va_user_id: "", monthly_revenue: "", notes: "" });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const logRevenue = async () => {
    try {
      const payload = { revenue: parseFloat(revForm.revenue || 0), period: revForm.period || undefined };
      await api.post(`/pm/commercial-accounts/${revOpen.account_id}/log-revenue`, payload);
      toast.success(`Logged $${payload.revenue} → 5% commission queued`);
      setRevOpen(null);
      setRevForm({ revenue: "", period: "" });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const totalRevenue = items?.filter((a) => a.active).reduce((s, a) => s + (a.monthly_revenue || 0), 0) || 0;

  return (
    <div className="p-6 md:p-10" data-testid="admin-commercial-accounts">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label">VA Commission Program</div>
          <h1 className="font-display text-4xl font-black tracking-tight">Commercial accounts</h1>
          <p className="mt-2 text-sm text-[#4B5563]">
            Recurring 5% commission per active account. Original VA retains rights for the lifetime of the account.
          </p>
        </div>
        <Button
          data-testid="add-commercial-btn"
          onClick={() => setOpen(true)}
          className="rounded-none bg-[#030712] hover:bg-[#1f2937] text-white"
        >
          <Plus size={16} className="mr-2" /> Add account
        </Button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="border border-[#E5E7EB] bg-white p-5">
          <div className="font-mono-label">Active accounts</div>
          <div className="mt-2 font-display text-3xl font-black">
            {items?.filter((a) => a.active).length ?? 0}
          </div>
        </div>
        <div className="border border-emerald-400 bg-white p-5">
          <div className="font-mono-label">Combined monthly revenue</div>
          <div className="mt-2 font-display text-3xl font-black text-emerald-700">{fmtMoney(totalRevenue)}</div>
        </div>
        <div className="border border-[#0044FF] bg-white p-5">
          <div className="font-mono-label">Commission per month (5%)</div>
          <div className="mt-2 font-display text-3xl font-black text-[#0044FF]">{fmtMoney(totalRevenue * 0.05)}</div>
        </div>
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          <Buildings size={36} weight="duotone" className="mx-auto text-[#4B5563] mb-3" />
          No commercial accounts yet.
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">Account</th>
                <th className="px-3 py-3">Original VA</th>
                <th className="px-3 py-3 text-right">Monthly revenue</th>
                <th className="px-3 py-3 text-right">VA monthly (5%)</th>
                <th className="px-3 py-3">Start</th>
                <th className="px-3 py-3">Active</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.account_id} className="border-t border-[#E5E7EB]" data-testid={`comm-acct-${a.account_id}`}>
                  <td className="px-3 py-3">
                    <div className="font-semibold">{a.account_name}</div>
                    {a.notes && <div className="text-xs text-[#4B5563]">{a.notes}</div>}
                  </td>
                  <td className="px-3 py-3 text-xs">{a.va_name}</td>
                  <td className="px-3 py-3 text-right font-mono">{fmtMoney(a.monthly_revenue)}</td>
                  <td className="px-3 py-3 text-right font-mono font-semibold text-emerald-700">
                    {fmtMoney((a.monthly_revenue || 0) * 0.05)}
                  </td>
                  <td className="px-3 py-3 text-xs text-[#4B5563]">{(a.start_date || "").slice(0, 10)}</td>
                  <td className="px-3 py-3">
                    {a.active ? (
                      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest bg-emerald-600 text-white">
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest bg-[#4B5563] text-white">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <button
                      data-testid={`log-revenue-${a.account_id}`}
                      onClick={() => setRevOpen(a)}
                      disabled={!a.active}
                      className="inline-flex items-center gap-1 border border-[#0044FF] bg-white px-2 py-1 text-xs text-[#0044FF] hover:bg-[#0044FF] hover:text-white disabled:opacity-50"
                    >
                      <CurrencyDollar size={11} weight="bold" /> Log month
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New commercial account</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="font-mono-label">Account name *</Label>
              <Input
                data-testid="comm-acct-name"
                value={form.account_name}
                onChange={(e) => setForm({ ...form, account_name: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Original VA *</Label>
              <select
                data-testid="comm-acct-va"
                value={form.va_user_id}
                onChange={(e) => setForm({ ...form, va_user_id: e.target.value })}
                className="mt-2 h-10 w-full border border-[#030712] bg-white px-3 text-sm"
              >
                <option value="">Select VA...</option>
                {vas.map((v) => (
                  <option key={v.user_id} value={v.user_id}>
                    {v.name} ({v.email})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label className="font-mono-label">Monthly revenue *</Label>
              <Input
                data-testid="comm-acct-revenue"
                type="number"
                min="0"
                step="0.01"
                value={form.monthly_revenue}
                onChange={(e) => setForm({ ...form, monthly_revenue: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Notes</Label>
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="rounded-none">
              Cancel
            </Button>
            <Button
              data-testid="comm-acct-create-confirm"
              onClick={create}
              disabled={!form.account_name || !form.va_user_id || !form.monthly_revenue}
              className="rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!revOpen} onOpenChange={(o) => !o && setRevOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Log monthly revenue · {revOpen?.account_name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="text-xs text-[#4B5563]">
              Logs a month of revenue against this commercial account → automatically creates a 5% commission for {revOpen?.va_name} (pending approval).
            </div>
            <div>
              <Label className="font-mono-label">Revenue collected *</Label>
              <Input
                data-testid="log-revenue-amount"
                type="number"
                step="0.01"
                value={revForm.revenue}
                onChange={(e) => setRevForm({ ...revForm, revenue: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Period (YYYY-MM, optional — defaults to this month)</Label>
              <Input
                data-testid="log-revenue-period"
                placeholder="2026-06"
                value={revForm.period}
                onChange={(e) => setRevForm({ ...revForm, period: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevOpen(null)} className="rounded-none">
              Cancel
            </Button>
            <Button
              data-testid="log-revenue-confirm"
              onClick={logRevenue}
              disabled={!revForm.revenue}
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              Log & queue commission
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
