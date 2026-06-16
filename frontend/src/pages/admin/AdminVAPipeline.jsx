import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { MagnifyingGlass, ArrowRight } from "@phosphor-icons/react";
import MessageUserButton from "@/components/messages/MessageUserButton";

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

function StageBadge({ stage }) {
  const s = STAGES.find((x) => x.value === stage) || STAGES[0];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${s.color}`}>
      {s.label}
    </span>
  );
}

export default function AdminVAPipeline() {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [stage, setStage] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [jobValueMap, setJobValueMap] = useState({}); // lead_id → input val for Paid stage

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (stage) params.set("stage", stage);
      if (serviceType) params.set("service_type", serviceType);
      const { data } = await api.get(`/pm/leads?${params.toString()}`);
      setItems(data.items || []);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [stage, serviceType]);

  const moveStage = async (lead, newStage) => {
    try {
      const payload = { stage: newStage };
      if (newStage === "paid") {
        const v = parseFloat(jobValueMap[lead.lead_id]);
        if (Number.isFinite(v) && v > 0) payload.job_value = v;
      }
      await api.put(`/pm/leads/${lead.lead_id}/stage`, payload);
      toast.success(`Moved to ${newStage.replace(/_/g, " ")}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const counts = items
    ? STAGES.reduce((acc, s) => {
        acc[s.value] = items.filter((l) => l.stage === s.value).length;
        return acc;
      }, {})
    : {};

  return (
    <div className="p-6 md:p-10" data-testid="admin-va-pipeline">
      <div className="mb-6">
        <div className="font-mono-label">VA Commission Program</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Lead pipeline</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Every VA-submitted lead across the platform. Move stages to drive commission lifecycle.
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
          <Input
            data-testid="pipeline-search"
            placeholder="Search name / phone / email"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="h-9 rounded-none border-[#030712] pl-8 text-xs w-56"
          />
        </div>
        <select
          data-testid="pipeline-stage-filter"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="h-9 border border-[#030712] bg-white px-2 text-xs"
        >
          <option value="">All stages ({items?.length ?? 0})</option>
          {STAGES.map((s) => (
            <option key={s.value} value={s.value}>{s.label} ({counts[s.value] || 0})</option>
          ))}
        </select>
        <select
          data-testid="pipeline-service-filter"
          value={serviceType}
          onChange={(e) => setServiceType(e.target.value)}
          className="h-9 border border-[#030712] bg-white px-2 text-xs"
        >
          <option value="">All services</option>
          <option value="routine">Routine</option>
          <option value="deep">Deep</option>
          <option value="moveout">Move-out</option>
          <option value="specialty">Specialty</option>
          <option value="commercial">Commercial</option>
        </select>
        <Button
          onClick={load}
          data-testid="pipeline-apply-btn"
          className="h-9 rounded-none bg-[#030712] px-3 text-xs text-white"
        >
          Apply
        </Button>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>
      )}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          No leads found.
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-3 py-3">VA</th>
                <th className="px-3 py-3">Prospect</th>
                <th className="px-3 py-3">Service</th>
                <th className="px-3 py-3">Size</th>
                <th className="px-3 py-3">Source</th>
                <th className="px-3 py-3">Submitted</th>
                <th className="px-3 py-3">Stage</th>
                <th className="px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => {
                const nexts = STAGE_TRANSITIONS[l.stage] || [];
                return (
                  <tr
                    key={l.lead_id}
                    data-testid={`pipeline-row-${l.lead_id}`}
                    className="border-t border-[#E5E7EB] hover:bg-[#F9FAFB] align-top"
                  >
                    <td className="px-3 py-3 text-xs">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-semibold">{l.va_name || "—"}</div>
                          <div className="text-[#4B5563]">{(l.va_user_id || "").slice(0, 18)}</div>
                        </div>
                        {l.va_user_id && (
                          <MessageUserButton
                            userId={l.va_user_id}
                            name={l.va_name}
                            variant="icon"
                            testId={`pipeline-message-va-${l.lead_id}`}
                          />
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-semibold">{l.prospect_name}</div>
                      <div className="text-xs text-[#4B5563]">{l.prospect_phone}</div>
                      {l.prospect_email && (
                        <div className="text-xs text-[#4B5563]">{l.prospect_email}</div>
                      )}
                    </td>
                    <td className="px-3 py-3 capitalize">{l.service_type}</td>
                    <td className="px-3 py-3 uppercase text-xs font-mono">{l.property_size}</td>
                    <td className="px-3 py-3 text-xs">{l.source?.replace(/_/g, " ")}</td>
                    <td className="px-3 py-3 text-xs text-[#4B5563]">
                      {(l.created_at || "").slice(0, 10)}
                    </td>
                    <td className="px-3 py-3">
                      <StageBadge stage={l.stage} />
                    </td>
                    <td className="px-3 py-3">
                      {nexts.length === 0 ? (
                        <span className="text-xs text-[#9CA3AF]">—</span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {nexts.map((ns) => (
                            <div key={ns} className="flex items-center gap-1">
                              {ns === "paid" && (
                                <input
                                  type="number"
                                  placeholder="$ value"
                                  data-testid={`job-value-${l.lead_id}`}
                                  value={jobValueMap[l.lead_id] || ""}
                                  onChange={(e) =>
                                    setJobValueMap({ ...jobValueMap, [l.lead_id]: e.target.value })
                                  }
                                  className="h-7 w-20 border border-[#E5E7EB] px-2 text-xs"
                                />
                              )}
                              <button
                                data-testid={`pipeline-move-${l.lead_id}-${ns}`}
                                onClick={() => moveStage(l, ns)}
                                className="inline-flex items-center gap-1 border border-[#030712] bg-white px-2 py-1 text-xs hover:bg-[#030712] hover:text-white"
                              >
                                <ArrowRight size={11} /> {ns.replace(/_/g, " ")}
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
