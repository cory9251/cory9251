import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowsClockwise,
  Clock,
  FireSimple,
  PlusCircle,
  Phone,
  EnvelopeSimple,
  CaretRight,
  WarningCircle,
  CheckCircle,
} from "@phosphor-icons/react";

// VA-controlled soft pipeline columns. Hard outcomes (booked/completed/lost)
// are lumped into a single read-only "With Ops" column to keep the board
// from sprawling — VAs care most about what they can still influence.
const COLUMNS = [
  {
    value: "new_lead",
    label: "New",
    sublabel: "Reach out",
    color: "border-[#0044FF]",
    accent: "text-[#0044FF]",
    bg: "bg-[#F0F4FF]",
  },
  {
    value: "contacted",
    label: "Contacted",
    sublabel: "Get the quote out",
    color: "border-violet-500",
    accent: "text-violet-600",
    bg: "bg-violet-50",
  },
  {
    value: "quoted",
    label: "Quoted",
    sublabel: "Close the deal",
    color: "border-amber-500",
    accent: "text-amber-700",
    bg: "bg-amber-50",
  },
  {
    value: "_with_ops",
    label: "With Ops",
    sublabel: "Booked / Closed / Lost",
    color: "border-[#9CA3AF]",
    accent: "text-[#4B5563]",
    bg: "bg-[#F9FAFB]",
  },
];

const TERMINAL_STAGES = new Set(["booked", "completed", "paid", "lost"]);

function columnOf(lead) {
  const s = (lead.stage || "new_lead").toLowerCase();
  if (TERMINAL_STAGES.has(s)) return "_with_ops";
  if (["new_lead", "contacted", "quoted"].includes(s)) return s;
  return "_with_ops";
}

function formatCountdown(dueIso) {
  if (!dueIso) return null;
  const due = new Date(dueIso).getTime();
  const now = Date.now();
  const ms = due - now;
  const overdue = ms <= 0;
  const absMs = Math.abs(ms);
  const hours = Math.floor(absMs / 3.6e6);
  const mins = Math.floor((absMs % 3.6e6) / 6e4);
  if (overdue) return `${hours}h ${mins}m overdue`;
  if (hours >= 1) return `${hours}h ${mins}m left`;
  return `${mins}m left`;
}

function SlaBadge({ lead }) {
  const state = lead.sla_state;
  const cd = formatCountdown(lead.sla_due_at_iso);
  if (!state || !cd) return null;
  const styles = {
    ok: "bg-[#10B981]/15 text-[#065F46] border-[#10B981]",
    hot: "bg-[#F59E0B]/15 text-[#92400E] border-[#F59E0B] animate-pulse",
    stale: "bg-[#EF4444]/15 text-[#991B1B] border-[#EF4444]",
  };
  const Icon = state === "stale" ? WarningCircle : state === "hot" ? FireSimple : Clock;
  return (
    <span
      data-testid={`sla-badge-${state}`}
      className={`inline-flex items-center gap-1 border px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${styles[state]}`}
    >
      <Icon size={10} weight="fill" />
      {cd}
    </span>
  );
}

export default function VAMyLeads() {
  const nav = useNavigate();
  const [board, setBoard] = useState(null);
  const [err, setErr] = useState("");
  const [moving, setMoving] = useState({}); // lead_id → true while moving
  const [tick, setTick] = useState(0); // forces re-render every 30s for SLA

  const load = async () => {
    try {
      const { data } = await api.get("/va/pipeline");
      setBoard(data);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  // SLA timer refresh — every 30s. Cheap, single state bump.
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  // Group leads by column
  const grouped = useMemo(() => {
    const g = { new_lead: [], contacted: [], quoted: [], _with_ops: [] };
    (board?.items || []).forEach((l) => {
      g[columnOf(l)].push(l);
    });
    return g;
  }, [board, tick]); // tick keeps SLA fresh on re-render

  const moveLead = async (leadId, newStage) => {
    setMoving((m) => ({ ...m, [leadId]: true }));
    try {
      await api.patch(`/va/leads/${leadId}/stage`, { stage: newStage });
      toast.success(`Moved to ${COLUMNS.find((c) => c.value === newStage)?.label || newStage}`);
      await load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setMoving((m) => {
        const next = { ...m };
        delete next[leadId];
        return next;
      });
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="va-pipeline-board">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label">My pipeline</div>
          <h1 className="font-display text-4xl font-black tracking-tight">My leads</h1>
          <p className="mt-2 max-w-xl text-sm text-[#4B5563]">
            Drag a lead through <strong>New → Contacted → Quoted</strong> as you work it.
            Hot/red timers mean it&apos;s about to age out — knock those out first.
            Bookings are flipped by Ops after they verify the deal.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="va-pipeline-refresh"
            onClick={load}
            className="inline-flex items-center gap-1 border border-[#030712] bg-white px-3 py-2 text-xs font-bold uppercase tracking-widest hover:bg-[#F9FAFB]"
          >
            <ArrowsClockwise size={12} /> Refresh
          </button>
          <Link
            to="/va/submit"
            data-testid="add-lead-btn"
            className="inline-flex items-center gap-2 bg-[#030712] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1f2937]"
          >
            <PlusCircle size={16} weight="bold" /> Submit new
          </Link>
        </div>
      </div>

      {err && (
        <div className="mb-4 border border-[#EF4444] bg-[#FEE2E2] p-3 text-sm text-[#991B1B]">
          {err}
        </div>
      )}

      {!board && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {COLUMNS.map((c) => (
            <div key={c.value} className="h-64 animate-pulse border border-[#E5E7EB] bg-white" />
          ))}
        </div>
      )}

      {board && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          {COLUMNS.map((col) => {
            const cards = grouped[col.value] || [];
            const hotCount = cards.filter(
              (l) => l.sla_state === "hot" || l.sla_state === "stale"
            ).length;
            return (
              <div
                key={col.value}
                data-testid={`column-${col.value}`}
                className={`flex min-h-[200px] flex-col border-t-2 ${col.color} bg-white`}
              >
                {/* Column header */}
                <div className={`flex items-center justify-between px-4 py-3 ${col.bg}`}>
                  <div>
                    <div className={`font-display text-base font-black ${col.accent}`}>
                      {col.label}{" "}
                      <span className="text-[10px] tracking-widest text-[#4B5563]">
                        ({cards.length})
                      </span>
                    </div>
                    <div className="font-mono-label text-[10px] text-[#4B5563]">
                      {col.sublabel}
                    </div>
                  </div>
                  {hotCount > 0 && col.value !== "_with_ops" && (
                    <span
                      data-testid={`column-hot-count-${col.value}`}
                      className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white"
                    >
                      <FireSimple size={10} weight="fill" />
                      {hotCount} hot
                    </span>
                  )}
                </div>

                {/* Cards */}
                <div className="flex-1 space-y-2 p-3">
                  {cards.length === 0 && (
                    <div className="border border-dashed border-[#E5E7EB] p-4 text-center text-[11px] text-[#9CA3AF]">
                      {col.value === "new_lead"
                        ? "Submit a new lead → it lands here"
                        : "Nothing here yet"}
                    </div>
                  )}
                  {cards.map((lead) => (
                    <LeadCard
                      key={lead.lead_id}
                      lead={lead}
                      column={col.value}
                      moving={!!moving[lead.lead_id]}
                      onMove={moveLead}
                      onOpen={() => nav(`/va/leads/${lead.lead_id}`)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function LeadCard({ lead, column, moving, onMove, onOpen }) {
  const [notes, setNotes] = useState(lead.notes || "");
  const [savingNote, setSavingNote] = useState(false);
  const [noteDirty, setNoteDirty] = useState(false);
  const phone = lead.prospect_phone;
  const email = lead.prospect_email;
  const isTerminal = column === "_with_ops";
  const terminalLabel = (() => {
    const s = (lead.stage || "").toLowerCase();
    if (s === "booked") return "Booked";
    if (s === "completed") return "Completed";
    if (s === "paid") return "Paid";
    if (s === "lost") return "Lost";
    return s;
  })();
  return (
    <div
      data-testid={`lead-card-${lead.lead_id}`}
      className={`border border-[#E5E7EB] bg-white p-3 transition-all hover:border-[#030712] hover:shadow-sm ${
        moving ? "opacity-50" : ""
      }`}
    >
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full items-start justify-between gap-2 text-left"
      >
        <div className="font-display text-sm font-bold leading-tight">
          {lead.prospect_name}
        </div>
        <CaretRight size={14} className="mt-1 shrink-0 text-[#9CA3AF]" />
      </button>

      <div className="mt-1 space-y-0.5">
        {phone && (
          <a
            href={`tel:${phone}`}
            data-testid={`lead-card-phone-${lead.lead_id}`}
            className="flex items-center gap-1 text-[11px] text-[#0044FF] hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            <Phone size={10} /> {phone}
          </a>
        )}
        {email && (
          <a
            href={`mailto:${email}`}
            data-testid={`lead-card-email-${lead.lead_id}`}
            className="flex items-center gap-1 text-[11px] text-[#4B5563] hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            <EnvelopeSimple size={10} /> {email}
          </a>
        )}
        {lead.service_type && (
          <div className="font-mono-label text-[10px] text-[#4B5563]">
            {lead.service_type.toUpperCase()} · {lead.property_size || "—"}
          </div>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {!isTerminal && <SlaBadge lead={lead} />}
        {isTerminal && (
          <span className="inline-flex items-center gap-1 border border-[#E5E7EB] bg-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
            <CheckCircle size={10} weight="fill" /> {terminalLabel}
          </span>
        )}
      </div>

      {/* Move dropdown — tap-to-move (mobile-first; works alongside future drag) */}
      {!isTerminal && (
        <div className="mt-3 flex items-center gap-2">
          <label
            htmlFor={`move-${lead.lead_id}`}
            className="font-mono-label text-[9px] text-[#4B5563]"
          >
            Move →
          </label>
          <select
            id={`move-${lead.lead_id}`}
            data-testid={`move-select-${lead.lead_id}`}
            disabled={moving}
            value={lead.stage}
            onChange={(e) => {
              if (e.target.value !== lead.stage) onMove(lead.lead_id, e.target.value);
            }}
            className="h-7 flex-1 border border-[#030712] bg-white px-2 text-[11px] font-bold uppercase tracking-widest"
          >
            <option value="new_lead">New</option>
            <option value="contacted">Contacted</option>
            <option value="quoted">Quoted</option>
          </select>
        </div>
      )}

      {/* Inline notes — saves on blur. Available at any stage. */}
      <div className="mt-2 border-t border-[#E5E7EB] pt-2">
        <textarea
          data-testid={`notes-input-${lead.lead_id}`}
          value={notes}
          onChange={(e) => {
            setNotes(e.target.value);
            setNoteDirty(e.target.value !== (lead.notes || ""));
          }}
          onBlur={async () => {
            if (!noteDirty || savingNote) return;
            setSavingNote(true);
            try {
              await api.patch(`/va/leads/${lead.lead_id}/notes`, { notes });
              setNoteDirty(false);
              toast.success("Note saved");
            } catch (e) {
              toast.error(getErr(e));
            } finally {
              setSavingNote(false);
            }
          }}
          placeholder="Quick note (saves on blur)…"
          rows={2}
          className="w-full resize-none border border-[#E5E7EB] bg-[#F9FAFB] p-2 text-[11px] focus:border-[#030712] focus:outline-none"
        />
        {savingNote && (
          <div className="font-mono-label text-[9px] text-[#4B5563]">Saving…</div>
        )}
        {noteDirty && !savingNote && (
          <div
            data-testid={`note-dirty-${lead.lead_id}`}
            className="font-mono-label text-[9px] text-amber-700"
          >
            Unsaved — click out to save
          </div>
        )}
      </div>
    </div>
  );
}
