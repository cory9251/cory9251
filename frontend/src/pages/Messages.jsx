import React, { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  PaperPlaneTilt,
  ChatCircleDots,
  ArrowLeft,
  Plus,
  Paperclip,
  X,
  Briefcase,
  User as UserIcon,
  ShieldCheck,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import NewMessageDialog from "@/components/messages/NewMessageDialog";

const MESSAGE_POLL_MS = 5000;
const LIST_POLL_MS = 10000;

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  const diff = (now - d) / (1000 * 60 * 60 * 24);
  if (diff < 7) {
    return d.toLocaleDateString([], { weekday: "short" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function avatarUrl(path) {
  if (!path) return null;
  return `${API}/files/${path}`;
}

function ThreadAvatar({ thread, currentUserId }) {
  const isDm = thread.type === "dm";
  const other = thread.other_user;
  if (isDm) {
    if (other?.avatar_path) {
      return (
        <img
          src={avatarUrl(other.avatar_path)}
          alt={other.name}
          className="h-10 w-10 rounded-none object-cover"
        />
      );
    }
    return (
      <div className="grid h-10 w-10 place-items-center bg-[#030712] text-white">
        {other?.role === "admin" ? (
          <ShieldCheck size={18} weight="fill" />
        ) : (
          <UserIcon size={18} weight="fill" />
        )}
      </div>
    );
  }
  return (
    <div className="grid h-10 w-10 place-items-center bg-[#0044FF] text-white">
      <Briefcase size={18} weight="fill" />
    </div>
  );
}

function ThreadTitle({ thread, currentUserId }) {
  if (thread.type === "dm") {
    const other = thread.other_user;
    return other?.name || "Direct message";
  }
  return thread.gig_title || "Gig chat";
}

export default function Messages() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeThreadId = searchParams.get("thread");
  const portalBase =
    user?.role === "admin"
      ? "/ops/messages"
      : user?.role === "va"
      ? "/va/messages"
      : "/crew/messages";

  const [threads, setThreads] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [activeThread, setActiveThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [attachments, setAttachments] = useState([]); // [{path, content_type, preview}]
  const [uploading, setUploading] = useState(false);
  const [newDialogOpen, setNewDialogOpen] = useState(false);

  const listTimerRef = useRef(null);
  const msgTimerRef = useRef(null);
  const fileInputRef = useRef(null);
  const scrollEndRef = useRef(null);

  // --- Threads list (poll) -------------------------------------------------
  const refreshThreads = async () => {
    try {
      const { data } = await api.get("/messages/threads");
      setThreads(data || []);
    } catch (e) {
      // silent
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    refreshThreads();
    listTimerRef.current = setInterval(refreshThreads, LIST_POLL_MS);
    return () => clearInterval(listTimerRef.current);
  }, []);

  // --- Active thread + messages (poll) -------------------------------------
  const loadActive = async (tid, { silent } = {}) => {
    if (!silent) setLoadingMsgs(true);
    try {
      const [tRes, mRes] = await Promise.all([
        api.get(`/messages/threads/${tid}`),
        api.get(`/messages/threads/${tid}/messages?limit=100`),
      ]);
      setActiveThread(tRes.data);
      setMessages(mRes.data || []);
      // mark read in background
      api
        .post(`/messages/threads/${tid}/read`)
        .then(() => {
          window.dispatchEvent(new Event("hcob:messages-changed"));
          refreshThreads();
        })
        .catch(() => {});
    } catch (e) {
      if (!silent) toast.error(getErr(e));
      setActiveThread(null);
      setMessages([]);
    } finally {
      if (!silent) setLoadingMsgs(false);
    }
  };

  useEffect(() => {
    if (msgTimerRef.current) clearInterval(msgTimerRef.current);
    if (!activeThreadId) {
      setActiveThread(null);
      setMessages([]);
      return;
    }
    loadActive(activeThreadId);
    msgTimerRef.current = setInterval(
      () => loadActive(activeThreadId, { silent: true }),
      MESSAGE_POLL_MS
    );
    return () => clearInterval(msgTimerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeThreadId]);

  // scroll to bottom when messages change
  useEffect(() => {
    if (scrollEndRef.current) {
      scrollEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages.length, activeThreadId]);

  const openThread = (tid) => {
    setSearchParams({ thread: tid });
  };
  const closeThread = () => {
    setSearchParams({});
  };

  const uploadAttachment = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/messages/attachments", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAttachments((prev) => [
        ...prev,
        {
          path: data.path,
          content_type: data.content_type,
          preview: URL.createObjectURL(file),
        },
      ]);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setUploading(false);
    }
  };

  const onFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    files.forEach(uploadAttachment);
    e.target.value = ""; // allow re-selecting the same file
  };

  const send = async () => {
    if (!activeThread) return;
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;
    setSending(true);
    try {
      await api.post(`/messages/threads/${activeThread.thread_id}/messages`, {
        text: trimmed,
        attachment_paths: attachments.map((a) => a.path),
      });
      setText("");
      setAttachments([]);
      await loadActive(activeThread.thread_id, { silent: true });
      refreshThreads();
      window.dispatchEvent(new Event("hcob:messages-changed"));
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSending(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // Auto-select first thread on desktop (admin) when none chosen
  // Worker UX prefers explicit selection so we don't auto-open there.

  return (
    <div
      className="flex h-[calc(100vh-65px)] md:h-screen flex-col md:flex-row bg-white"
      data-testid="messages-page"
    >
      {/* LEFT — thread list */}
      <aside
        className={`border-r border-[#E5E7EB] md:w-80 md:flex md:flex-col ${
          activeThreadId ? "hidden md:flex" : "flex flex-col"
        }`}
        data-testid="thread-list"
      >
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-4 py-3">
          <div>
            <div className="font-display text-xl font-black tracking-tight">
              Messages
            </div>
            <div className="font-mono-label text-[10px] text-[#737373]">
              {threads.length} thread{threads.length === 1 ? "" : "s"}
            </div>
          </div>
          <button
            data-testid="new-message-btn"
            onClick={() => setNewDialogOpen(true)}
            className="flex items-center gap-1 bg-[#030712] px-3 py-2 text-xs font-bold uppercase tracking-widest text-white hover:bg-[#0044FF]"
          >
            <Plus size={14} weight="bold" /> New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingList ? (
            <div className="p-6 text-center text-sm text-[#737373]">Loading…</div>
          ) : threads.length === 0 ? (
            <div
              className="p-8 text-center text-sm text-[#737373]"
              data-testid="thread-list-empty"
            >
              <ChatCircleDots
                size={36}
                weight="duotone"
                className="mx-auto mb-2 text-[#9CA3AF]"
              />
              No conversations yet. Start a new one ↑
            </div>
          ) : (
            <ul className="divide-y divide-[#F3F4F6]">
              {threads.map((t) => {
                const isActive = t.thread_id === activeThreadId;
                const isDm = t.type === "dm";
                return (
                  <li key={t.thread_id}>
                    <button
                      type="button"
                      onClick={() => openThread(t.thread_id)}
                      data-testid={`thread-row-${t.thread_id}`}
                      className={`flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-[#FFFBEB] ${
                        isActive ? "bg-[#FFFBEB]" : ""
                      }`}
                    >
                      <ThreadAvatar thread={t} currentUserId={user?.user_id} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <div className="truncate text-sm font-semibold">
                            <ThreadTitle thread={t} currentUserId={user?.user_id} />
                          </div>
                          {!isDm && (
                            <span className="font-mono-label text-[9px] text-[#0044FF]">
                              GROUP
                            </span>
                          )}
                          <div className="ml-auto whitespace-nowrap text-[10px] text-[#737373]">
                            {formatTime(t.last_message_at)}
                          </div>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2">
                          <div className="truncate text-xs text-[#525252]">
                            {t.last_message_text || "Say hello 👋"}
                          </div>
                          {t.unread_count > 0 && (
                            <span
                              data-testid={`thread-unread-${t.thread_id}`}
                              className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                            >
                              {t.unread_count > 99 ? "99+" : t.unread_count}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      {/* RIGHT — active conversation */}
      <section
        className={`flex flex-1 flex-col bg-white ${
          activeThreadId ? "flex" : "hidden md:flex"
        }`}
        data-testid="message-pane"
      >
        {!activeThread ? (
          <div className="grid flex-1 place-items-center p-10 text-center">
            <div>
              <ChatCircleDots
                size={56}
                weight="duotone"
                className="mx-auto mb-3 text-[#9CA3AF]"
              />
              <div className="font-display text-lg font-black">
                Pick a conversation
              </div>
              <div className="mt-1 text-sm text-[#737373]">
                Or start a new one →
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 border-b border-[#E5E7EB] px-4 py-3">
              <button
                type="button"
                data-testid="thread-back-btn"
                onClick={closeThread}
                className="md:hidden grid h-9 w-9 place-items-center hover:bg-[#F3F4F6]"
                aria-label="Back to threads"
              >
                <ArrowLeft size={18} weight="bold" />
              </button>
              <ThreadAvatar thread={activeThread} currentUserId={user?.user_id} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-display text-base font-black">
                  {user?.role === "admin" &&
                  activeThread.type === "dm" &&
                  activeThread.other_user?.role === "worker" ? (
                    <a
                      href={`/ops/workers/${activeThread.other_user.user_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid={`worker-link-${activeThread.other_user.user_id}`}
                      className="underline decoration-dotted underline-offset-4 hover:text-[#0044FF]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ThreadTitle thread={activeThread} currentUserId={user?.user_id} />
                    </a>
                  ) : (
                    <ThreadTitle thread={activeThread} currentUserId={user?.user_id} />
                  )}
                </div>
                <div className="truncate text-[11px] text-[#737373]">
                  {activeThread.type === "gig_group" ? (
                    <>
                      Group chat ·{" "}
                      {activeThread.participants?.length || 0} participants
                      {activeThread.gig_id && (
                        <>
                          {" · "}
                          <button
                            type="button"
                            onClick={() => {
                              const base =
                                user?.role === "admin"
                                  ? `/ops/gigs/${activeThread.gig_id}`
                                  : `/crew/gigs/${activeThread.gig_id}`;
                              navigate(base);
                            }}
                            className="underline hover:text-[#0044FF]"
                            data-testid="thread-open-gig"
                          >
                            Open gig →
                          </button>
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      Direct message ·{" "}
                      <span className="uppercase tracking-widest">
                        {activeThread.other_user?.role || "user"}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div
              className="flex-1 overflow-y-auto bg-[#F9FAFB] px-4 py-4"
              data-testid="messages-scroll"
            >
              {loadingMsgs ? (
                <div className="text-center text-sm text-[#737373]">Loading…</div>
              ) : messages.length === 0 ? (
                <div className="mt-10 text-center text-sm text-[#737373]">
                  This conversation is empty. Send the first message ↓
                </div>
              ) : (
                <ul className="space-y-3">
                  {messages.map((m) => {
                    const mine = m.sender_id === user?.user_id;
                    return (
                      <li
                        key={m.message_id}
                        className={`flex ${mine ? "justify-end" : "justify-start"}`}
                        data-testid={`message-${m.message_id}`}
                      >
                        <div
                          className={`max-w-[80%] border ${
                            mine
                              ? "border-[#030712] bg-[#030712] text-white"
                              : "border-[#E5E7EB] bg-white text-[#030712]"
                          } px-3 py-2`}
                        >
                          {!mine && (
                            <div className="mb-0.5 text-[10px] font-bold uppercase tracking-widest opacity-70">
                              {user?.role === "admin" && m.sender_role === "worker" ? (
                                <a
                                  href={`/ops/workers/${m.sender_id}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  data-testid={`worker-link-${m.sender_id}`}
                                  className="underline decoration-dotted underline-offset-4 hover:opacity-100"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {m.sender_name}
                                </a>
                              ) : (
                                m.sender_name
                              )}
                              {m.sender_role === "admin" && " · admin"}
                            </div>
                          )}
                          {m.attachments?.length > 0 && (
                            <div className="mb-1 flex flex-wrap gap-2">
                              {m.attachments.map((a, idx) => (
                                <a
                                  key={idx}
                                  href={avatarUrl(a.path)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  data-testid={`message-attachment-${m.message_id}-${idx}`}
                                >
                                  <img
                                    src={avatarUrl(a.path)}
                                    alt="attachment"
                                    className="max-h-40 max-w-[200px] object-cover border border-[#0006]"
                                  />
                                </a>
                              ))}
                            </div>
                          )}
                          {m.text && (
                            <div className="whitespace-pre-wrap break-words text-sm">
                              {m.text}
                            </div>
                          )}
                          <div className="mt-1 text-[10px] opacity-60">
                            {formatTime(m.created_at)}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              <div ref={scrollEndRef} />
            </div>

            {/* Composer */}
            <div className="border-t border-[#E5E7EB] bg-white p-3" data-testid="composer">
              {attachments.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                  {attachments.map((a, idx) => (
                    <div
                      key={a.path}
                      className="relative"
                      data-testid={`pending-attachment-${idx}`}
                    >
                      <img
                        src={a.preview}
                        alt="pending"
                        className="h-16 w-16 object-cover border border-[#E5E7EB]"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setAttachments((prev) =>
                            prev.filter((_, i) => i !== idx)
                          )
                        }
                        className="absolute -right-2 -top-2 grid h-5 w-5 place-items-center rounded-full bg-[#030712] text-white"
                        aria-label="Remove attachment"
                        data-testid={`remove-attachment-${idx}`}
                      >
                        <X size={10} weight="bold" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-end gap-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  data-testid="attach-btn"
                  className="grid h-10 w-10 place-items-center border border-[#E5E7EB] hover:bg-[#F3F4F6] disabled:opacity-50"
                  aria-label="Attach image"
                >
                  <Paperclip size={16} />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={onFileChange}
                  className="hidden"
                  data-testid="file-input"
                />
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={onKeyDown}
                  rows={1}
                  placeholder="Write a message…"
                  className="flex-1 resize-none border border-[#E5E7EB] px-3 py-2 text-sm focus:border-[#030712] focus:outline-none"
                  data-testid="message-input"
                  style={{ maxHeight: "120px" }}
                />
                <button
                  type="button"
                  onClick={send}
                  disabled={
                    sending ||
                    uploading ||
                    (!text.trim() && attachments.length === 0)
                  }
                  data-testid="send-message-btn"
                  className="grid h-10 w-10 place-items-center bg-[#030712] text-white hover:bg-[#0044FF] disabled:opacity-30"
                  aria-label="Send message"
                >
                  <PaperPlaneTilt size={16} weight="fill" />
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <NewMessageDialog
        open={newDialogOpen}
        onOpenChange={setNewDialogOpen}
        onOpened={(t) => {
          refreshThreads();
          openThread(t.thread_id);
        }}
      />
    </div>
  );
}
