/**
 * Inline customer-chat panel for contractors (and admins, eventually).
 *
 * Lists every customer thread on this gig, lets the contractor expand one
 * and chat live with the customer. PII-stripped (customer first name only).
 *
 * Polls every 5s when expanded.
 */
import React, { useEffect, useRef, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { ChatCircleDots, PaperPlaneTilt, CaretDown, CaretUp } from "@phosphor-icons/react";

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

function ThreadCard({ thread, onChanged }) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  async function fetchMessages() {
    try {
      const { data } = await api.get(
        `/crew/customer-threads/${thread.thread_id}/messages`
      );
      setMessages(data || []);
    } catch {
      /* ignore */
    }
  }

  // Load + poll on expand
  useEffect(() => {
    if (!expanded) return undefined;
    setLoading(true);
    fetchMessages().finally(() => setLoading(false));
    const id = setInterval(fetchMessages, 5000);
    return () => clearInterval(id);
  }, [expanded]);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    if (!expanded || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, expanded]);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      const { data } = await api.post(
        `/crew/customer-threads/${thread.thread_id}/messages`,
        { text }
      );
      setMessages((prev) => [...prev, data]);
      setDraft("");
      if (onChanged) onChanged();
    } catch (e) {
      const code = e?.response?.status;
      if (code === 410) {
        toast.error("This chat has ended.");
        if (onChanged) onChanged();
      } else {
        toast.error(getErr(e));
      }
    } finally {
      setSending(false);
    }
  }

  const closed = thread.status === "closed";

  return (
    <div
      className="border border-[#E5E7EB] bg-white"
      data-testid={`crew-customer-thread-${thread.thread_id}`}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#F8FAFC]"
        data-testid={`crew-customer-thread-toggle-${thread.thread_id}`}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <ChatCircleDots
              size={16}
              className={closed ? "text-[#9CA3AF]" : "text-[#0044FF]"}
              weight="duotone"
            />
            <span className="font-bold text-sm text-[#030712]">
              {thread.customer_first_name}
            </span>
            {thread.scope_type === "project" && (
              <span
                className="text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 bg-[#0044FF] text-white"
                title="Project-wide chat (multiple gigs)"
              >
                Project
              </span>
            )}
            <span
              className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 ${
                closed
                  ? "bg-[#9CA3AF] text-white"
                  : "bg-[#10B981] text-white"
              }`}
            >
              {closed ? "Ended" : "Live"}
            </span>
          </div>
          {thread.last_message_preview && (
            <div className="text-xs text-[#6B7280] truncate mt-1">
              {thread.last_message_preview}
            </div>
          )}
        </div>
        {expanded ? <CaretUp size={16} /> : <CaretDown size={16} />}
      </button>

      {expanded && (
        <div className="border-t border-[#E5E7EB]">
          {/* Messages */}
          <div
            ref={scrollRef}
            className="max-h-72 overflow-y-auto p-3 space-y-2 bg-[#F8FAFC]"
            data-testid={`crew-customer-thread-messages-${thread.thread_id}`}
          >
            {loading && (
              <div className="text-xs text-[#6B7280] text-center py-4">
                Loading…
              </div>
            )}
            {!loading && messages.length === 0 && (
              <div className="text-xs text-[#6B7280] text-center py-4">
                No messages yet — say hi to the customer.
              </div>
            )}
            {messages.map((m) => {
              const mine = m.sender_type === "contractor";
              return (
                <div
                  key={m.message_id}
                  className={`flex ${mine ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] px-3 py-2 text-sm ${
                      mine
                        ? "bg-[#0044FF] text-white"
                        : m.sender_type === "admin"
                        ? "bg-[#F3E8FF] text-[#5B21B6] border border-[#DDD6FE]"
                        : "bg-white border border-[#E5E7EB] text-[#030712]"
                    }`}
                  >
                    {!mine && (
                      <div className="text-[10px] font-mono uppercase tracking-widest mb-0.5 opacity-70">
                        {m.sender_type === "admin"
                          ? "HCOB Team"
                          : m.sender_first_name}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {m.text}
                    </div>
                    <div
                      className={`text-[9px] mt-0.5 ${
                        mine ? "text-white/70" : "text-[#9CA3AF]"
                      }`}
                    >
                      {_shortTime(m.created_at)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Composer */}
          <div className="border-t border-[#E5E7EB] p-2 flex gap-2 bg-white">
            <input
              type="text"
              data-testid={`crew-customer-composer-${thread.thread_id}`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={closed ? "This chat has ended" : "Reply to customer…"}
              disabled={closed}
              className="flex-1 border border-[#E5E7EB] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0044FF] disabled:bg-[#F3F4F6]"
            />
            <button
              type="button"
              data-testid={`crew-customer-send-${thread.thread_id}`}
              onClick={send}
              disabled={closed || sending || !draft.trim()}
              className="bg-[#030712] text-white px-3 py-2 text-sm hover:bg-[#0044FF] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <PaperPlaneTilt size={14} weight="fill" />
              <span className="hidden sm:inline">{sending ? "…" : "Send"}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CustomerChatPanel({ gigId, projectId }) {
  const [threads, setThreads] = useState([]);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    try {
      // Scope: prefer projectId when both provided (avoids duplicate work
      // when a gig page also wants the project view).
      const url = projectId
        ? `/crew/projects/${projectId}/customer-threads`
        : `/crew/gigs/${gigId}/customer-threads`;
      const { data } = await api.get(url);
      setThreads(data?.items || []);
    } catch {
      setThreads([]);
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    load();
    // Refresh thread list every 30s so new threads created by admin show up
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [gigId, projectId]);

  if (!loaded || threads.length === 0) return null;

  return (
    <div className="mx-0 mt-5" data-testid="worker-customer-chat-panel">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-mono uppercase tracking-widest text-[#6B7280]">
          Customer chats ({threads.length})
        </h3>
      </div>
      <div className="space-y-2">
        {threads.map((t) => (
          <ThreadCard key={t.thread_id} thread={t} onChanged={load} />
        ))}
      </div>
    </div>
  );
}
