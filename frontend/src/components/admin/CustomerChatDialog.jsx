/**
 * Admin dialog: generate / view customer chat links for a gig.
 *
 * Opens from the GigDetail page. Lists all existing customer threads for
 * the gig with copy-link buttons + a create form for a new one.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ChatCircleDots, Copy, Check, X, ArrowClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CustomerChatDialog({ gigId, trigger }) {
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/gigs/${gigId}/customer-threads`, {
        withCredentials: true,
      });
      setThreads(r.data?.items || []);
    } catch {
      setThreads([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open) load();
  }, [open]);

  async function create() {
    if (!name.trim()) {
      toast.error("Add the customer's name first");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(
        `${API}/admin/customer-threads`,
        {
          gig_id: gigId,
          customer_name: name.trim(),
          customer_email: email.trim() || null,
        },
        { withCredentials: true }
      );
      setName("");
      setEmail("");
      toast.success("Customer chat link ready — copy below");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't create chat link");
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
    if (!window.confirm(`Close chat with ${t.customer_name}? They won't be able to message.`)) return;
    try {
      await axios.post(
        `${API}/admin/customer-threads/${t.thread_id}/close`,
        { reason: "Closed by admin" },
        { withCredentials: true }
      );
      await load();
      toast.success("Chat closed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't close chat");
    }
  }

  async function reopenThread(t) {
    try {
      await axios.post(
        `${API}/admin/customer-threads/${t.thread_id}/reopen`,
        {},
        { withCredentials: true }
      );
      await load();
      toast.success("Chat reopened");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't reopen chat");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="rounded-none max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-black tracking-tight flex items-center gap-2">
            <ChatCircleDots size={20} className="text-[#0044FF]" />
            Customer chat links
          </DialogTitle>
        </DialogHeader>

        {/* Create form */}
        <div className="border border-[#E5E7EB] p-4 bg-[#F8FAFC]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280] mb-3">
            New chat link
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wide text-[#6B7280]">
                Customer name
              </Label>
              <Input
                data-testid="customer-thread-name"
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
                data-testid="customer-thread-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@example.com"
                className="rounded-none mt-1"
              />
            </div>
          </div>
          <Button
            data-testid="customer-thread-create"
            onClick={create}
            disabled={submitting}
            className="mt-3 w-full rounded-none bg-[#030712] hover:bg-[#0044FF]"
          >
            {submitting ? "Creating…" : "Generate link"}
          </Button>
        </div>

        {/* Existing threads */}
        <div className="mt-2 max-h-[40vh] overflow-y-auto space-y-2">
          {loading && (
            <div className="text-xs text-[#6B7280] py-4 text-center">Loading…</div>
          )}
          {!loading && threads.length === 0 && (
            <div className="text-sm text-[#6B7280] py-6 text-center">
              No customer chat links yet for this assignment.
            </div>
          )}
          {!loading &&
            threads.map((t) => (
              <div
                key={t.thread_id}
                className="border border-[#E5E7EB] p-3 flex flex-col gap-2"
                data-testid={`customer-thread-row-${t.thread_id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-bold text-sm text-[#030712] truncate">
                      {t.customer_name}
                    </div>
                    {t.customer_email && (
                      <div className="text-xs text-[#6B7280] truncate">
                        {t.customer_email}
                      </div>
                    )}
                  </div>
                  <span
                    className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 ${
                      t.status === "active"
                        ? "bg-[#10B981] text-white"
                        : "bg-[#9CA3AF] text-white"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <code className="text-[11px] flex-1 truncate bg-[#F3F4F6] px-2 py-1 font-mono text-[#374151] border border-[#E5E7EB]">
                    {t.customer_link}
                  </code>
                  <Button
                    data-testid={`customer-thread-copy-${t.thread_id}`}
                    size="sm"
                    variant="outline"
                    className="rounded-none border-[#0044FF] text-[#0044FF]"
                    onClick={() => copyLink(t)}
                  >
                    {copiedId === t.thread_id ? (
                      <>
                        <Check size={14} className="mr-1" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy size={14} className="mr-1" /> Copy
                      </>
                    )}
                  </Button>
                  {t.status === "active" ? (
                    <Button
                      data-testid={`customer-thread-close-${t.thread_id}`}
                      size="sm"
                      variant="outline"
                      className="rounded-none border-[#EF4444] text-[#EF4444]"
                      onClick={() => closeThread(t)}
                    >
                      <X size={14} className="mr-1" /> Close
                    </Button>
                  ) : (
                    <Button
                      data-testid={`customer-thread-reopen-${t.thread_id}`}
                      size="sm"
                      variant="outline"
                      className="rounded-none border-[#10B981] text-[#065F46]"
                      onClick={() => reopenThread(t)}
                    >
                      <ArrowClockwise size={14} className="mr-1" /> Reopen
                    </Button>
                  )}
                </div>
                {t.last_message_preview && (
                  <div className="text-xs text-[#6B7280] truncate mt-1">
                    <span className="font-mono uppercase text-[10px] tracking-widest text-[#9CA3AF] mr-2">
                      Last
                    </span>
                    {t.last_message_preview}
                  </div>
                )}
              </div>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
