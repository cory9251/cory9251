import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Megaphone } from "@phosphor-icons/react";

export const AnnouncementsPopup = () => {
  const [queue, setQueue] = useState([]);

  useEffect(() => {
    api.get("/announcements")
      .then((r) => setQueue((r.data.items || []).filter((a) => a.popup && !a.dismissed)))
      .catch(() => {});
  }, []);

  const current = queue[0];
  if (!current) return null;

  const dismiss = async () => {
    try {
      await api.post(`/announcements/${current.announcement_id}/dismiss`);
    } catch {
      /* non-blocking */
    }
    setQueue((q) => q.slice(1));
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) setQueue((q) => q.slice(1)); }}>
      <DialogContent data-testid="announcement-popup" className="max-w-md rounded-none border-2 border-[#030712]">
        <DialogHeader>
          <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest text-[#0044FF]">
            <Megaphone size={14} weight="fill" /> Announcement from HCOB
          </div>
          <DialogTitle className="font-display text-xl font-black" data-testid="announcement-popup-title">
            {current.title}
          </DialogTitle>
          <DialogDescription className="sr-only">Company announcement</DialogDescription>
        </DialogHeader>
        <div className="whitespace-pre-line text-sm leading-relaxed text-[#374151]" data-testid="announcement-popup-body">
          {current.body}
        </div>
        <div className="text-xs text-[#9CA3AF]">
          {new Date(current.created_at).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
          {current.created_by_name ? ` · ${current.created_by_name}` : ""}
        </div>
        <Button
          data-testid="announcement-popup-dismiss"
          onClick={dismiss}
          className="h-11 w-full rounded-none bg-[#030712] font-bold text-white hover:bg-[#1f2937]"
        >
          Got it{queue.length > 1 ? ` · ${queue.length - 1} more` : ""}
        </Button>
      </DialogContent>
    </Dialog>
  );
};
