import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Check, Pause, Trash, UserPlus, Copy, Key } from "@phosphor-icons/react";
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

const STATUS_PILL = {
  pending: "bg-amber-500 text-white",
  approved: "bg-emerald-600 text-white",
  suspended: "bg-red-600 text-white",
  removed: "bg-[#4B5563] text-white",
};

function StatusPill({ status }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${STATUS_PILL[status] || STATUS_PILL.pending}`}
    >
      {status}
    </span>
  );
}

function genPassword() {
  return Math.random().toString(36).slice(2, 10) + "!";
}

export default function AdminVAs() {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    email: "",
    name: "",
    password: "",
    va_phone: "",
    va_address: "",
    auto_approve: true,
  });
  const [createdInfo, setCreatedInfo] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/pm/vas");
      setItems(data.items || []);
    } catch (e) {
      setErr(getErr(e));
    }
  };
  useEffect(() => {
    load(); // eslint-disable-line
  }, []);

  const filtered =
    filter === "all" ? items : items?.filter((u) => (u.va_status || "pending") === filter);

  const counts = items
    ? items.reduce((acc, u) => {
        const s = u.va_status || "pending";
        acc[s] = (acc[s] || 0) + 1;
        return acc;
      }, {})
    : {};

  const create = async () => {
    try {
      const payload = { ...form };
      if (!payload.va_phone) delete payload.va_phone;
      if (!payload.va_address) delete payload.va_address;
      const { data } = await api.post("/pm/vas", payload);
      toast.success("VA created");
      setCreatedInfo({ email: data.email, password: form.password });
      setCreateOpen(false);
      setForm({ email: "", name: "", password: "", va_phone: "", va_address: "", auto_approve: true });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const action = async (va, kind, note = "") => {
    try {
      if (kind === "approve") await api.post(`/pm/vas/${va.user_id}/approve`, { note });
      else if (kind === "suspend") await api.post(`/pm/vas/${va.user_id}/suspend`, { note });
      else if (kind === "remove") await api.delete(`/pm/vas/${va.user_id}`);
      toast.success(`VA ${kind}ed`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="admin-vas">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label">VA Commission Program</div>
          <h1 className="font-display text-4xl font-black tracking-tight">VA accounts</h1>
          <p className="mt-2 text-sm text-[#4B5563]">
            Approve pending VAs, suspend bad actors, or create new accounts directly.
          </p>
        </div>
        <Button
          data-testid="add-va-btn"
          onClick={() => {
            setForm({ email: "", name: "", password: genPassword(), va_phone: "", va_address: "", auto_approve: true });
            setCreateOpen(true);
          }}
          className="rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
        >
          <UserPlus size={16} className="mr-2" /> Add VA
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {["all", "pending", "approved", "suspended", "removed"].map((s) => (
          <button
            key={s}
            data-testid={`va-tab-${s}`}
            onClick={() => setFilter(s)}
            className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
              filter === s
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {s} ({s === "all" ? items?.length ?? 0 : counts[s] || 0})
          </button>
        ))}
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : !filtered || filtered.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          No VAs in this state.
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">Name</th>
                <th className="px-3 py-3">Email</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3 text-right">Leads</th>
                <th className="px-3 py-3 text-right">Conv.</th>
                <th className="px-3 py-3 text-right">Pending $</th>
                <th className="px-3 py-3 text-right">Paid $</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const earn = u.earnings_by_status || {};
                const pending = (earn.calculating || 0) + (earn.pending_approval || 0) + (earn.pm_approved || 0);
                const approved = earn.owner_approved || 0;
                const paid = earn.paid || 0;
                return (
                  <tr
                    key={u.user_id}
                    data-testid={`va-row-${u.user_id}`}
                    className="border-t border-[#E5E7EB] hover:bg-[#F9FAFB]"
                  >
                    <td className="px-3 py-3 font-semibold">{u.name}</td>
                    <td className="px-3 py-3 text-xs">{u.email}</td>
                    <td className="px-3 py-3"><StatusPill status={u.va_status || "pending"} /></td>
                    <td className="px-3 py-3 text-right font-mono">{u.lead_count}</td>
                    <td className="px-3 py-3 text-right font-mono">{u.conversion_rate}%</td>
                    <td className="px-3 py-3 text-right font-mono">{fmtMoney(pending)}</td>
                    <td className="px-3 py-3 text-right font-mono font-semibold">{fmtMoney(paid + approved)}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {u.va_status === "pending" && (
                          <button
                            data-testid={`va-approve-${u.user_id}`}
                            onClick={() => action(u, "approve")}
                            className="inline-flex items-center gap-1 border border-emerald-700 bg-white px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-700 hover:text-white"
                          >
                            <Check size={11} weight="bold" /> Approve
                          </button>
                        )}
                        {u.va_status === "approved" && (
                          <button
                            data-testid={`va-suspend-${u.user_id}`}
                            onClick={() => action(u, "suspend")}
                            className="inline-flex items-center gap-1 border border-amber-600 bg-white px-2 py-1 text-xs text-amber-700 hover:bg-amber-600 hover:text-white"
                          >
                            <Pause size={11} weight="bold" /> Suspend
                          </button>
                        )}
                        {u.va_status === "suspended" && (
                          <button
                            data-testid={`va-reinstate-${u.user_id}`}
                            onClick={() => action(u, "approve")}
                            className="inline-flex items-center gap-1 border border-emerald-700 bg-white px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-700 hover:text-white"
                          >
                            <Check size={11} weight="bold" /> Reinstate
                          </button>
                        )}
                        {u.va_status !== "removed" && (
                          <>
                            <button
                              data-testid={`va-reset-pw-${u.user_id}`}
                              onClick={async () => {
                                if (!window.confirm(`Reset password for ${u.name}? All their sessions will be terminated.`)) return;
                                try {
                                  const { data } = await api.post(`/admin/users/${u.user_id}/reset-password`, {});
                                  setCreatedInfo({ email: data.email, password: data.new_password });
                                } catch (e) {
                                  toast.error(getErr(e));
                                }
                              }}
                              className="inline-flex items-center gap-1 border border-[#0044FF] bg-white px-2 py-1 text-xs text-[#0044FF] hover:bg-[#0044FF] hover:text-white"
                            >
                              <Key size={11} weight="bold" /> Reset PW
                            </button>
                            <button
                              data-testid={`va-remove-${u.user_id}`}
                              onClick={() => {
                                if (!window.confirm(`Remove ${u.name}? They lose access immediately.`)) return;
                                action(u, "remove");
                              }}
                              className="inline-flex items-center gap-1 border border-red-700 bg-white px-2 py-1 text-xs text-red-700 hover:bg-red-700 hover:text-white"
                            >
                              <Trash size={11} weight="bold" /> Remove
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create VA dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent data-testid="create-va-dialog">
          <DialogHeader>
            <DialogTitle>Add a new VA</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="font-mono-label">Full name *</Label>
              <Input
                data-testid="create-va-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Email *</Label>
              <Input
                data-testid="create-va-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="mt-2 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Temp password *</Label>
              <div className="mt-2 flex items-center gap-2">
                <Input
                  data-testid="create-va-password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="h-10 rounded-none border-[#030712] flex-1"
                />
                <button
                  onClick={() => setForm({ ...form, password: genPassword() })}
                  className="h-10 border border-[#030712] px-3 text-xs hover:bg-[#030712] hover:text-white"
                >
                  Generate
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-mono-label">Phone (optional)</Label>
                <Input
                  value={form.va_phone}
                  onChange={(e) => setForm({ ...form, va_phone: e.target.value })}
                  className="mt-2 h-10 rounded-none border-[#030712]"
                />
              </div>
              <div>
                <Label className="font-mono-label">Address (optional)</Label>
                <Input
                  value={form.va_address}
                  onChange={(e) => setForm({ ...form, va_address: e.target.value })}
                  className="mt-2 h-10 rounded-none border-[#030712]"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                data-testid="create-va-autoapprove"
                checked={form.auto_approve}
                onChange={(e) => setForm({ ...form, auto_approve: e.target.checked })}
              />
              Auto-approve (skip pending state)
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} className="rounded-none">
              Cancel
            </Button>
            <Button
              data-testid="create-va-confirm"
              onClick={create}
              disabled={!form.name || !form.email || !form.password}
              className="rounded-none bg-[#030712] hover:bg-[#1f2937] text-white"
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Created info modal */}
      <Dialog open={!!createdInfo} onOpenChange={(o) => !o && setCreatedInfo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>VA account created</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <p>Share these credentials securely with the new VA. They&apos;ll be required to change the password after first login.</p>
            <div className="border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="text-xs text-[#4B5563]">Email</div>
              <div className="font-mono">{createdInfo?.email}</div>
            </div>
            <div className="border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="text-xs text-[#4B5563]">Password</div>
              <div className="flex items-center justify-between">
                <span className="font-mono">{createdInfo?.password}</span>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(createdInfo?.password || "");
                    toast.success("Copied");
                  }}
                  className="inline-flex items-center gap-1 border border-[#030712] px-2 py-1 text-xs hover:bg-[#030712] hover:text-white"
                >
                  <Copy size={11} /> Copy
                </button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setCreatedInfo(null)} className="rounded-none bg-[#030712] text-white">
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
