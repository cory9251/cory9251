import React, { useEffect, useState } from "react";
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
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { MagnifyingGlass, Link as LinkIcon } from "@phosphor-icons/react";

export default function LinkGigToProjectDialog({
  open,
  onOpenChange,
  projectId,
  projectDefaults,
  onLinked,
}) {
  const [gigs, setGigs] = useState([]);
  const [q, setQ] = useState("");
  const [sync, setSync] = useState(false);
  const [linkingId, setLinkingId] = useState(null);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const { data } = await api.get("/gigs");
        // Only show unlinked gigs (project_id null/undefined). Filter by query.
        setGigs(
          (data || []).filter(
            (g) =>
              !g.project_id &&
              g.status !== "completed" &&
              g.status !== "cancelled"
          )
        );
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, [open]);

  const linkIt = async (gig_id) => {
    setLinkingId(gig_id);
    try {
      await api.post(`/gigs/${gig_id}/link-to-project`, {
        project_id: projectId,
        sync_defaults: sync,
      });
      toast.success("Gig linked");
      onLinked && onLinked();
      onOpenChange(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLinkingId(null);
    }
  };

  const filtered = gigs.filter((g) =>
    q.trim()
      ? (g.title || "").toLowerCase().includes(q.toLowerCase()) ||
        (g.location || "").toLowerCase().includes(q.toLowerCase())
      : true
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="link-gig-dialog"
        className="max-h-[85vh] max-w-xl overflow-hidden rounded-none border-[#030712] p-0"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-lg font-black">
            Link existing gig to this project
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 px-6 py-4">
          <div className="flex items-center gap-2">
            <MagnifyingGlass size={14} className="text-[#4B5563]" />
            <Input
              data-testid="link-gig-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by title or location…"
              className="h-10 rounded-none border-[#030712]"
            />
          </div>
          {projectDefaults && Object.keys(projectDefaults || {}).length > 0 && (
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                data-testid="link-gig-sync"
                checked={sync}
                onCheckedChange={(v) => setSync(!!v)}
              />
              Also overwrite gig's location/date/payment timeline with the
              project's defaults
            </label>
          )}
        </div>
        <ul className="max-h-[55vh] divide-y divide-[#E5E7EB] overflow-y-auto border-t border-[#E5E7EB]">
          {filtered.length === 0 ? (
            <li className="bg-[#F9FAFB] p-6 text-center text-xs text-[#4B5563]">
              No unlinked gigs match your search.
            </li>
          ) : (
            filtered.map((g) => (
              <li
                key={g.gig_id}
                data-testid={`link-candidate-${g.gig_id}`}
                className="flex items-center justify-between px-6 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-display text-sm font-bold">{g.title}</div>
                  <div className="text-[11px] text-[#4B5563]">
                    {g.category} · {g.scheduled_date || "Flexible"} ·{" "}
                    {g.location || "—"}
                  </div>
                </div>
                <Button
                  onClick={() => linkIt(g.gig_id)}
                  disabled={linkingId === g.gig_id}
                  className="h-9 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc]"
                >
                  <LinkIcon size={12} className="mr-1" />{" "}
                  {linkingId === g.gig_id ? "Linking…" : "Link"}
                </Button>
              </li>
            ))
          )}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
