/**
 * Project-wide customer chat dialog.
 *
 * Same shape as the per-gig CustomerChatDialog (Iter 63) but with an
 * admin-curated PARTICIPANT PICKER instead of an automatic gig roster.
 * Per the user spec: admin picks who's in (choice 1c), one chat per
 * project (3a), never auto-close (2b — manual only).
 *
 * Pulls the candidate contractor list from the project's `crew` array
 * that the admin project detail page already loads.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ChatCircleDots,
  Copy,
  Check,
  X,
  ArrowClockwise,
  UsersThree,
} from "@phosphor-icons/react";

export default function ProjectCustomerChatDialog({ projectId, crew = [], trigger }) {
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [picked, setPicked] = useState({}); // {worker_id: true}
  const [submitting, setSubmitting] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Unique workers across all gigs in the project (de-dupe by worker_id)
  const candidates = useMemo(() => {
    const map = new Map();
    for (const c of crew || []) {
      if (!c.worker_id) continue;
      if (!map.has(c.worker_id)) {
        map.set(c.worker_id, {
          worker_id: c.worker_id,
          name: c.worker_name || c.worker_email || "(unnamed)",
          gigs: new Set(),
        });
      }
      if (c.gig_title) map.get(c.worker_id).gigs.add(c.gig_title);
    }
    return Array.from(map.values()).map((w) => ({
      ...w,
      gigs: Array.from(w.gigs),
    }));
  }, [crew]);

  const allPickedInitially = useMemo(() => {
    const o = {};
    for (const w of candidates) o[w.worker_id] = true;
    return o;
  }, [candidates]);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get(`/admin/projects/${projectId}/customer-threads`);
      setThreads(r.data?.items || []);
    } catch {
      setThreads([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    load();
    setPicked(allPickedInitially);
  }, [open, projectId, allPickedInitially]);

  function togglePick(id) {
    setPicked((p) => ({ ...p, [id]: !p[id] }));
  }

  function pickAll() {
    setPicked(allPickedInitially);
  }

  function pickNone() {
    setPicked({});
  }

  async function create() {
    if (!name.trim()) {
      toast.error("Add the customer's name first");
      return;
    }
    const ids = Object.keys(picked).filter((k) => picked[k]);
    if (ids.length === 0) {
      const ok = window.confirm(
        "No contractors picked. The customer will only chat with admins. Continue?"
      );
      if (!ok) return;
    }
    setSubmitting(true);
    try {
      await api.post(`/admin/projects/${projectId}/customer-threads`, {
        customer_name: name.trim(),
        customer_email: email.trim() || null,
        contractor_ids: ids,
      });
      setName("");
      setEmail("");
      toast.success("Project chat link ready — copy below");
      await load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function copyLink(t) {
    try {
      await navigator.clipboard.writeText(t.customer_link);
      setCopiedId(t.thread_id);
      toast.success("Link copied — paste it into a text/email");
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      window.prompt("Copy this link:", t.customer_link);
    }
  }

  async function closeThread(t) {
    if (!window.confirm(`Close project chat with ${t.customer_name}?`)) return;
    try {
      await api.post(`/admin/customer-threads/${t.thread_id}/close`, {
        reason: "Closed by admin",
      });
      await load();
      toast.success("Chat closed");
    } catch (e) {
      toast.error(getErr(e));
    }
  }

  async function reopenThread(t) {
    try {
      await api.post(`/admin/customer-threads/${t.thread_id}/reopen`, {});
      await load();
      toast.success("Chat reopened");
    } catch (e) {
      toast.error(getErr(e));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="rounded-none max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-black tracking-tight flex items-center gap-2">
            <ChatCircleDots size={20} className="text-[#0044FF]" />
            Project customer chat
          </DialogTitle>
          <DialogDescription className="text-xs text-[#6B7280]">
            Generate a shareable link the customer uses to chat with the picked contractors and the HCOB team.
          </DialogDescription>
        </DialogHeader>

        {/* Create form */}
        <div className="border border-[#E5E7EB] p-4 bg-[#F8FAFC]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280] mb-3">
            New project chat link
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wide text-[#6B7280]">
                Customer name
              </Label>
              <Input
                data-testid="project-thread-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                className="rounded-none mt-1"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wide text-[#6B7280]">
                Email (for replies)
              </Label>
              <Input
                data-testid="project-thread-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@example.com"
                className="rounded-none mt-1"
              />
            </div>
          </div>

          {/* Participant picker */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
                Contractors in this chat ({Object.values(picked).filter(Boolean).length}/{candidates.length})
              </div>
              <div className="flex gap-1">
                <button
                  type="button"
                  data-testid="project-thread-pick-all"
                  onClick={pickAll}
                  className="text-[10px] uppercase tracking-widest text-[#0044FF] hover:underline px-1"
                >
                  All
                </button>
                <span className="text-[#E5E7EB]">·</span>
                <button
                  type="button"
                  data-testid="project-thread-pick-none"
                  onClick={pickNone}
                  className="text-[10px] uppercase tracking-widest text-[#6B7280] hover:underline px-1"
                >
                  None
                </button>
              </div>
            </div>
            {candidates.length === 0 ? (
              <div className="text-xs text-[#6B7280] border border-dashed border-[#E5E7EB] p-4 text-center">
                No contractors on this project yet. Add a gig + accept workers first.
              </div>
            ) : (
              <div className="max-h-44 overflow-y-auto border border-[#E5E7EB]">
                {candidates.map((w) => {
                  const on = !!picked[w.worker_id];
                  return (
                    <label
                      key={w.worker_id}
                      data-testid={`project-thread-pick-${w.worker_id}`}
                      className={`flex items-center gap-3 px-3 py-2 border-b border-[#E5E7EB] last:border-b-0 cursor-pointer ${
                        on ? "bg-[#F5F8FF]" : "bg-white hover:bg-[#F9FAFB]"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={() => togglePick(w.worker_id)}
                        className="h-4 w-4 accent-[#0044FF]"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-bold text-[#030712] truncate">
                          {w.name}
                        </div>
                        {w.gigs.length > 0 && (
                          <div className="text-[11px] text-[#6B7280] truncate">
                            On: {w.gigs.join(" · ")}
                          </div>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <Button
            data-testid="project-thread-create"
            onClick={create}
            disabled={submitting}
            className="mt-3 w-full rounded-none bg-[#030712] hover:bg-[#0044FF]"
          >
            {submitting ? "Creating…" : "Generate link"}
          </Button>
        </div>

        {/* Existing threads */}
        <div className="mt-2 space-y-2">
          {loading && (
            <div className="text-xs text-[#6B7280] py-4 text-center">Loading…</div>
          )}
          {!loading && threads.length === 0 && (
            <div className="text-sm text-[#6B7280] py-6 text-center">
              No project chats yet.
            </div>
          )}
          {!loading &&
            threads.map((t) => (
              <ThreadRow
                key={t.thread_id}
                thread={t}
                candidates={candidates}
                copiedId={copiedId}
                onCopy={copyLink}
                onClose={closeThread}
                onReopen={reopenThread}
                onParticipantsChanged={load}
              />
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ThreadRow({ thread, candidates, copiedId, onCopy, onClose, onReopen, onParticipantsChanged }) {
  const [editing, setEditing] = useState(false);
  const [picked, setPicked] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const initial = {};
    for (const id of thread.participant_contractor_ids || []) initial[id] = true;
    setPicked(initial);
  }, [thread]);

  async function save() {
    setSaving(true);
    try {
      const ids = Object.keys(picked).filter((k) => picked[k]);
      await api.patch(`/admin/customer-threads/${thread.thread_id}/participants`, {
        contractor_ids: ids,
      });
      toast.success("Participants updated");
      setEditing(false);
      if (onParticipantsChanged) onParticipantsChanged();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="border border-[#E5E7EB] p-3 space-y-2"
      data-testid={`project-thread-row-${thread.thread_id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-bold text-sm text-[#030712] truncate">
            {thread.customer_name}
          </div>
          {thread.customer_email && (
            <div className="text-xs text-[#6B7280] truncate">
              {thread.customer_email}
            </div>
          )}
          <div className="text-[11px] text-[#0044FF] mt-1 flex items-center gap-1">
            <UsersThree size={12} weight="bold" />
            {(thread.participant_contractor_ids || []).length} contractor
            {(thread.participant_contractor_ids || []).length === 1 ? "" : "s"}
          </div>
        </div>
        <span
          className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 ${
            thread.status === "active" ? "bg-[#10B981] text-white" : "bg-[#9CA3AF] text-white"
          }`}
        >
          {thread.status}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <code className="text-[11px] flex-1 truncate bg-[#F3F4F6] px-2 py-1 font-mono text-[#374151] border border-[#E5E7EB]">
          {thread.customer_link}
        </code>
        <Button
          data-testid={`project-thread-copy-${thread.thread_id}`}
          size="sm"
          variant="outline"
          className="rounded-none border-[#0044FF] text-[#0044FF]"
          onClick={() => onCopy(thread)}
        >
          {copiedId === thread.thread_id ? (
            <>
              <Check size={14} className="mr-1" /> Copied
            </>
          ) : (
            <>
              <Copy size={14} className="mr-1" /> Copy
            </>
          )}
        </Button>
        <Button
          data-testid={`project-thread-edit-${thread.thread_id}`}
          size="sm"
          variant="outline"
          className="rounded-none border-[#030712] text-[#030712]"
          onClick={() => setEditing((v) => !v)}
        >
          {editing ? "Cancel" : "Edit participants"}
        </Button>
        {thread.status === "active" ? (
          <Button
            data-testid={`project-thread-close-${thread.thread_id}`}
            size="sm"
            variant="outline"
            className="rounded-none border-[#EF4444] text-[#EF4444]"
            onClick={() => onClose(thread)}
          >
            <X size={14} className="mr-1" /> Close
          </Button>
        ) : (
          <Button
            data-testid={`project-thread-reopen-${thread.thread_id}`}
            size="sm"
            variant="outline"
            className="rounded-none border-[#10B981] text-[#065F46]"
            onClick={() => onReopen(thread)}
          >
            <ArrowClockwise size={14} className="mr-1" /> Reopen
          </Button>
        )}
      </div>

      {editing && (
        <div className="bg-[#F8FAFC] p-2 border border-[#E5E7EB] mt-1">
          <div className="max-h-40 overflow-y-auto">
            {candidates.map((w) => {
              const on = !!picked[w.worker_id];
              return (
                <label
                  key={w.worker_id}
                  data-testid={`project-thread-edit-pick-${thread.thread_id}-${w.worker_id}`}
                  className="flex items-center gap-2 py-1 cursor-pointer text-sm"
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      setPicked((p) => ({ ...p, [w.worker_id]: !p[w.worker_id] }))
                    }
                    className="h-4 w-4 accent-[#0044FF]"
                  />
                  <span className="text-[#030712]">{w.name}</span>
                </label>
              );
            })}
          </div>
          <Button
            data-testid={`project-thread-save-${thread.thread_id}`}
            size="sm"
            disabled={saving}
            onClick={save}
            className="mt-2 rounded-none bg-[#030712] hover:bg-[#0044FF]"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      )}

      {thread.last_message_preview && (
        <div className="text-xs text-[#6B7280] truncate mt-1">
          <span className="font-mono uppercase text-[10px] tracking-widest text-[#9CA3AF] mr-2">
            Last
          </span>
          {thread.last_message_preview}
        </div>
      )}
    </div>
  );
}
