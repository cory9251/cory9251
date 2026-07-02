import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Plus, Trash, ArrowsClockwise } from "@phosphor-icons/react";
import { EXPENSE_CATEGORIES, categoryLabel, money } from "@/lib/ledgerOptions";

const EMPTY = { amount: "", category: "software", description: "", vendor: "", day_of_month: "1" };

export const BookRecurring = () => {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.get("/admin/recurring-expenses").then((r) => setItems(r.data.items)).catch((e) => toast.error(getErr(e)));
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const add = async (ev) => {
    ev.preventDefault();
    setSaving(true);
    try {
      await api.post("/admin/recurring-expenses", {
        ...form,
        amount: parseFloat(form.amount),
        day_of_month: parseInt(form.day_of_month, 10),
        vendor: form.vendor || undefined,
      });
      toast.success("Recurring expense added — due entries auto-logged");
      setForm(EMPTY);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (r) => {
    try {
      await api.put(`/admin/recurring-expenses/${r.recurring_id}`, { active: !r.active });
      toast.success(r.active ? "Paused" : "Activated");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const remove = async (r) => {
    if (!window.confirm(`Delete recurring "${r.description}"? Already-logged entries stay in the ledger.`)) return;
    try {
      await api.delete(`/admin/recurring-expenses/${r.recurring_id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div data-testid="book-recurring">
      <div className="mb-4 flex items-center gap-2 text-sm text-[#4B5563]">
        <ArrowsClockwise size={16} weight="duotone" />
        Recurring expenses auto-log a ledger entry each month on the chosen day (e.g. software subscriptions, rent).
      </div>

      {/* Add form */}
      <form onSubmit={add} className="mb-6 grid grid-cols-2 items-end gap-3 border border-[#E5E7EB] bg-white p-5 md:grid-cols-6" data-testid="book-recurring-form">
        <div>
          <Label className="font-mono-label">Amount ($) *</Label>
          <Input data-testid="recurring-amount" required type="number" min="0.01" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" />
        </div>
        <div>
          <Label className="font-mono-label">Category *</Label>
          <select data-testid="recurring-category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="mt-1 h-10 w-full border border-[#030712] bg-white px-2 text-sm">
            {EXPENSE_CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <div className="col-span-2">
          <Label className="font-mono-label">Description *</Label>
          <Input data-testid="recurring-description" required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" placeholder="e.g. QuickBooks subscription" />
        </div>
        <div>
          <Label className="font-mono-label">Day of month *</Label>
          <Input data-testid="recurring-day" required type="number" min="1" max="28" value={form.day_of_month} onChange={(e) => setForm({ ...form, day_of_month: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" />
        </div>
        <Button data-testid="recurring-add" type="submit" disabled={saving} className="h-10 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]">
          <Plus size={14} className="mr-1" /> {saving ? "Adding…" : "Add"}
        </Button>
      </form>

      {/* List */}
      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-8 text-center text-sm text-[#4B5563]" data-testid="recurring-empty">
          No recurring expenses yet.
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm" data-testid="recurring-table">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Day</th>
                <th className="px-4 py-3">Last logged</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.recurring_id} data-testid={`recurring-row-${r.recurring_id}`} className="border-t border-[#E5E7EB]">
                  <td className="px-4 py-2.5">
                    <div className="font-semibold">{r.description}</div>
                    {r.vendor && <div className="text-xs text-[#9CA3AF]">{r.vendor}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-xs">{categoryLabel(r.category)}</td>
                  <td className="px-4 py-2.5 font-bold text-red-600">{money(r.amount)}</td>
                  <td className="px-4 py-2.5 text-xs">{r.day_of_month}<sup>th</sup></td>
                  <td className="px-4 py-2.5 text-xs text-[#4B5563]">{r.last_generated_period || "—"}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${r.active ? "bg-emerald-600" : "bg-[#9CA3AF]"}`}>
                      {r.active ? "Active" : "Paused"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <button data-testid={`recurring-toggle-${r.recurring_id}`} onClick={() => toggle(r)} className="text-xs font-semibold text-[#0044FF] hover:underline">
                        {r.active ? "Pause" : "Activate"}
                      </button>
                      <button data-testid={`recurring-delete-${r.recurring_id}`} onClick={() => remove(r)} className="text-[#4B5563] hover:text-red-600"><Trash size={15} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
