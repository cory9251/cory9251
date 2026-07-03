/**
 * Customer ↔ Contractor magic-link chat page.
 *
 * Public route: `/c/:token` (no login required).
 * Customer enters here from a link an admin texted/emailed them.
 *
 * Polls for new messages every 5s. Auto-scrolls to the latest message.
 * Read-only with a friendly notice when the underlying assignment is
 * marked completed (the backend flips the thread to `status=closed`).
 */
import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { BACKEND_URL } from "@/lib/api";
import { ChatCircle, PaperPlaneTilt, Lock, Lightning } from "@phosphor-icons/react";

const API = `${BACKEND_URL}/api`;

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

export default function CustomerChat() {
  const { token } = useParams();
  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);
  const lastMsgIdRef = useRef(null);

  // Initial load + thread polling
  useEffect(() => {
    let cancel = false;
    async function load() {
      try {
        const t = await axios.get(`${API}/customer/threads/${token}`);
        if (cancel) return;
        setThread(t.data);
        const m = await axios.get(`${API}/customer/threads/${token}/messages`);
        if (cancel) return;
        setMessages(m.data || []);
      } catch (e) {
        if (cancel) return;
        const code = e?.response?.status;
        setError(
          code === 404
            ? "This chat link is invalid or expired."
            : "We couldn't load this chat. Try refreshing the page."
        );
      } finally {
        if (!cancel) setLoading(false);
      }
    }
    load();
    return () => {
      cancel = true;
    };
  }, [token]);

  // Poll for new messages every 5s — cheap & deterministic, no websockets.
  useEffect(() => {
    if (!thread) return undefined;
    const id = setInterval(async () => {
      try {
        const m = await axios.get(`${API}/customer/threads/${token}/messages`);
        setMessages(m.data || []);
        // Also re-check thread status (might have auto-closed if gig completed)
        const t = await axios.get(`${API}/customer/threads/${token}`);
        setThread(t.data);
      } catch {
        /* ignore transient failures during polling */
      }
    }, 5000);
    return () => clearInterval(id);
  }, [thread, token]);

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
      const r = await axios.post(`${API}/customer/threads/${token}/messages`, {
        text,
      });
      setMessages((prev) => [...prev, r.data]);
      setDraft("");
    } catch (e) {
      const code = e?.response?.status;
      if (code === 410) {
        toast.error("This chat has ended.");
        // Refresh thread to surface the closed banner.
        try {
          const t = await axios.get(`${API}/customer/threads/${token}`);
          setThread(t.data);
        } catch { /* noop */ }
      } else {
        toast.error("Couldn't send — please try again.");
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <div className="text-[#6B7280] font-mono text-xs uppercase tracking-widest">
          Loading chat…
        </div>
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC] p-6">
        <div
          className="bg-white border border-[#E5E7EB] max-w-md p-8 text-center"
          data-testid="customer-chat-error"
        >
          <Lock size={36} className="mx-auto text-[#9CA3AF] mb-4" />
          <h1 className="text-xl font-black text-[#030712] mb-2">Chat unavailable</h1>
          <p className="text-sm text-[#6B7280]">{error || "Link not found."}</p>
        </div>
      </div>
    );
  }

  const closed = thread.status === "closed";
  const contractors = thread.contractors || [];

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC]" data-testid="customer-chat-page">
      {/* Header bar — branded, no nav */}
      <header className="bg-[#030712] text-white">
        <div className="max-w-3xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lightning size={20} weight="fill" className="text-[#FACC15]" />
            <span className="font-black tracking-tight text-base">HCOB Network</span>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#9CA3AF]">
            Private chat
          </span>
        </div>
      </header>

      {/* Thread context strip */}
      <div className="bg-white border-b border-[#E5E7EB]">
        <div className="max-w-3xl mx-auto px-5 py-4">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
            {thread.scope_type === "project" ? "Project" : "Assignment"}
          </div>
          <div
            className="text-lg font-bold text-[#030712] mt-0.5"
            data-testid="customer-chat-gig-title"
          >
            {thread.title || thread.project_title || thread.gig_title || "HCOB Assignment"}
          </div>
          {contractors.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#6B7280]">
                Crew
              </span>
              {contractors.map((c) => (
                <span
                  key={c.user_id}
                  className="px-2 py-1 bg-[#F3F4F6] border border-[#E5E7EB] text-xs font-medium text-[#030712]"
                  data-testid={`customer-chat-contractor-${c.user_id}`}
                >
                  {c.first_name}
                </span>
              ))}
            </div>
          )}
          {closed && (
            <div
              className="mt-3 px-3 py-2 bg-[#FFFBEB] border-l-2 border-[#F59E0B] text-xs text-[#92400E]"
              data-testid="customer-chat-closed-banner"
            >
              <strong>This chat has ended.</strong>{" "}
              {thread.closed_reason || "The assignment is complete."}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <main
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        data-testid="customer-chat-messages"
      >
        <div className="max-w-3xl mx-auto px-5 py-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <ChatCircle size={40} className="mx-auto text-[#9CA3AF] mb-3" />
              <p className="text-sm text-[#6B7280]">
                No messages yet. Send the first message below — your crew will be notified.
              </p>
            </div>
          ) : (
            messages.map((m) => {
              const mine = m.sender_type === "customer";
              return (
                <div
                  key={m.message_id}
                  className={`flex ${mine ? "justify-end" : "justify-start"}`}
                  data-testid={`customer-chat-msg-${m.message_id}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 ${
                      mine
                        ? "bg-[#0044FF] text-white"
                        : "bg-white border border-[#E5E7EB] text-[#030712]"
                    }`}
                  >
                    {!mine && (
                      <div
                        className={`text-[10px] font-mono uppercase tracking-widest mb-1 ${
                          m.sender_type === "admin"
                            ? "text-[#7C3AED]"
                            : "text-[#0044FF]"
                        }`}
                      >
                        {m.sender_type === "admin" ? "HCOB Team" : m.sender_first_name}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                      {m.text}
                    </div>
                    <div
                      className={`text-[10px] mt-1.5 ${
                        mine ? "text-white/70" : "text-[#9CA3AF]"
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
        <div className="max-w-3xl mx-auto px-5 py-3 flex items-end gap-2">
          <textarea
            data-testid="customer-chat-composer"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={closed ? "This chat has ended." : "Type a message…"}
            rows={1}
            disabled={closed}
            className="flex-1 resize-none border border-[#E5E7EB] px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#0044FF] focus:border-transparent disabled:bg-[#F3F4F6] min-h-[42px] max-h-32"
          />
          <button
            data-testid="customer-chat-send"
            onClick={send}
            disabled={closed || sending || !draft.trim()}
            className="bg-[#030712] text-white px-4 py-2.5 font-medium text-sm hover:bg-[#0044FF] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2 h-[42px]"
          >
            <PaperPlaneTilt size={16} weight="fill" />
            <span className="hidden sm:inline">{sending ? "Sending…" : "Send"}</span>
          </button>
        </div>
        <div className="max-w-3xl mx-auto px-5 pb-3">
          <p className="text-[10px] text-[#9CA3AF]">
            Powered by <strong className="text-[#030712]">HCOB Network</strong>.
            Messages are visible to your assigned crew + the HCOB team.
          </p>
        </div>
      </footer>
    </div>
  );
}
