import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Briefcase, PlusCircle } from "@phosphor-icons/react";

const STAGES = [
  { value: "new_lead", label: "New Lead", color: "bg-[#0044FF]" },
  { value: "contacted", label: "Contacted", color: "bg-violet-600" },
  { value: "quoted", label: "Quoted", color: "bg-amber-500" },
  { value: "booked", label: "Booked", color: "bg-emerald-600" },
  { value: "completed", label: "Completed", color: "bg-teal-700" },
  { value: "paid", label: "Paid ✓", color: "bg-emerald-700" },
  { value: "lost", label: "Lost", color: "bg-[#9CA3AF]" },
];

function StageBadge({ stage }) {
  const s = STAGES.find((x) => x.value === stage) || STAGES[0];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white ${s.color}`}
    >
      {s.label}
    </span>
  );
}

export default function VAMyLeads() {
  const nav = useNavigate();
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [stageFilter, setStageFilter] = useState("all");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/va/leads");
        setItems(data.items || []);
      } catch (e) {
        setErr(getErr(e));
      }
    })();
  }, []);

  const filtered = items?.filter((l) =>
    stageFilter === "all" ? true : l.stage === stageFilter
  );

  const counts = items
    ? STAGES.reduce((acc, s) => {
        acc[s.value] = items.filter((l) => l.stage === s.value).length;
        return acc;
      }, {})
    : {};

  return (
    <div className="p-6 md:p-10" data-testid="va-my-leads">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono-label">My pipeline</div>
          <h1 className="font-display text-4xl font-black tracking-tight">My leads</h1>
          <p className="mt-2 text-sm text-[#4B5563]">
            Click any lead to view details, edit (while it&apos;s still <strong>New Lead</strong>), or delete it.
            Once Ops picks it up, stage changes are made for you.
          </p>
        </div>
        <Link
          to="/va/submit"
          data-testid="add-lead-btn"
          className="inline-flex items-center gap-2 bg-[#030712] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f2937]"
        >
          <PlusCircle size={16} weight="bold" /> Submit new
        </Link>
      </div>

      {/* Stage filter chips */}
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          data-testid="stage-filter-all"
          onClick={() => setStageFilter("all")}
          className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
            stageFilter === "all"
              ? "border-[#030712] bg-[#030712] text-white"
              : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
          }`}
        >
          All ({items?.length ?? 0})
        </button>
        {STAGES.map((s) => (
          <button
            key={s.value}
            data-testid={`stage-filter-${s.value}`}
            onClick={() => setStageFilter(s.value)}
            className={`border px-3 py-1.5 text-xs font-mono uppercase tracking-widest ${
              stageFilter === s.value
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {s.label} ({counts[s.value] || 0})
          </button>
        ))}
      </div>

      {err && (
        <div data-testid="va-leads-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {err}
        </div>
      )}

      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : filtered.length === 0 ? (
        <div
          data-testid="va-leads-empty"
          className="flex flex-col items-center gap-3 border border-dashed border-[#E5E7EB] bg-white p-12 text-center"
        >
          <Briefcase size={36} weight="duotone" className="text-[#4B5563]" />
          <div className="font-display text-lg font-black">No leads yet</div>
          <div className="max-w-md text-sm text-[#4B5563]">
            Submit your first lead from the form to lock in ownership and start earning commission.
          </div>
          <Link
            to="/va/submit"
            className="mt-2 inline-flex items-center gap-2 bg-[#030712] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1f2937]"
          >
            <PlusCircle size={16} weight="bold" /> Submit a lead
          </Link>
        </div>
      ) : (
        <div className="border border-[#E5E7EB] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                <th className="px-4 py-3">Prospect</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Service</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Submitted</th>
                <th className="px-4 py-3">Stage</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((l) => (
                <tr
                  key={l.lead_id}
                  data-testid={`lead-row-${l.lead_id}`}
                  onClick={() => nav(`/va/leads/${l.lead_id}`)}
                  className="cursor-pointer border-t border-[#E5E7EB] hover:bg-[#F9FAFB]"
                >
                  <td className="px-4 py-3">
                    <div className="font-semibold text-[#0044FF]">{l.prospect_name}</div>
                    {l.notes && (
                      <div className="mt-1 line-clamp-2 text-xs text-[#4B5563]">{l.notes}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <div>{l.prospect_phone}</div>
                    {l.prospect_email && <div className="text-[#4B5563]">{l.prospect_email}</div>}
                  </td>
                  <td className="px-4 py-3 capitalize">{l.service_type}</td>
                  <td className="px-4 py-3 uppercase font-mono text-xs">{l.property_size}</td>
                  <td className="px-4 py-3 text-xs text-[#4B5563]">
                    {l.source?.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-3 text-xs text-[#4B5563]">
                    {(l.created_at || "").slice(0, 10)}
                  </td>
                  <td className="px-4 py-3">
                    <StageBadge stage={l.stage} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
