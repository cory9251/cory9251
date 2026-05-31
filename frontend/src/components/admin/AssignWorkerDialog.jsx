import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MagnifyingGlass,
  UserCircle,
  ShieldCheck,
  Plus,
} from "@phosphor-icons/react";

export default function AssignWorkerDialog({
  open,
  onOpenChange,
  gig,
  onAssigned,
}) {
  const [workers, setWorkers] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const { data } = await api.get("/admin/workers", {
          params: { status: "approved" },
        });
        setWorkers(data);
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, [open]);

  // Exclude workers already on the gig (pending OR approved)
  const excludeIds = useMemo(() => {
    const set = new Set();
    (gig?.pending_requests || []).forEach((a) => set.add(a.worker_id));
    (gig?.acceptances || []).forEach((a) => set.add(a.worker_id));
    return set;
  }, [gig]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    return workers
      .filter((w) => !excludeIds.has(w.user_id))
      .filter(
        (w) =>
          !query ||
          (w.name || "").toLowerCase().includes(query) ||
          (w.email || "").toLowerCase().includes(query)
      )
      .slice(0, 80);
  }, [workers, excludeIds, q]);

  const assign = async (w) => {
    setBusy(w.user_id);
    try {
      await api.post(`/gigs/${gig.gig_id}/assign`, { worker_id: w.user_id });
      toast.success(`${w.name || w.email} added to gig`);
      onAssigned && onAssigned();
      onOpenChange(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl rounded-none border-[#030712] p-0"
        data-testid="assign-worker-dialog"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-2xl font-black tracking-tight">
            Add a worker to this gig
          </DialogTitle>
        </DialogHeader>
        <div className="border-b border-[#E5E7EB] p-4">
          <div className="relative">
            <MagnifyingGlass
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4B5563]"
            />
            <Input
              data-testid="assign-search"
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name or email…"
              className="h-11 rounded-none border-[#030712] pl-9"
            />
          </div>
          <div className="mt-2 font-mono-label">
            {filtered.length} eligible worker{filtered.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="max-h-[60vh] overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="p-10 text-center text-sm text-[#4B5563]">
              No workers match — every approved worker is either already on this
              gig or doesn't match your search.
            </div>
          ) : (
            <ul className="divide-y divide-[#E5E7EB]">
              {filtered.map((w) => (
                <li
                  key={w.user_id}
                  data-testid={`assign-row-${w.user_id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-[#F9FAFB]"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="grid h-10 w-10 shrink-0 place-items-center bg-[#F0F4FF] text-[#0044FF]">
                      <UserCircle size={22} weight="duotone" />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate font-display text-base font-bold">
                        {w.name || w.email}
                      </div>
                      <div className="truncate text-xs text-[#4B5563]">
                        {w.email}
                        {w.phone ? ` · ${w.phone}` : ""}
                      </div>
                    </div>
                    {w.id_verified ? (
                      <span className="inline-flex shrink-0 items-center gap-1 bg-[#10B981]/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-[#065F46]">
                        <ShieldCheck size={10} weight="fill" /> ID OK
                      </span>
                    ) : (
                      <span className="shrink-0 bg-[#F59E0B]/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-[#92400E]">
                        NO VERIFIED ID
                      </span>
                    )}
                  </div>
                  <Button
                    data-testid={`assign-btn-${w.user_id}`}
                    onClick={() => assign(w)}
                    disabled={busy === w.user_id}
                    className="h-9 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
                  >
                    <Plus size={12} className="mr-1" />
                    {busy === w.user_id ? "Adding…" : "Add"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
