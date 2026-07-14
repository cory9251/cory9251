import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  CheckCircle,
  XCircle,
  ArrowCounterClockwise,
  Plus,
  Trash,
  Toolbox,
  ClockCounterClockwise,
  Wrench,
  ChartBar,
  IdentificationCard,
} from "@phosphor-icons/react";

const TABS = [
  { key: "queue", label: "Review Queue", icon: ClockCounterClockwise },
  { key: "manager", label: "Trade Manager", icon: Wrench },
  { key: "metrics", label: "Metrics", icon: ChartBar },
];

const STATUS_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "returned", label: "Returned" },
  { value: "verified", label: "Verified" },
  { value: "incomplete", label: "Incomplete" },
  { value: "all", label: "All" },
];

export default function AdminTrades() {
  const [tab, setTab] = useState("queue");
  return (
    <div data-testid="admin-trades">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">Specialist verification</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">Trades</h1>
      </div>
      <div className="flex flex-wrap gap-1 border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`trades-tab-${t.key}`}
            onClick={() => setTab(t.key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-widest ${
              tab === t.key
                ? "bg-[#030712] text-white"
                : "border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
            }`}
          >
            <t.icon size={13} weight="duotone" /> {t.label}
          </button>
        ))}
      </div>
      <div className="px-6 py-6 md:px-10">
        {tab === "queue" && <ReviewQueue />}
        {tab === "manager" && <TradeManager />}
        {tab === "metrics" && <Metrics />}
      </div>
    </div>
  );
}

// ============================================================================
// Review Queue
// ============================================================================
function ReviewQueue() {
  const [status, setStatus] = useState("pending");
  const [claims, setClaims] = useState([]);
  const [busyKey, setBusyKey] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/trade-claims", { params: { status } });
      setClaims(data.claims || []);
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [status]);

  const act = async (c, action) => {
    const key = `${c.worker.user_id}:${c.trade}`;
    let body = {};
    if (action === "return") {
      const note = window.prompt("Return note for the worker (e.g. \"photo unclear — retake showing the machine's ID plate\"):");
      if (note === null) return;
      body = { note };
    }
    if (action === "grace") {
      const days = window.prompt("Extend grace by how many days?", "30");
      if (days === null) return;
      body = { days: parseInt(days || "30", 10) };
    }
    setBusyKey(key);
    try {
      await api.post(`/admin/trade-claims/${c.worker.user_id}/${c.trade}/${action === "return" ? "return" : action}`, body);
      toast.success(action === "verify" ? "Trade verified" : action === "return" ? "Returned to worker" : "Grace extended");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div data-testid="trades-review-queue">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {STATUS_OPTIONS.map((s) => (
          <button
            key={s.value}
            data-testid={`claims-status-${s.value}`}
            onClick={() => setStatus(s.value)}
            className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest ${
              status === s.value ? "bg-[#0044FF] text-white" : "border border-[#E5E7EB] text-[#4B5563]"
            }`}
          >
            {s.label}
          </button>
        ))}
        <span className="ml-auto font-mono-label">{claims.length} claims</span>
      </div>

      {claims.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] p-10 text-center text-sm text-[#4B5563]" data-testid="claims-empty">
          No {status !== "all" ? status : ""} claims.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {claims.map((c) => {
            const key = `${c.worker.user_id}:${c.trade}`;
            const checked = Object.entries(c.checklist || {}).filter(([, v]) => v).map(([k]) => k);
            return (
              <div key={key} data-testid={`claim-card-${c.trade}-${c.worker.user_id}`} className="border border-[#E5E7EB] bg-white p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-display text-lg font-black tracking-tight">{c.label}</div>
                    <Link to={`/ops/workers/${c.worker.user_id}`} className="text-sm font-semibold text-[#0044FF] hover:underline" data-testid={`claim-worker-link-${c.worker.user_id}`}>
                      {c.worker.name || c.worker.email}
                    </Link>
                    <div className="text-[11px] text-[#4B5563]">
                      {c.worker.phone || "no phone"} · ZIP {c.worker.zip_code || "—"}
                      {c.submitted_at && <> · submitted {new Date(c.submitted_at).toLocaleDateString()}</>}
                    </div>
                  </div>
                  <StatusPill status={c.status} />
                </div>

                {c.grace_until && (
                  <div className="mt-2 inline-flex items-center gap-1 bg-[#FFFBEB] px-2 py-1 text-[10px] font-bold text-[#92400E]" data-testid={`claim-grace-${c.trade}`}>
                    <ClockCounterClockwise size={11} /> Grace until {new Date(c.grace_until).toLocaleDateString()}
                  </div>
                )}

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <div className="font-mono-label mb-2">Equipment checklist</div>
                    <ul className="space-y-1.5">
                      {(c.checklist_items || []).map((it) => {
                        const owned = checked.includes(it.key);
                        return (
                          <li key={it.key} className="flex items-start gap-1.5 text-xs">
                            {owned ? (
                              <CheckCircle size={14} weight="fill" className="mt-0.5 shrink-0 text-[#10B981]" />
                            ) : (
                              <XCircle size={14} className="mt-0.5 shrink-0 text-[#D1D5DB]" />
                            )}
                            <span className={owned ? "" : "text-[#9CA3AF]"}>
                              {it.label}
                              {owned && c.detail_fields?.[it.key] && (
                                <span className="block font-semibold text-[#0044FF]">{c.detail_fields[it.key]}</span>
                              )}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                    {c.licensed && (
                      <div className="mt-2 flex items-center gap-1.5 text-xs">
                        <IdentificationCard size={14} className="text-[#0044FF]" />
                        License #: <strong>{c.license_number || "—"}</strong>
                      </div>
                    )}
                    <div className="mt-2 text-xs text-[#4B5563]">
                      Experience: <strong>{{ none: "None", "0_1_yr": "<1 yr", "1_3_yr": "1–3 yrs", "3_plus_yr": "3+ yrs" }[c.experience] || "—"}</strong>
                    </div>
                    {c.completeness_errors?.length > 0 && (
                      <div className="mt-2 bg-[#FFFBEB] p-2 text-[11px] text-[#92400E]">
                        {c.completeness_errors.join(" · ")}
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="font-mono-label mb-2">Photo proof ({(c.photos || []).length})</div>
                    {(c.photos || []).length ? (
                      <div className="flex flex-wrap gap-2">
                        {c.photos.map((p) => <AdminThumb key={p} path={p} />)}
                      </div>
                    ) : (
                      <div className="text-xs text-[#9CA3AF]">No photos</div>
                    )}
                    {c.admin_note && (
                      <div className="mt-2 text-[11px] text-[#991B1B]">Last note: {c.admin_note}</div>
                    )}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2 border-t border-[#E5E7EB] pt-3">
                  {c.status !== "verified" && (
                    <Button
                      data-testid={`claim-verify-${c.trade}-${c.worker.user_id}`}
                      onClick={() => act(c, "verify")}
                      disabled={busyKey === key}
                      className="h-9 rounded-none bg-[#10B981] px-4 text-xs font-bold text-white hover:bg-[#059669]"
                    >
                      <CheckCircle size={14} weight="fill" className="mr-1" /> Verify
                    </Button>
                  )}
                  {c.status !== "verified" && (
                    <Button
                      data-testid={`claim-return-${c.trade}-${c.worker.user_id}`}
                      onClick={() => act(c, "return")}
                      disabled={busyKey === key}
                      variant="outline"
                      className="h-9 rounded-none border-[#EF4444] px-4 text-xs font-bold text-[#EF4444]"
                    >
                      <ArrowCounterClockwise size={14} className="mr-1" /> Return w/ note
                    </Button>
                  )}
                  {c.status !== "verified" && (
                    <Button
                      data-testid={`claim-grace-btn-${c.trade}-${c.worker.user_id}`}
                      onClick={() => act(c, "grace")}
                      disabled={busyKey === key}
                      variant="outline"
                      className="h-9 rounded-none border-[#F59E0B] px-4 text-xs font-bold text-[#92400E]"
                    >
                      Extend grace
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const m = {
    incomplete: "bg-[#F59E0B]",
    pending: "bg-[#0044FF]",
    verified: "bg-[#10B981]",
    returned: "bg-[#EF4444]",
  }[status] || "bg-[#4B5563]";
  return (
    <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white ${m}`}>
      {status}
    </span>
  );
}

function AdminThumb({ path }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, { credentials: "include" });
        if (!res.ok) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        setSrc(url);
      } catch {}
    })();
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (!src) return <div className="h-24 w-24 bg-[#F3F4F6]" />;
  return (
    <a href={src} target="_blank" rel="noreferrer">
      <img src={src} alt="proof" className="h-24 w-24 border border-[#E5E7EB] object-cover" />
    </a>
  );
}

// ============================================================================
// Trade Manager
// ============================================================================
function TradeManager() {
  const [trades, setTrades] = useState([]);
  const [editing, setEditing] = useState(null); // trade_id | "new"

  const load = async () => {
    try {
      const { data } = await api.get("/admin/trades");
      setTrades(data.trades || []);
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  useEffect(() => { load(); }, []);

  return (
    <div data-testid="trades-manager">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-[#4B5563]">
          Edit checklists here — changes apply to new signups immediately, no code change.
        </div>
        <Button
          data-testid="new-trade-btn"
          onClick={() => setEditing("new")}
          className="h-9 rounded-none bg-[#030712] px-4 text-xs font-bold text-white"
        >
          <Plus size={14} className="mr-1" /> New trade
        </Button>
      </div>

      {editing === "new" && (
        <TradeEditor
          trade={null}
          onDone={() => { setEditing(null); load(); }}
          onCancel={() => setEditing(null)}
        />
      )}

      <div className="space-y-3">
        {trades.map((t) =>
          editing === t.trade_id ? (
            <TradeEditor
              key={t.trade_id}
              trade={t}
              onDone={() => { setEditing(null); load(); }}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <div key={t.trade_id} data-testid={`trade-def-${t.trade_id}`} className="flex items-center gap-3 border border-[#E5E7EB] bg-white p-4">
              <div className="grid h-10 w-10 place-items-center bg-[#F0F4FF] text-[#0044FF]">
                <Toolbox size={20} weight="duotone" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-display text-base font-bold">
                  {t.label}
                  {!t.active && <span className="ml-2 bg-[#4B5563] px-1.5 py-0.5 text-[9px] font-bold text-white">INACTIVE</span>}
                  {t.licensed && <span className="ml-2 bg-[#7C3AED] px-1.5 py-0.5 text-[9px] font-bold text-white">LICENSED</span>}
                </div>
                <div className="text-[11px] text-[#4B5563]">
                  {(t.checklist || []).length} checklist items
                  {t.photo_hint && <> · {t.photo_hint}</>}
                </div>
              </div>
              <Button
                data-testid={`edit-trade-${t.trade_id}`}
                variant="outline"
                onClick={() => setEditing(t.trade_id)}
                className="h-9 rounded-none border-[#030712] px-4 text-xs font-bold"
              >
                Edit
              </Button>
            </div>
          )
        )}
      </div>
    </div>
  );
}

function TradeEditor({ trade, onDone, onCancel }) {
  const [label, setLabel] = useState(trade?.label || "");
  const [licensed, setLicensed] = useState(!!trade?.licensed);
  const [active, setActive] = useState(trade ? !!trade.active : true);
  const [photoHint, setPhotoHint] = useState(trade?.photo_hint || "");
  const [items, setItems] = useState(trade?.checklist?.map((i) => ({ ...i })) || []);
  const [busy, setBusy] = useState(false);

  const setItem = (idx, patch) =>
    setItems((arr) => arr.map((it, i) => (i === idx ? { ...it, ...patch } : it)));

  const save = async () => {
    if (!label.trim()) return toast.error("Trade name required");
    setBusy(true);
    try {
      const body = {
        label: label.trim(),
        licensed,
        active,
        photo_hint: photoHint.trim() || null,
        checklist: items.filter((i) => i.label.trim()),
      };
      if (trade) await api.put(`/admin/trades/${trade.trade_id}`, body);
      else await api.post("/admin/trades", body);
      toast.success(trade ? "Trade updated" : "Trade created");
      onDone();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid={`trade-editor-${trade?.trade_id || "new"}`} className="mb-3 border-2 border-[#0044FF] bg-white p-5">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="md:col-span-2">
          <div className="font-mono-label mb-1.5">Trade name</div>
          <Input data-testid="trade-editor-label" value={label} onChange={(e) => setLabel(e.target.value)} className="h-10 rounded-none border-[#030712]" />
        </div>
        <div className="flex items-end gap-4 pb-1">
          <label className="flex items-center gap-2 text-xs font-bold">
            <input data-testid="trade-editor-licensed" type="checkbox" checked={licensed} onChange={(e) => setLicensed(e.target.checked)} className="h-4 w-4 accent-[#7C3AED]" />
            Licensed
          </label>
          <label className="flex items-center gap-2 text-xs font-bold">
            <input data-testid="trade-editor-active" type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="h-4 w-4 accent-[#10B981]" />
            Active
          </label>
        </div>
      </div>
      <div className="mt-3">
        <div className="font-mono-label mb-1.5">Photo requirement hint (shown to workers)</div>
        <Input data-testid="trade-editor-photo-hint" value={photoHint} onChange={(e) => setPhotoHint(e.target.value)} placeholder="e.g. Machine photo REQUIRED" className="h-10 rounded-none border-[#030712]" />
      </div>

      <div className="mt-4">
        <div className="font-mono-label mb-2">Checklist items</div>
        <div className="space-y-2">
          {items.map((it, idx) => (
            <div key={idx} className="flex flex-wrap items-center gap-2 border border-[#E5E7EB] p-2" data-testid={`trade-editor-item-${idx}`}>
              <Input
                value={it.label}
                onChange={(e) => setItem(idx, { label: e.target.value })}
                placeholder="Item label"
                className="h-9 min-w-[160px] flex-1 rounded-none border-[#E5E7EB] text-sm"
              />
              <Input
                value={it.detail_label || ""}
                onChange={(e) => setItem(idx, { detail_label: e.target.value })}
                placeholder="Detail field (optional, e.g. Make/model)"
                className="h-9 min-w-[160px] flex-1 rounded-none border-[#E5E7EB] text-sm"
              />
              <label className="flex items-center gap-1.5 text-[10px] font-bold uppercase">
                <input
                  type="checkbox"
                  checked={!!it.photo_required}
                  onChange={(e) => setItem(idx, { photo_required: e.target.checked })}
                  className="h-3.5 w-3.5 accent-[#F59E0B]"
                />
                Photo req.
              </label>
              <button type="button" onClick={() => setItems((arr) => arr.filter((_, i) => i !== idx))} className="text-[#EF4444]">
                <Trash size={15} />
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          data-testid="trade-editor-add-item"
          onClick={() => setItems((arr) => [...arr, { key: "", label: "", detail_label: "", photo_required: false }])}
          className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-[#0044FF]"
        >
          <Plus size={13} /> Add item
        </button>
      </div>

      <div className="mt-4 flex gap-2 border-t border-[#E5E7EB] pt-3">
        <Button data-testid="trade-editor-save" onClick={save} disabled={busy} className="h-9 rounded-none bg-[#030712] px-5 text-xs font-bold text-white">
          {busy ? "Saving…" : "Save"}
        </Button>
        <Button data-testid="trade-editor-cancel" variant="outline" onClick={onCancel} className="h-9 rounded-none border-[#E5E7EB] px-5 text-xs font-bold">
          Cancel
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Metrics
// ============================================================================
function Metrics() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/admin/trades/metrics").then(({ data }) => setData(data)).catch((e) => toast.error(getErr(e)));
  }, []);
  if (!data) return null;
  return (
    <div data-testid="trades-metrics">
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Specialists on roster" value={data.total_specialists} />
        <MetricCard label="With ≥1 verified trade" value={data.verified_specialists} />
        <MetricCard label="% of roster verified" value={`${data.pct_roster_verified}%`} />
      </div>
      <div className="overflow-x-auto border border-[#E5E7EB]">
        <div className="grid grid-cols-7 gap-0 border-b border-[#E5E7EB] bg-[#F9FAFB] px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
          <div className="col-span-2">Trade</div>
          <div>Claims</div>
          <div>Pending</div>
          <div>Verified</div>
          <div>% verified</div>
          <div>Avg turnaround</div>
        </div>
        {data.trades.map((t) => (
          <div key={t.trade} data-testid={`metrics-row-${t.trade}`} className="grid grid-cols-7 border-b border-[#E5E7EB] px-4 py-2.5 text-sm">
            <div className="col-span-2 font-semibold">{t.label}</div>
            <div>{t.total}</div>
            <div>{t.pending}</div>
            <div className="font-bold text-[#10B981]">{t.verified}</div>
            <div>{t.pct_verified}%</div>
            <div>{t.avg_turnaround_days != null ? `${t.avg_turnaround_days}d` : "—"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="border border-[#E5E7EB] bg-white p-5">
      <div className="font-mono-label">{label}</div>
      <div className="mt-1 font-display text-3xl font-black tracking-tight">{value}</div>
    </div>
  );
}
