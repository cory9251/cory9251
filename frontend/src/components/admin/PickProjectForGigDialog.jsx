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
import { Checkbox } from "@/components/ui/checkbox";
import {
  MagnifyingGlass,
  Link as LinkIcon,
  FolderSimple,
  Plus,
} from "@phosphor-icons/react";
import CreateProjectDialog from "@/components/admin/CreateProjectDialog";

export default function PickProjectForGigDialog({
  open,
  onOpenChange,
  gigId,
  onLinked,
}) {
  const [projects, setProjects] = useState([]);
  const [q, setQ] = useState("");
  const [sync, setSync] = useState(false);
  const [linkingId, setLinkingId] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/projects?archived=false");
      setProjects(data || []);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    if (!open) return;
    load();
  }, [open]);

  const linkIt = async (project_id) => {
    setLinkingId(project_id);
    try {
      await api.post(`/gigs/${gigId}/link-to-project`, {
        project_id,
        sync_defaults: sync,
      });
      toast.success("Gig linked to project");
      onLinked && onLinked();
      onOpenChange(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLinkingId(null);
    }
  };

  const filtered = projects.filter((p) =>
    q.trim()
      ? (p.title || "").toLowerCase().includes(q.toLowerCase()) ||
        (p.client_name || "").toLowerCase().includes(q.toLowerCase())
      : true
  );

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          data-testid="pick-project-dialog"
          className="max-h-[85vh] max-w-xl overflow-hidden rounded-none border-[#030712] p-0"
        >
          <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
            <DialogTitle className="font-display text-lg font-black">
              Link gig to a project
            </DialogTitle>
            <p className="text-xs text-[#4B5563]">
              Group this gig with others that share a job site so workers can
              coordinate.
            </p>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4">
            <div className="flex items-center gap-2">
              <MagnifyingGlass size={14} className="text-[#4B5563]" />
              <Input
                data-testid="pick-project-search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search by title or client…"
                className="h-10 rounded-none border-[#030712]"
              />
              <Button
                onClick={() => setCreateOpen(true)}
                variant="outline"
                className="h-10 shrink-0 rounded-none border-[#030712]"
                data-testid="pick-project-new"
              >
                <Plus size={12} className="mr-1" /> New
              </Button>
            </div>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                data-testid="pick-project-sync"
                checked={sync}
                onCheckedChange={(v) => setSync(!!v)}
              />
              Also overwrite this gig&apos;s location/date/payment timeline with
              the project&apos;s defaults
            </label>
          </div>
          <ul className="max-h-[55vh] divide-y divide-[#E5E7EB] overflow-y-auto border-t border-[#E5E7EB]">
            {filtered.length === 0 ? (
              <li className="bg-[#F9FAFB] p-6 text-center text-xs text-[#4B5563]">
                {projects.length === 0
                  ? "No active projects yet. Click +New to create one."
                  : "No projects match your search."}
              </li>
            ) : (
              filtered.map((p) => (
                <li
                  key={p.project_id}
                  data-testid={`pick-project-${p.project_id}`}
                  className="flex items-center justify-between gap-3 px-6 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 font-display text-sm font-bold">
                      <FolderSimple size={12} weight="duotone" /> {p.title}
                    </div>
                    <div className="text-[11px] text-[#4B5563]">
                      {p.client_name ? `${p.client_name} · ` : ""}
                      {p.gig_count} gig{p.gig_count === 1 ? "" : "s"} ·{" "}
                      {p.slots_filled}/{p.slots_total} slots
                    </div>
                  </div>
                  <Button
                    onClick={() => linkIt(p.project_id)}
                    disabled={linkingId === p.project_id}
                    className="h-9 shrink-0 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc]"
                  >
                    <LinkIcon size={12} className="mr-1" />{" "}
                    {linkingId === p.project_id ? "Linking…" : "Link"}
                  </Button>
                </li>
              ))
            )}
          </ul>
        </DialogContent>
      </Dialog>
      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(p) => {
          load();
          linkIt(p.project_id);
        }}
      />
    </>
  );
}
