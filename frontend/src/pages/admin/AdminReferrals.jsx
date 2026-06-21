import React, { useEffect, useMemo, useState } from "react";
import {
  Handshake,
  CurrencyDollar,
  MapPin,
  ArrowsClockwise,
  CheckCircle,
  WarningCircle,
  CaretRight,
  X,
  Receipt,
} from "@phosphor-icons/react";
import { api, getErr } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const STATUS_FLOW = [
  "submitted",
  "under_review",
  "quoted",
  "scheduled",
  "in_progress",
  "completed",
  "invoiced",
  "paid",
  "commission_released",
];
const TERMINAL = ["void", "self_fulfilled"];

const STATUS_LABEL = {
  submitted: "Submitted",
  under_review: "Under review",
  quoted: "Quoted",
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  invoiced: "Invoiced",
  paid: "Customer paid",
  commission_released: "Commission released",
  void: "Voided",
  self_fulfilled: "Self-fulfilled",
};

const STATUS_TONE = {
  submitted: "bg-[#F0F4FF] text-[#0044FF] border-[#0044FF]",
  under_review: "bg-[#F0F4FF] text-[#0044FF] border-[#0044FF]",
  quoted: "bg-violet-50 text-violet-700 border-violet-500",
  scheduled: "bg-violet-50 text-violet-700 border-violet-500",
  in_progress: "bg-amber-50 text-amber-700 border-amber-500",
  completed: "bg-amber-50 text-amber-700 border-amber-500",
  invoiced: "bg-amber-50 text-amber-700 border-amber-500",
  paid: "bg-[#D1FAE5] text-[#065F46] border-[#10B981]",
  commission_released: "bg-[#D1FAE5] text-[#065F46] border-[#10B981]",
  void: "bg-[#FEE2E2] text-[#991B1B] border-[#EF4444]",
  self_fulfilled: "bg-[#FEE2E2] text-[#991B1B] border-[#EF4444]",
};

export default function AdminReferrals() {
  const [board, setBoard] = useState(null);
  const [activeStatus, setActiveStatus] = useState(null); // null = all
  const [activeRef, setActiveRef] = useState(null);
  const [err, setErr] = useState("");
  const [rate, setRate] = useState(0.1);
  const [editingRate, setEditingRate] = useState(false);

  const load = async () => {
    try {
      const [r, s] = await Promise.all([
        api.get("/admin/referrals" + (activeStatus ? `?status=${activeStatus}` : "")),
        api.get("/admin/referrals/settings"),
      ]);
      setBoard(r.data);
      setRate(s.data.commission_rate);
      // Clear any stale error from a previous failed load so the red
      // banner doesn't linger after a successful refresh.
      setErr("");
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, [activeStatus]);

  const items = board?.items || [];

  return (
    <div className="p-6 md:p-10" data-testid="admin-referrals-page">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label flex items-center gap-1.5">
            <Handshake size={14} weight="fill" /> Lead center · Network referrals
          </div>
          <h1 className="font-display text-4xl font-black tracking-tight">
            Network referrals
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
            Leads spotted by contractors out in the field. Quote them, dispatch,
            and mark paid — the platform handles commission accrual.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <CommissionRateEditor
            rate={rate}
            editing={editingRate}
            setEditing={setEditingRate}
            onSave={async (v) => {
              try {
                await api.put("/admin/referrals/settings", { commission_rate: v });
                setRate(v);
                setEditingRate(false);
                toast.success("Commission rate updated");
              } catch (e) {
                toast.error(getErr(e));
              }
            }}
          />
          <Button
            data-testid="refresh-referrals"
            variant="outline"
            onClick={load}
            className="h-10 rounded-none border-[#030712]"
          >
            <ArrowsClockwise size={14} className="mr-2" /> Refresh
          </Button>
        </div>
      </div>

      {/* Status filter pills */}
      <div className="mb-6 flex flex-wrap gap-2" data-testid="status-filter">
        <FilterPill
          label={`All (${items.length})`}
          active={activeStatus === null}
          onClick={() => setActiveStatus(null)}
          testid="filter-all"
        />
        {[...STATUS_FLOW, ...TERMINAL].map((s) => {
          const n = board?.counts?.[s] || 0;
          if (n === 0 && activeStatus !== s) return null;
          return (
            <FilterPill
              key={s}
              label={`${STATUS_LABEL[s]} (${n})`}
              active={activeStatus === s}
              onClick={() => setActiveStatus(activeStatus === s ? null : s)}
              testid={`filter-${s}`}
            />
          );
        })}
      </div>

      {err && (
        <div className="mb-4 border border-[#EF4444] bg-[#FEE2E2] p-3 text-sm text-[#991B1B]">
          {err}
        </div>
      )}

      {/* List */}
      {items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          {activeStatus
            ? `No referrals in "${STATUS_LABEL[activeStatus]}" status.`
            : "No referrals yet. Approved workers can submit from /crew/refer."}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((r) => (
            <AdminReferralRow
              key={r.referral_id}
              r={r}
              onOpen={() => setActiveRef(r)}
            />
          ))}
        </div>
      )}

      {activeRef && (
        <ReferralDetailDrawer
          referralId={activeRef.referral_id}
          onClose={() => setActiveRef(null)}
          onUpdated={() => {
            setActiveRef(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function FilterPill({ label, active, onClick, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={`inline-flex items-center border px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors ${
        active
          ? "border-[#030712] bg-[#030712] text-white"
          : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
      }`}
    >
      {label}
    </button>
  );
}

function CommissionRateEditor({ rate, editing, setEditing, onSave }) {
  const [draft, setDraft] = useState(rate * 100);
  useEffect(() => {
    setDraft(rate * 100);
  }, [rate]);
  if (!editing) {
    return (
      <button
        type="button"
        data-testid="edit-commission-rate"
        onClick={() => setEditing(true)}
        className="flex flex-col items-start border border-[#E5E7EB] bg-white px-4 py-2 hover:border-[#030712]"
      >
        <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          Commission rate
        </div>
        <div className="font-display text-xl font-black">
          {(rate * 100).toFixed(0)}%
        </div>
      </button>
    );
  }
  return (
    <div className="flex items-end gap-2 border border-[#030712] bg-white px-3 py-2">
      <div>
        <Label className="font-mono-label">Rate (%)</Label>
        <Input
          data-testid="commission-rate-input"
          type="number"
          step="0.5"
          min="0"
          max="100"
          value={draft}
          onChange={(e) => setDraft(Number(e.target.value))}
          className="mt-1 h-9 w-24 rounded-none border-[#030712]"
        />
      </div>
      <Button
        data-testid="save-commission-rate"
        onClick={() => onSave(draft / 100)}
        className="h-9 rounded-none bg-[#0044FF] text-white"
      >
        Save
      </Button>
      <Button
        variant="ghost"
        onClick={() => setEditing(false)}
        className="h-9 rounded-none"
      >
        Cancel
      </Button>
    </div>
  );
}

function AdminReferralRow({ r, onOpen }) {
  const tone = STATUS_TONE[r.status] || "bg-[#E5E7EB] text-[#374151] border-[#E5E7EB]";
  return (
    <button
      type="button"
      onClick={onOpen}
      data-testid={`admin-referral-row-${r.referral_id}`}
      className="flex w-full items-start gap-4 border border-[#E5E7EB] bg-white p-4 text-left transition-all hover:border-[#030712] hover:shadow-sm"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 border px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${tone}`}
          >
            {STATUS_LABEL[r.status] || r.status}
          </span>
          <span className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
            {r.service_category}
          </span>
          {r.intent === "for_self" && (
            <span className="inline-flex items-center gap-1 border border-[#F59E0B] bg-[#FFFBEB] px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-[#92400E]">
              <WarningCircle size={10} weight="fill" /> Wants to take it
            </span>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2 font-display text-base font-bold">
          <MapPin size={14} /> {r.property_address}
        </div>
        <div className="mt-1 line-clamp-2 text-sm text-[#4B5563]">
          {r.opportunity_description}
        </div>
        <div className="mt-2 flex items-center gap-3 font-mono-label text-[10px] tracking-widest text-[#4B5563]">
          <span>From: {r.referring_contractor_name || r.referring_contractor_id}</span>
          {r.contact?.phone && <span>· {r.contact.phone}</span>}
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        {r.quoted_amount > 0 && (
          <div className="text-right">
            <div className="font-mono-label text-[10px] text-[#4B5563]">Quote</div>
            <div className="font-display text-lg font-bold text-[#0044FF]">
              ${Number(r.quoted_amount).toLocaleString("en-US")}
            </div>
          </div>
        )}
        {r.commission_amount > 0 && (
          <div className="text-right">
            <div className="font-mono-label text-[10px] text-[#4B5563]">Commission</div>
            <div className="font-display text-lg font-bold text-[#10B981]">
              ${Number(r.commission_amount).toLocaleString("en-US")}
            </div>
          </div>
        )}
        <CaretRight size={16} className="mt-1 text-[#9CA3AF]" />
      </div>
    </button>
  );
}

function ReferralDetailDrawer({ referralId, onClose, onUpdated }) {
  const [r, setR] = useState(null);
  const [updating, setUpdating] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    api
      .get(`/admin/referrals/${referralId}`)
      .then((res) => {
        setR(res.data);
        setForm({
          status: res.data.status,
          quoted_amount: res.data.quoted_amount || "",
          assigned_contractor_id: res.data.assigned_contractor_id || "",
          linked_invoice_id: res.data.linked_invoice_id || "",
          admin_notes: res.data.admin_notes || "",
        });
      })
      .catch((e) => toast.error(getErr(e)));
  }, [referralId]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setUpdating(true);
    try {
      const payload = { ...form };
      if (payload.quoted_amount === "" || payload.quoted_amount == null) {
        delete payload.quoted_amount;
      } else {
        payload.quoted_amount = Number(payload.quoted_amount);
      }
      await api.patch(`/admin/referrals/${referralId}`, payload);
      toast.success("Updated");
      onUpdated();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setUpdating(false);
    }
  };

  if (!r) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        onClick={onClose}
      >
        <div className="bg-white p-6">Loading…</div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-end bg-black/40 backdrop-blur-sm sm:items-stretch"
      onClick={onClose}
      data-testid="referral-detail-drawer"
    >
      <div
        className="flex w-full max-w-xl flex-col border border-[#030712] bg-white shadow-2xl sm:max-h-screen"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#030712] bg-[#030712] px-5 py-3 text-white">
          <div>
            <div className="font-display text-lg font-bold">Referral detail</div>
            <div className="font-mono-label text-[10px] text-white/70">
              {r.referral_id}
            </div>
          </div>
          <button
            data-testid="close-detail"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center text-white hover:bg-white/10"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5 text-sm">
          {/* Read-only details */}
          <div>
            <div className="font-mono-label">Referred by</div>
            <div className="font-bold">
              {r.referring_contractor_name} · {r.referring_contractor_id}
            </div>
            {r.intent === "for_self" && (
              <div className="mt-1 inline-flex items-center gap-1 border border-[#F59E0B] bg-[#FFFBEB] px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-[#92400E]">
                Wants to take it themselves
              </div>
            )}
          </div>
          <div>
            <div className="font-mono-label">Address</div>
            <div>{r.property_address}</div>
          </div>
          <div>
            <div className="font-mono-label">What they spotted</div>
            <div className="whitespace-pre-wrap">{r.opportunity_description}</div>
          </div>
          {(r.contact?.name || r.contact?.phone || r.contact?.email) && (
            <div>
              <div className="font-mono-label">Contact</div>
              <div className="text-[#0044FF]">
                {r.contact.name && <div>{r.contact.name}</div>}
                {r.contact.phone && (
                  <a href={`tel:${r.contact.phone}`} className="hover:underline">
                    {r.contact.phone}
                  </a>
                )}
                {r.contact.email && (
                  <a href={`mailto:${r.contact.email}`} className="block hover:underline">
                    {r.contact.email}
                  </a>
                )}
              </div>
            </div>
          )}

          <hr className="border-[#E5E7EB]" />

          {/* Editable */}
          <div>
            <Label className="font-mono-label">Status</Label>
            <select
              data-testid="admin-set-status"
              value={form.status || ""}
              onChange={(e) => set("status", e.target.value)}
              className="mt-1 h-10 w-full rounded-none border border-[#030712] bg-white px-3 text-sm"
            >
              {[...STATUS_FLOW, ...TERMINAL].map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="font-mono-label">Quoted ($)</Label>
              <Input
                data-testid="admin-set-quoted"
                type="number"
                value={form.quoted_amount}
                onChange={(e) => set("quoted_amount", e.target.value)}
                className="mt-1 h-10 rounded-none border-[#030712]"
              />
            </div>
            <div>
              <Label className="font-mono-label">Square invoice ID</Label>
              <Input
                data-testid="admin-set-invoice"
                value={form.linked_invoice_id}
                onChange={(e) => set("linked_invoice_id", e.target.value)}
                placeholder="optional"
                className="mt-1 h-10 rounded-none border-[#030712]"
              />
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Assigned contractor (user_id)</Label>
            <Input
              data-testid="admin-set-assigned"
              value={form.assigned_contractor_id}
              onChange={(e) => set("assigned_contractor_id", e.target.value)}
              placeholder="user_xxxxx"
              className="mt-1 h-10 rounded-none border-[#030712]"
            />
            <div className="mt-1 font-mono-label text-[9px] text-[#4B5563]">
              If this matches the referring contractor, status auto-flips to
              &ldquo;Self-fulfilled&rdquo; and the commission is voided.
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Admin notes</Label>
            <Textarea
              data-testid="admin-set-notes"
              value={form.admin_notes}
              onChange={(e) => set("admin_notes", e.target.value)}
              rows={3}
              className="mt-1 rounded-none border-[#030712]"
            />
          </div>

          {/* Commission roll-up */}
          {(r.commission_amount > 0 || r.commission_status !== "pending") && (
            <div className="border border-[#10B981] bg-[#D1FAE5] p-3">
              <div className="font-mono-label flex items-center gap-1.5 text-[#065F46]">
                <Receipt size={12} weight="fill" /> Commission
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                <div className="font-display text-2xl font-black text-[#065F46]">
                  ${Number(r.commission_amount || 0).toLocaleString("en-US")}
                </div>
                <div className="font-mono-label text-[10px] uppercase tracking-widest text-[#065F46]">
                  {r.commission_status}
                </div>
              </div>
              {r.commission_paid_date && (
                <div className="mt-1 text-[11px] text-[#065F46]">
                  Released {new Date(r.commission_paid_date).toLocaleDateString()}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[#E5E7EB] bg-white p-4">
          <Button variant="outline" onClick={onClose} className="rounded-none border-[#030712]">
            Close
          </Button>
          <Button
            data-testid="save-referral-update"
            onClick={save}
            disabled={updating}
            className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            <CheckCircle size={14} className="mr-1" />
            {updating ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
