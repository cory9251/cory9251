import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, IdentificationCard, UserCircle } from "@phosphor-icons/react";

export default function AdminWorkers() {
  const [workers, setWorkers] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/admin/workers");
        setWorkers(data);
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, []);

  return (
    <div data-testid="admin-workers">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">Roster</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          Workers
        </h1>
      </div>

      <div className="px-6 py-6 md:px-10">
        {workers.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No workers yet.
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
                <div className="mt-4 flex items-center justify-between text-xs">
                  <span className="font-mono-label">
                    {new Date(w.created_at).toLocaleDateString()}
                  </span>
                  {w.id_image_path ? (
                    w.id_verified ? (
                      <span className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-1 text-[10px] font-bold tracking-widest text-white">
                        <CheckCircle size={10} weight="fill" /> VERIFIED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-1 text-[10px] font-bold tracking-widest text-white">
                        <IdentificationCard size={10} /> PENDING
                      </span>
                    )
                  ) : (
                    <span className="bg-[#E5E7EB] px-2 py-1 text-[10px] font-bold tracking-widest text-[#4B5563]">
                      NO ID
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
