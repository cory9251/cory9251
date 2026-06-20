/**
 * Admin-side view of a customer chat thread.
 *
 * Routed from /ops/customer-chats/:threadId. Lets admins read the full
 * conversation, see customer email/contractor roster (admin gets full
 * PII), and reply as "HCOB Team" (sender_type='admin' — shown in light
 * purple on both the customer view and the contractor view).
 *
 * Polls every 5s for new messages (same cadence as the customer page).
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft,
  ChatCircleDots,
  PaperPlaneTilt,
  Copy,
  Check,
  X,
  ArrowClockwise,
  UsersThree,
  EnvelopeSimple,
  Briefcase,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

function _shortTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString([], {
      hour: "numeric",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

export default function AdminCustomerChat() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const scrollRef = useRef(null);
  const lastMsgIdRef = useRef(null);

  async function loadAll(initial = false) {
    try {
      const [t, m] = await Promise.all([
        api.get(`/admin/customer-threads/${threadId}`),
        api.get(`/admin/customer-threads/${threadId}/messages`),
      ]);
      setThread(t.data);
      setMessages(m.data || []);
      setError(null);
    } catch (e) {
      if (initial) {
        const code = e?.response?.status;
        setError(
          code === 404
            ? "Chat not found — it may have been deleted."
            : "Couldn't load this chat. Try refreshing."
        );
      }
    } finally {
      if (initial) setLoading(false);
    }
  }

  useEffect(() => {
    loadAll(true);
    const id = setInterval(() => loadAll(false), 5000);
    return () => clearInterval(id);
  }, [threadId]);

  // Auto-scroll on new message
  useEffect(() => {
    if (!messages.length) return;
    const last = messages[messages.length - 1];
    if (last?.message_id !== lastMsgIdRef.current) {
      lastMsgIdRef.current = last?.message_id;
      requestAnimationFrame(() => {
        scrollRef.current?.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: "smooth",
        });
      });
    }
  }, [messages]);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      const r = await api.post(`/admin/customer-threads/${threadId}/messages`, {
        text,
      });
      setMessages((prev) => [...prev, r.data]);
      setDraft("");
    } catch (e) {
      const code = e?.response?.status;
      if (code === 410) {
        toast.error("This chat has ended.");
        loadAll(false);
      } else {
        toast.error(getErr(e));
      }
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  async function copyLink() {
    if (!thread?.customer_link) return;
    try {
      await navigator.clipboard.writeText(thread.customer_link);
      setCopied(true);
      toast.success("Link copied — paste it into a text/email");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy this link:", thread.customer_link);
    }
  }

  async function closeThread() {
    if (!window.confirm(`Close chat with ${thread.customer_name}?`)) return;
    try {
      await api.post(`/admin/customer-threads/${threadId}/close`, {
        reason: "Closed by admin",
      });
      await loadAll(false);
      toast.success("Chat closed");
    } catch (e) {
      toast.error(getErr(e));
    }
  }

  async function reopenThread() {
    try {
      await api.post(`/admin/customer-threads/${threadId}/reopen`, {});
      await loadAll(false);
      toast.success("Chat reopened");
    } catch (e) {
      toast.error(getErr(e));
    }
  }

  const isProject = thread?.scope_type === "project";
  const title = thread?.title || thread?.project_title || thread?.gig_title || "Customer chat";
  const closed = thread?.status === "closed";
  const contextHref = useMemo(() => {
    if (!thread) return "/ops/customer-chats";
    if (isProject && thread.project_id) return `/ops/projects/${thread.project_id}`;
    if (thread.gig_id) return `/ops/assignments/${thread.gig_id}`;
    return "/ops/projects";
  }, [thread, isProject]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xs font-mono uppercase tracking-widest text-[#6B7280]">
          Loading chat…
        </div>
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div
          className="bg-white border border-[#E5E7EB] max-w-md p-8 text-center"
          data-testid="admin-chat-error"
        >
          <ChatCircleDots size={36} className="mx-auto text-[#9CA3AF] mb-4" />
          <h1 className="text-xl font-black text-[#030712] mb-2">Chat unavailable</h1>
          <p className="text-sm text-[#6B7280]">{error || "Thread not found."}</p>
          <Button
            onClick={() => navigate(-1)}
            className="mt-4 rounded-none bg-[#030712] hover:bg-[#0044FF]"
            data-testid="admin-chat-back"
          >
            <ArrowLeft size={14} className="mr-1" /> Back
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen bg-[#F8FAFC] flex flex-col"
      data-testid="admin-customer-chat-page"
    >
      {/* Top bar */}
      <header className="bg-white border-b border-[#E5E7EB]">
        <div className="max-w-5xl mx-auto px-5 py-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(contextHref)}
            className="flex h-9 w-9 items-center justify-center border border-[#E5E7EB] hover:border-[#030712] hover:bg-[#F9FAFB]"
            data-testid="admin-chat-back"
            title={isProject ? "Back to project" : "Back to assignment"}
          >
            <ArrowLeft size={16} />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {isProject ? (
                <Briefcase size={14} weight="bold" className="text-[#0044FF]" />
              ) : (
                <ChatCircleDots size={14} weight="duotone" className="text-[#0044FF]" />
              )}
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
                {isProject ? "Project chat" : "Assignment chat"}
              </span>
              <span
                className={`text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 ${
                  closed
                    ? "bg-[#9CA3AF] text-white"
                    : "bg-[#10B981] text-white"
                }`}
              >
                {closed ? "Ended" : "Live"}
              </span>
            </div>
            <h1
              className="text-lg font-black text-[#030712] truncate -mt-0.5"
              data-testid="admin-chat-title"
            >
              {title}
            </h1>
          </div>
          <Button
            variant="outline"
            className="rounded-none border-[#0044FF] text-[#0044FF]"
            onClick={copyLink}
            data-testid="admin-chat-copy-link"
          >
            {copied ? (
              <>
                <Check size={14} className="mr-1" /> Copied
              </>
            ) : (
              <>
                <Copy size={14} className="mr-1" /> Copy link
              </>
            )}
          </Button>
          {closed ? (
            <Button
              variant="outline"
              className="rounded-none border-[#10B981] text-[#065F46]"
              onClick={reopenThread}
              data-testid="admin-chat-reopen"
            >
              <ArrowClockwise size={14} className="mr-1" /> Reopen
            </Button>
          ) : (
            <Button
              variant="outline"
              className="rounded-none border-[#EF4444] text-[#EF4444]"
              onClick={closeThread}
              data-testid="admin-chat-close"
            >
              <X size={14} className="mr-1" /> Close
            </Button>
          )}
        </div>
      </header>

      {/* Customer + crew info strip */}
      <div className="bg-white border-b border-[#E5E7EB]">
        <div className="max-w-5xl mx-auto px-5 py-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <div>
            <span className="font-mono uppercase tracking-widest text-[#6B7280] mr-2">
              Customer
            </span>
            <span
              className="font-bold text-[#030712]"
              data-testid="admin-chat-customer-name"
            >
              {thread.customer_name}
            </span>
          </div>
          {thread.customer_email && (
            <div className="flex items-center gap-1">
              <EnvelopeSimple size={12} className="text-[#9CA3AF]" />
              <a
                href={`mailto:${thread.customer_email}`}
                className="text-[#0044FF] hover:underline"
              >
                {thread.customer_email}
              </a>
            </div>
          )}
          {thread.contractors && thread.contractors.length > 0 && (
            <div className="flex items-center gap-2">
              <UsersThree size={12} className="text-[#9CA3AF]" />
              <span className="font-mono uppercase tracking-widest text-[10px] text-[#6B7280]">
                Crew ({thread.contractors.length})
              </span>
              <div className="flex flex-wrap items-center gap-1">
                {thread.contractors.map((c) => (
                  <span
                    key={c.user_id}
                    className="px-2 py-0.5 bg-[#F3F4F6] border border-[#E5E7EB] text-[#030712]"
                  >
                    {c.first_name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {closed && (
        <div className="bg-[#FFFBEB] border-b border-[#F59E0B]/40">
          <div className="max-w-5xl mx-auto px-5 py-2 text-xs text-[#92400E]">
            <strong>This chat is closed.</strong>{" "}
            {thread.closed_reason || "No new messages can be sent."}
          </div>
        </div>
      )}

      {/* Messages */}
      <main ref={scrollRef} className="flex-1 overflow-y-auto" data-testid="admin-chat-messages">
        <div className="max-w-5xl mx-auto px-5 py-6 space-y-3">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <ChatCircleDots size={40} className="mx-auto text-[#9CA3AF] mb-3" />
              <p className="text-sm text-[#6B7280]">
                No messages yet. Start the conversation below — the customer will get an email.
              </p>
            </div>
          ) : (
            messages.map((m) => {
              const mine = m.sender_type === "admin";
              const isCustomer = m.sender_type === "customer";
              return (
                <div
                  key={m.message_id}
                  className={`flex ${mine ? "justify-end" : "justify-start"}`}
                  data-testid={`admin-chat-msg-${m.message_id}`}
                >
                  <div
                    className={`max-w-[75%] px-4 py-3 text-sm ${
                      mine
                        ? "bg-[#7C3AED] text-white"
                        : isCustomer
                        ? "bg-[#0044FF] text-white"
                        : "bg-white border border-[#E5E7EB] text-[#030712]"
                    }`}
                  >
                    <div
                      className={`text-[10px] font-mono uppercase tracking-widest mb-1 ${
                        mine || isCustomer ? "text-white/80" : "text-[#0044FF]"
                      }`}
                    >
                      {mine
                        ? "HCOB Team (you)"
                        : isCustomer
                        ? thread.customer_name
                        : m.sender_name || m.sender_first_name}
                    </div>
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {m.text}
                    </div>
                    <div
                      className={`text-[10px] mt-1 ${
                        mine || isCustomer ? "text-white/70" : "text-[#9CA3AF]"
                      }`}
                    >
                      {_shortTime(m.created_at)}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>

      {/* Composer */}
      <footer className="bg-white border-t border-[#E5E7EB]">
        <div className="max-w-5xl mx-auto px-5 py-3 flex items-end gap-2">
          <textarea
            data-testid="admin-chat-composer"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              closed
                ? "This chat is closed."
                : "Reply as HCOB Team — Enter to send, Shift+Enter for new line"
            }
            rows={1}
            disabled={closed}
            className="flex-1 resize-none border border-[#E5E7EB] px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#7C3AED] focus:border-transparent disabled:bg-[#F3F4F6] min-h-[42px] max-h-32"
          />
          <button
            type="button"
            data-testid="admin-chat-send"
            onClick={send}
            disabled={closed || sending || !draft.trim()}
            className="bg-[#7C3AED] text-white px-4 py-2.5 font-medium text-sm hover:bg-[#5B21B6] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 h-[42px]"
          >
            <PaperPlaneTilt size={16} weight="fill" />
            <span>{sending ? "Sending…" : "Send"}</span>
          </button>
        </div>
      </footer>
    </div>
  );
}
