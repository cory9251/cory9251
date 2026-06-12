import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { MagnifyingGlass, ShieldCheck, User as UserIcon } from "@phosphor-icons/react";

/**
 * Pick a user to start a new DM with.
 * onOpened(thread) — called after thread is opened/created.
 */
export default function NewMessageDialog({ open, onOpenChange, onOpened }) {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setBusy(true);
    api
      .get("/messages/eligible-users")
      .then(({ data }) => setUsers(data || []))
      .catch((e) => toast.error(getErr(e)))
      .finally(() => setBusy(false));
  }, [open]);

  const filtered = users.filter((u) => {
    const s = q.trim().toLowerCase();
    if (!s) return true;
    return (
      (u.name || "").toLowerCase().includes(s) ||
      (u.email || "").toLowerCase().includes(s) ||
      (u.role || "").toLowerCase().includes(s)
    );
  });

  const openDM = async (u) => {
    setOpening(u.user_id);
    try {
      const { data } = await api.post("/messages/threads/dm", { user_id: u.user_id });
      onOpened?.(data);
      onOpenChange(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setOpening(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-none border-[#030712]" data-testid="new-message-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black tracking-tight">
            New Message
          </DialogTitle>
        </DialogHeader>
        <div className="relative">
          <MagnifyingGlass
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]"
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by name, email or role…"
            className="pl-9 rounded-none border-[#E5E7EB] focus-visible:ring-0 focus-visible:border-[#030712]"
            data-testid="new-message-search"
            autoFocus
          />
        </div>
        <ScrollArea className="h-72 -mx-2">
          {busy ? (
            <div className="p-6 text-center text-sm text-[#737373]">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="p-6 text-center text-sm text-[#737373]" data-testid="new-message-empty">
              {users.length === 0 && user?.role === "worker" ? (
                <>
                  No one to message yet.
                  <br />
                  <span className="text-xs">
                    You can DM HCOB admins anytime, and any worker after you've shared a gig with them.
                  </span>
                </>
              ) : (
                "No matching users."
              )}
            </div>
          ) : (
            <ul className="divide-y divide-[#F3F4F6]">
              {filtered.map((u) => (
                <li key={u.user_id}>
                  <button
                    type="button"
                    onClick={() => openDM(u)}
                    disabled={opening === u.user_id}
                    data-testid={`new-message-user-${u.user_id}`}
                    className="flex w-full items-center gap-3 px-3 py-3 text-left hover:bg-[#FFFBEB] disabled:opacity-50"
                  >
                    <div className="grid h-9 w-9 place-items-center bg-[#030712] text-white">
                      {u.role === "admin" ? (
                        <ShieldCheck size={16} weight="fill" />
                      ) : (
                        <UserIcon size={16} weight="fill" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold">
                        {u.name || u.email}
                      </div>
                      <div className="truncate text-[11px] text-[#737373]">
                        {u.email} ·{" "}
                        <span className="uppercase tracking-widest">
                          {u.is_owner
                            ? "Owner"
                            : u.is_program_manager
                            ? "Program Manager"
                            : u.role}
                        </span>
                      </div>
                    </div>
                    {opening === u.user_id && (
                      <span className="text-[10px] font-mono uppercase tracking-widest text-[#737373]">
                        Opening…
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
