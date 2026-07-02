import React, { useEffect, useRef, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, DownloadSimple, Paperclip, PencilSimple, Trash, Receipt } from "@phosphor-icons/react";
import { EXPENSE_CATEGORIES, INCOME_CATEGORIES, categoryLabel, money } from "@/lib/ledgerOptions";

const EMPTY = {
  type: "expense", amount: "", category: "supplies", date: new Date().toISOString().slice(0, 10),
  description: "", vendor: "", project_id: "", gig_id: "",
};

export const BookTransactions = () => {
  const [items, setItems] = useState(null);
  const [totals, setTotals] = useState(null);
  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState({ type: "", category: "", q: "", date_from: "", date_to: "" });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);
  const uploadTarget = useRef(null);

  const params = () => {
    const p = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => v && p.set(k, v));
    return p;
  };

  const load = () => {
    api.get(`/admin/ledger?${params()}`)
      .then((r) => { setItems(r.data.items); setTotals(r.data.totals); })
      .catch((e) => toast.error(getErr(e)));
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [filters]);

  useEffect(() => {
    api.get("/admin/ledger/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const openNew = () => { setForm(EMPTY); setEditingId(null); setDialogOpen(true); };
  const openEdit = (e) => {
    setForm({
      type: e.type, amount: String(e.amount), category: e.category, date: e.date,
      description: e.description || "", vendor: e.vendor || "",
      project_id: e.project_id || "", gig_id: e.gig_id || "",
    });
    setEditingId(e.entry_id);
    setDialogOpen(true);
  };

  const save = async (ev) => {
    ev.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, amount: parseFloat(form.amount) };
      if (!editingId) {
        if (!payload.vendor) delete payload.vendor;
        if (!payload.project_id) delete payload.project_id;
        if (!payload.gig_id) delete payload.gig_id;
        await api.post("/admin/ledger", payload);
        toast.success("Entry added");
      } else {
        await api.put(`/admin/ledger/${editingId}`, payload);
        toast.success("Entry updated");
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (e) => {
    if (!window.confirm(`Delete this ${e.type} of ${money(e.amount)}?`)) return;
    try {
      await api.delete(`/admin/ledger/${e.entry_id}`);
      toast.success("Entry deleted");
      load();
    } catch (er) {
      toast.error(getErr(er));
    }
  };

  const attachReceipt = (entryId) => {
    uploadTarget.current = entryId;
    fileRef.current?.click();
  };

  const onFilePicked = async (ev) => {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file || !uploadTarget.current) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      toast.info("Uploading receipt…");
      await api.post(`/admin/ledger/${uploadTarget.current}/receipt`, fd);
      toast.success("Receipt attached");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const cats = form.type === "expense" ? EXPENSE_CATEGORIES : INCOME_CATEGORIES;
  const filterCats = filters.type === "income" ? INCOME_CATEGORIES : filters.type === "expense" ? EXPENSE_CATEGORIES : [...EXPENSE_CATEGORIES, ...INCOME_CATEGORIES];

  return (
    <div data-testid="book-transactions">
      <input ref={fileRef} type="file" accept="image/*,application/pdf" className="hidden" onChange={onFilePicked} data-testid="book-receipt-input" />

      {/* Filters + actions */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select data-testid="book-filter-type" value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value, category: "" })} className="h-9 border border-[#E5E7EB] bg-white px-2 text-sm">
          <option value="">All types</option>
          <option value="expense">Expenses</option>
          <option value="income">Income</option>
        </select>
        <select data-testid="book-filter-category" value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} className="h-9 border border-[#E5E7EB] bg-white px-2 text-sm">
          <option value="">All categories</option>
          {filterCats.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <Input data-testid="book-filter-from" type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="h-9 w-36 rounded-none border-[#E5E7EB] text-xs" />
        <Input data-testid="book-filter-to" type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="h-9 w-36 rounded-none border-[#E5E7EB] text-xs" />
        <Input data-testid="book-filter-search" placeholder="Search description / vendor…" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className="h-9 w-56 rounded-none border-[#E5E7EB] text-sm" />
        <div className="ml-auto flex gap-2">
          <Button data-testid="book-export-csv" variant="outline" onClick={() => window.open(`${API}/admin/ledger/export?${params()}`, "_blank")} className="h-9 rounded-none border-[#030712] text-xs">
            <DownloadSimple size={14} className="mr-1" /> Export CSV
          </Button>
          <Button data-testid="book-add-entry" onClick={openNew} className="h-9 rounded-none bg-[#030712] text-xs text-white hover:bg-[#1f2937]">
            <Plus size={14} className="mr-1" /> Add entry
          </Button>
        </div>
      </div>

      {/* Filtered totals strip */}
      {totals && (
        <div className="mb-4 flex flex-wrap gap-x-6 gap-y-1 border border-[#E5E7EB] bg-[#F9FAFB] px-4 py-2 text-xs" data-testid="book-filtered-totals">
          <span>Income: <strong className="text-emerald-700">{money(totals.income)}</strong></span>
          <span>Expenses: <strong className="text-red-600">{money(totals.expenses)}</strong></span>
          <span>Net: <strong className={totals.net >= 0 ? "text-emerald-700" : "text-red-600"}>{money(totals.net)}</strong></span>
        </div>
      )}

      {/* Table */}
      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]" data-testid="book-empty">
          <Receipt size={28} weight="duotone" className="mx-auto mb-2 text-[#9CA3AF]" />
          No entries match. Add your first expense or income entry.
        </div>
      ) : (
        <div className="overflow-x-auto border border-[#E5E7EB] bg-white">
          <table className="w-full text-sm" data-testid="book-table">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">Date</th>
                <th className="px-3 py-3">Type</th>
                <th className="px-3 py-3">Category</th>
                <th className="px-3 py-3">Description</th>
                <th className="px-3 py-3">Linked to</th>
                <th className="px-3 py-3 text-right">Amount</th>
                <th className="px-3 py-3">Receipt</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.entry_id} data-testid={`book-row-${e.entry_id}`} className="border-t border-[#E5E7EB] hover:bg-[#F9FAFB]">
                  <td className="px-3 py-2.5 text-xs">{e.date}</td>
                  <td className="px-3 py-2.5">
                    <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${e.type === "income" ? "bg-emerald-600" : "bg-red-600"}`}>
                      {e.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-xs">{categoryLabel(e.category)}</td>
                  <td className="px-3 py-2.5 text-xs">
                    <div className="max-w-[240px] truncate font-semibold" title={e.description}>{e.description}</div>
                    {e.vendor && <div className="text-[#9CA3AF]">{e.vendor}</div>}
                    {e.recurring_id && <span className="text-[10px] uppercase text-violet-600">recurring</span>}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-[#4B5563]">
                    {e.project_title && <div>📁 {e.project_title}</div>}
                    {e.gig_title && <div>📌 {e.gig_title}</div>}
                    {!e.project_title && !e.gig_title && "—"}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-bold ${e.type === "income" ? "text-emerald-700" : "text-red-600"}`}>
                    {e.type === "income" ? "+" : "−"}{money(e.amount)}
                  </td>
                  <td className="px-3 py-2.5">
                    {e.receipt_path ? (
                      <button data-testid={`book-view-receipt-${e.entry_id}`} onClick={() => window.open(`${API}/files/${e.receipt_path}`, "_blank")} className="text-xs font-semibold text-[#0044FF] hover:underline">
                        View
                      </button>
                    ) : (
                      <button data-testid={`book-attach-receipt-${e.entry_id}`} onClick={() => attachReceipt(e.entry_id)} className="inline-flex items-center gap-1 text-xs text-[#4B5563] hover:text-[#030712]">
                        <Paperclip size={12} /> Attach
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex gap-2">
                      <button data-testid={`book-edit-${e.entry_id}`} onClick={() => openEdit(e)} className="text-[#4B5563] hover:text-[#030712]"><PencilSimple size={15} /></button>
                      <button data-testid={`book-delete-${e.entry_id}`} onClick={() => remove(e)} className="text-[#4B5563] hover:text-red-600"><Trash size={15} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Entry dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg rounded-none border-[#030712]" data-testid="book-entry-dialog">
          <DialogHeader>
            <DialogTitle className="font-display font-black">{editingId ? "Edit entry" : "Add entry"}</DialogTitle>
            <DialogDescription className="text-xs text-[#4B5563]">
              Record an expense or income entry in the ledger.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="flex gap-2">
              {["expense", "income"].map((t) => (
                <button
                  key={t} type="button" data-testid={`book-form-type-${t}`}
                  onClick={() => setForm({ ...form, type: t, category: t === "expense" ? "supplies" : "assignment_income" })}
                  className={`flex-1 border px-3 py-2 text-sm font-bold uppercase tracking-widest ${
                    form.type === t
                      ? t === "expense" ? "border-red-600 bg-red-600 text-white" : "border-emerald-600 bg-emerald-600 text-white"
                      : "border-[#E5E7EB] bg-white text-[#4B5563]"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-mono-label">Amount ($) *</Label>
                <Input data-testid="book-form-amount" required type="number" min="0.01" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" />
              </div>
              <div>
                <Label className="font-mono-label">Date *</Label>
                <Input data-testid="book-form-date" required type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" />
              </div>
            </div>
            <div>
              <Label className="font-mono-label">Category *</Label>
              <select data-testid="book-form-category" required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="mt-1 h-10 w-full border border-[#030712] bg-white px-2 text-sm">
                {cats.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <Label className="font-mono-label">Description *</Label>
              <Input data-testid="book-form-description" required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" placeholder={form.type === "expense" ? "e.g. Cleaning supplies restock" : "e.g. Payment for office deep clean"} />
            </div>
            <div>
              <Label className="font-mono-label">{form.type === "expense" ? "Vendor / payee" : "Payer / customer"} <span className="text-[#9CA3AF]">(optional)</span></Label>
              <Input data-testid="book-form-vendor" value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-mono-label">Link project <span className="text-[#9CA3AF]">(optional)</span></Label>
                <select data-testid="book-form-project" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="mt-1 h-10 w-full border border-[#E5E7EB] bg-white px-2 text-xs">
                  <option value="">— none —</option>
                  {(meta?.projects || []).map((p) => <option key={p.project_id} value={p.project_id}>{p.title}</option>)}
                </select>
              </div>
              <div>
                <Label className="font-mono-label">Link assignment <span className="text-[#9CA3AF]">(optional)</span></Label>
                <select data-testid="book-form-gig" value={form.gig_id} onChange={(e) => setForm({ ...form, gig_id: e.target.value })} className="mt-1 h-10 w-full border border-[#E5E7EB] bg-white px-2 text-xs">
                  <option value="">— none —</option>
                  {(meta?.gigs || []).map((g) => (
                    <option key={g.gig_id} value={g.gig_id}>
                      {g.title}{g.scheduled_at ? ` (${String(g.scheduled_at).slice(0, 10)})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="h-10 rounded-none border-[#030712]">Cancel</Button>
              <Button data-testid="book-form-save" type="submit" disabled={saving} className="h-10 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]">
                {saving ? "Saving…" : editingId ? "Save changes" : "Add entry"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};
