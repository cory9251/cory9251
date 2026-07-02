import React, { useState } from "react";
import { toast } from "sonner";
import { Phone, ChatCircle, CalendarBlank } from "@phosphor-icons/react";
import { serviceTypeLabel } from "@/lib/leadOptions";

const STAGES = [
  { value: "new_lead", label: "New Lead", color: "bg-[#0044FF]" },
  { value: "contacted", label: "Contacted", color: "bg-violet-600" },
  { value: "quoted", label: "Quoted", color: "bg-amber-500" },
  { value: "booked", label: "Booked", color: "bg-emerald-600" },
  { value: "completed", label: "Completed", color: "bg-teal-700" },
  { value: "paid", label: "Paid ✓", color: "bg-emerald-700" },
  { value: "lost", label: "Lost", color: "bg-[#9CA3AF]" },
];

const STAGE_TRANSITIONS = {
  new_lead: ["contacted", "lost"],
  contacted: ["quoted", "lost"],
  quoted: ["booked", "lost"],
  booked: ["completed", "lost"],
  completed: ["paid", "lost"],
  paid: [],
  lost: [],
};

export const PipelineBoard = ({ items, onMove, onOpen }) => {
  const [dragId, setDragId] = useState(null);

  const isOverdue = (l) =>
    l.next_followup_at &&
    new Date(l.next_followup_at) < new Date() &&
    !["paid", "lost"].includes(l.stage);

  const handleDrop = (e, targetStage) => {
    e.preventDefault();
    const lead = items.find((l) => l.lead_id === dragId);
    setDragId(null);
    if (!lead || lead.stage === targetStage) return;
    const allowed = STAGE_TRANSITIONS[lead.stage] || [];
    if (!allowed.includes(targetStage)) {
      toast.error(
        `Can't move ${lead.stage.replace(/_/g, " ")} → ${targetStage.replace(/_/g, " ")}. Allowed: ${allowed.map((s) => s.replace(/_/g, " ")).join(", ") || "none"}`
      );
      return;
    }
    let jobValue = null;
    if (targetStage === "paid") {
      const v = window.prompt(
        `Job value ($) for "${lead.prospect_name}"? Commission is calculated from this.`,
        lead.job_value ?? lead.estimated_budget ?? ""
      );
      if (v === null) return;
      jobValue = v;
    }
    onMove(lead, targetStage, jobValue);
  };

  return (
    <div className="flex gap-3 overflow-x-auto pb-4" data-testid="pipeline-board">
      {STAGES.map((s) => {
        const col = items.filter((l) => l.stage === s.value);
        const total = col.reduce((sum, l) => sum + Number(l.job_value ?? l.estimated_budget ?? 0), 0);
        return (
          <div
            key={s.value}
            data-testid={`board-col-${s.value}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => handleDrop(e, s.value)}
            className="w-64 shrink-0 border border-[#E5E7EB] bg-[#F9FAFB]"
          >
            <div className={`flex items-center justify-between px-3 py-2 text-white ${s.color}`}>
              <span className="text-[10px] font-bold uppercase tracking-widest">{s.label}</span>
              <span className="text-[10px] font-bold">
                {col.length}
                {total > 0 ? ` · $${total.toFixed(0)}` : ""}
              </span>
            </div>
            <div className="min-h-[140px] space-y-2 p-2">
              {col.map((l) => (
                <div
                  key={l.lead_id}
                  draggable
                  data-testid={`board-card-${l.lead_id}`}
                  onDragStart={() => setDragId(l.lead_id)}
                  onClick={() => onOpen(l)}
                  className="cursor-grab border border-[#030712] bg-white p-2.5 shadow-sm transition-shadow hover:shadow-md active:cursor-grabbing"
                >
                  <div className="text-sm font-bold text-[#0044FF]">{l.prospect_name}</div>
                  <div className="mt-0.5 text-[11px] text-[#4B5563]">{serviceTypeLabel(l.service_type)}</div>
                  <div className="mt-0.5 text-[11px] text-[#9CA3AF]">VA: {l.va_name || "—"}</div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-[#4B5563]">
                    {(l.job_value ?? l.estimated_budget) != null && (
                      <span className="font-bold text-emerald-700">
                        ${Number(l.job_value ?? l.estimated_budget).toFixed(0)}
                      </span>
                    )}
                    {(l.contact_count || 0) > 0 && (
                      <span className="inline-flex items-center gap-0.5" title="Contact attempts">
                        <Phone size={10} /> {l.contact_count}
                      </span>
                    )}
                    {(l.comment_count || 0) > 0 && (
                      <span className="inline-flex items-center gap-0.5" title="Comments">
                        <ChatCircle size={10} /> {l.comment_count}
                      </span>
                    )}
                    {l.next_followup_at && (
                      <span
                        className={`inline-flex items-center gap-0.5 ${isOverdue(l) ? "font-bold text-[#DC2626]" : ""}`}
                        title={l.followup_note || "Next follow-up"}
                      >
                        <CalendarBlank size={10} /> {String(l.next_followup_at).slice(5, 10)}
                        {isOverdue(l) ? " !" : ""}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {col.length === 0 && (
                <div className="p-4 text-center text-[10px] uppercase tracking-widest text-[#D1D5DB]">
                  Drop here
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
