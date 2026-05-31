import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, CurrencyDollar, MapPin, Clock } from "@phosphor-icons/react";

export default function WorkerAccepted() {
  const [items, setItems] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/gigs", { params: { status: "all" } });
        // we want only ones the worker accepted; backend already attaches my_acceptance
        setItems(data.filter((g) => g.my_acceptance));
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, []);

  return (
    <div className="px-5 py-6" data-testid="worker-accepted">
      <div className="font-mono-label">My commitments</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        My gigs
      </h1>

      <div className="mt-5 space-y-4">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            You haven't accepted any gigs yet.
          </div>
        ) : (
          items.map((g) => {
            const acc = g.my_acceptance || {};
            const isRequested = acc.status === "requested";
            const onClock = acc.clock_in_at && !acc.clock_out_at;
            const completed = !!acc.clock_out_at;
            return (
            <button
              key={g.gig_id}
              data-testid={`accepted-gig-${g.gig_id}`}
              onClick={() => nav(`/app/gigs/${g.gig_id}`)}
              className="gb-tactile w-full rounded-2xl border border-black/5 bg-white p-5 text-left"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-mono-label">
                    {g.category} · {g.subcategory || "general"}
                  </div>
                  <div className="mt-1 font-display text-lg font-bold">{g.title}</div>
                </div>
                {isRequested ? (
                  <span
                    data-testid={`requested-badge-${g.gig_id}`}
                    className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white"
                  >
                    <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                    REQUESTED
                  </span>
                ) : onClock ? (
                  <span
                    data-testid={`on-clock-badge-${g.gig_id}`}
                    className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white"
                  >
                    <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                    ON THE CLOCK
                  </span>
                ) : completed ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                    <CheckCircle size={10} weight="fill" />{" "}
                    {acc.hours_worked != null ? `${acc.hours_worked.toFixed(2)}H` : "DONE"}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#0044FF] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                    <CheckCircle size={10} weight="fill" /> APPROVED
                  </span>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-3 border-t border-[#E5E7EB] pt-3 text-xs">
                <Tag icon={CurrencyDollar} v={`$${Number(g.pay_rate).toFixed(0)}${g.pay_type === "hourly" ? "/hr" : ""}`} />
                <Tag icon={MapPin} v={g.location} />
                <Tag icon={Clock} v={g.scheduled_date} />
              </div>
            </button>
            );
          })
        )}
      </div>
    </div>
  );
}
const Tag = ({ icon: I, v }) => (
  <span className="inline-flex items-center gap-1 text-[#030712]">
    <I size={12} weight="duotone" /> {v}
  </span>
);
