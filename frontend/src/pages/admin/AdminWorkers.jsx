import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  CheckCircle,
  IdentificationCard,
  UserCircle,
  ClockCounterClockwise,
  Prohibit,
  PauseCircle,
} from "@phosphor-icons/react";

const TABS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "suspended", label: "Suspended" },
];

function StatusBadge({ status }) {
  const s = status || "approved"; // legacy users without field
  const m = {
    pending: { bg: "bg-[#F59E0B]", icon: ClockCounterClockwise, label: "PENDING" },
    approved: { bg: "bg-[#10B981]", icon: CheckCircle, label: "APPROVED" },
    rejected: { bg: "bg-[#EF4444]", icon: Prohibit, label: "REJECTED" },
    suspended: { bg: "bg-[#4B5563]", icon: PauseCircle, label: "SUSPENDED" },
  }[s] || { bg: "bg-[#4B5563]", icon: UserCircle, label: s.toUpperCase() };
  const Icon = m.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-bold tracking-widest text-white ${m.bg}`}>
      <Icon size={10} weight="fill" /> {m.label}
    </span>
  );
}

export default function AdminWorkers() {
  const [workers, setWorkers] = useState([]);
  const [params, setParams] = useSearchParams();
  const tab = params.get("status") || "all";
  const nav = useNavigate();

  const load = async () => {
    try {
      const q = tab === "all" ? {} : { status: tab };
      const { data } = await api.get("/admin/workers", { params: q });
      setWorkers(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [tab]);

  const counts = useMemo(() => {
    // Quick local count for the visible list — accurate per active filter.
    return workers.length;
  }, [workers]);

  return (
    <div data-testid="admin-workers">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">Roster</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">Workers</h1>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`workers-tab-${t.key}`}
            onClick={() =>
              setParams(t.key === "all" ? {} : { status: t.key })
            }
            className={`px-3 py-1.5 text-xs font-bold tracking-widest uppercase ${
              tab === t.key
                ? "bg-[#030712] text-white"
                : "border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
            }`}
          >
            {t.label}
          </button>
        ))}
        <span className="ml-auto font-mono-label">{counts} shown</span>
      </div>

      <div className="px-6 py-6 md:px-10">
        {workers.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No workers in this category.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {workers.map((w) => (
              <button
                key={w.user_id}
                data-testid={`worker-card-${w.user_id}`}
                onClick={() => nav(`/admin/workers/${w.user_id}`)}
                className="border border-[#E5E7EB] bg-white p-5 text-left hover:border-[#030712]"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center bg-[#F0F4FF] text-[#0044FF]">
                    <UserCircle size={28} weight="duotone" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-display text-lg font-bold">{w.name}</div>
                    <div className="truncate text-xs text-[#4B5563]">{w.email}</div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <StatusBadge status={w.worker_status} />
                  {w.id_image_path ? (
                    w.id_verified ? (
                      <span className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#065F46]">
                        <CheckCircle size={10} weight="fill" /> ID OK
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#92400E]">
                        <IdentificationCard size={10} /> ID PENDING
                      </span>
                    )
                  ) : (
                    <span className="bg-[#E5E7EB] px-2 py-1 text-[10px] font-bold tracking-widest text-[#4B5563]">
                      NO ID
                    </span>
                  )}
                </div>
                <div className="mt-2 font-mono-label">
                  Joined {new Date(w.created_at).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
