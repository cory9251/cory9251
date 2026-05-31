import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ClockCounterClockwise,
  CheckCircle,
  Prohibit,
  CurrencyDollar,
  MapPin,
  CalendarBlank,
  Broom,
  Wrench,
  Car,
  Phone,
  EnvelopeSimple,
  ShieldCheck,
  ArrowRight,
} from "@phosphor-icons/react";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function AdminRequests() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const nav = useNavigate();

  const load = async () => {
    try {
      const { data } = await api.get("/admin/requests");
      setRows(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const act = async (row, action) => {
    setBusyId(row.acceptance_id);
    try {
      await api.post(
        `/gigs/${row.gig_id}/requests/${row.acceptance_id}/${action}`
      );
      toast.success(
        action === "approve"
          ? `${row.worker_name || "Worker"} approved for "${row.gig?.title}"`
          : "Request rejected"
      );
      // Remove the row from the queue
      setRows((rs) => rs.filter((r) => r.acceptance_id !== row.acceptance_id));
      // Tell the sidebar badge to refresh
      window.dispatchEvent(new Event("hcob:requests-changed"));
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-10 font-mono-label" data-testid="requests-loading">
        Loading requests…
      </div>
    );
  }

  return (
    <div data-testid="admin-requests">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div>
          <div className="font-mono-label">Approval queue</div>
          <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
            Requests
          </h1>
          <p className="mt-1 text-sm text-[#4B5563]">
            Every worker waiting on you to approve them for a specific gig.
          </p>
        </div>
        <div className="flex items-center gap-2 border border-[#030712] bg-[#030712] px-4 py-2 text-white">
          <ClockCounterClockwise size={18} weight="fill" />
          <span className="font-display text-2xl font-black tabular-nums">
            {rows.length}
          </span>
          <span className="font-mono-label text-white/70">pending</span>
        </div>
      </div>

      <div className="px-6 py-6 md:px-10">
        {rows.length === 0 ? (
          <div
            data-testid="requests-empty"
            className="border border-dashed border-[#E5E7EB] p-12 text-center"
          >
            <CheckCircle
              size={32}
              weight="duotone"
              className="mx-auto text-[#10B981]"
            />
            <div className="mt-3 font-display text-xl font-bold">
              All caught up
            </div>
            <div className="mt-1 text-sm text-[#4B5563]">
              No pending requests right now. New requests will land here.
            </div>
          </div>
        ) : (
          <ul className="space-y-3">
            {rows.map((r) => {
              const g = r.gig || {};
              const Icon = CAT_ICON[g.category] || Broom;
              const pay = `$${Number(g.pay_rate || 0).toFixed(2)}${
                g.pay_type === "hourly" ? "/hr" : " flat"
              }`;
              return (
                <li
                  key={r.acceptance_id}
                  data-testid={`request-${r.acceptance_id}`}
                  className="grid grid-cols-1 gap-4 border border-[#E5E7EB] bg-white p-5 lg:grid-cols-12"
                >
                  {/* Worker block */}
                  <div className="lg:col-span-4">
                    <div className="font-mono-label">Worker</div>
                    <div className="mt-1 font-display text-xl font-bold leading-tight">
                      {r.worker_name || r.worker_id}
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-[#4B5563]">
                      <div className="flex items-center gap-1.5">
                        <EnvelopeSimple size={12} /> {r.worker_email}
                      </div>
                      {r.worker_phone && (
                        <div className="flex items-center gap-1.5">
                          <Phone size={12} /> {r.worker_phone}
                        </div>
                      )}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {r.worker_id_verified ? (
                          <span className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-[#065F46]">
                            <ShieldCheck size={10} weight="fill" /> ID VERIFIED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-[#92400E]">
                            ID NOT VERIFIED
                          </span>
                        )}
                        {r.worker_status &&
                          r.worker_status !== "approved" && (
                            <span className="inline-flex items-center gap-1 bg-[#EF4444]/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-[#991B1B]">
                              {r.worker_status.toUpperCase()}
                            </span>
                          )}
                      </div>
                    </div>
                  </div>

                  {/* Gig block */}
                  <button
                    onClick={() => nav(`/admin/gigs/${r.gig_id}`)}
                    className="text-left lg:col-span-5"
                  >
                    <div className="font-mono-label flex items-center gap-2">
                      <Icon size={12} weight="duotone" /> {g.category} ·{" "}
                      {g.subcategory || "general"}
                    </div>
                    <div className="mt-1 flex items-center gap-1 font-display text-lg font-bold hover:text-[#0044FF]">
                      {g.title || r.gig_id}
                      <ArrowRight size={14} className="opacity-50" />
                    </div>
                    <div className="mt-2 grid grid-cols-1 gap-1 text-xs text-[#030712] sm:grid-cols-3">
                      <span className="inline-flex items-center gap-1.5">
                        <CurrencyDollar size={12} weight="duotone" /> {pay}
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <MapPin size={12} weight="duotone" /> {g.location}
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <CalendarBlank size={12} weight="duotone" />{" "}
                        {g.scheduled_date}
                      </span>
                    </div>
                    <div className="mt-1 font-mono-label">
                      Slots {g.slots_filled}/{g.slots}{" "}
                      {r.requested_at && (
                        <>
                          ·{" "}
                          {Math.max(
                            1,
                            Math.round(
                              (Date.now() - new Date(r.requested_at).getTime()) /
                                3600000
                            )
                          )}
                          h ago
                        </>
                      )}
                    </div>
                  </button>

                  {/* Actions */}
                  <div className="flex items-center gap-2 lg:col-span-3 lg:justify-end">
                    <Button
                      data-testid={`approve-request-${r.acceptance_id}`}
                      onClick={() => act(r, "approve")}
                      disabled={busyId === r.acceptance_id}
                      className="h-10 flex-1 rounded-none bg-[#10B981] text-white hover:bg-[#0e9971] lg:flex-none"
                    >
                      <CheckCircle weight="fill" size={14} className="mr-1" />
                      Approve
                    </Button>
                    <Button
                      data-testid={`reject-request-${r.acceptance_id}`}
                      onClick={() => act(r, "reject")}
                      disabled={busyId === r.acceptance_id}
                      variant="outline"
                      className="h-10 flex-1 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white lg:flex-none"
                    >
                      <Prohibit size={14} className="mr-1" /> Reject
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
