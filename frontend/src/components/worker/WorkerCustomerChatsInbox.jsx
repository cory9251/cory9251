/**
 * Worker home/feed "Customer chats" inbox tile.
 *
 * One-card summary of all customer threads the worker can read across
 * every gig + project. Clicks open the relevant context (project page
 * for project threads, assignment page for gig threads). Hidden when
 * there are no chats.
 *
 * Polls every 30s.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ChatCircleDots, CaretRight, UsersThree } from "@phosphor-icons/react";

function _shortTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function WorkerCustomerChatsInbox() {
  const [threads, setThreads] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const nav = useNavigate();

  async function load() {
    try {
      const { data } = await api.get("/crew/customer-threads/mine");
      setThreads(data?.items || []);
    } catch {
      setThreads([]);
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  if (!loaded || threads.length === 0) return null;

  const open = (t) => {
    if (t.scope_type === "project" && t.project_id) {
      nav(`/crew/projects/${t.project_id}`);
    } else if (t.gig_id) {
      nav(`/crew/assignments/${t.gig_id}`);
    }
  };

  const active = threads.filter((t) => t.status !== "closed");

  return (
    <div className="mt-4" data-testid="worker-customer-chats-inbox">
      <div className="border border-[#0044FF]/20 bg-[#F5F8FF] p-4">
        <div className="flex items-center gap-2">
          <ChatCircleDots size={16} weight="duotone" className="text-[#0044FF]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#0044FF]">
            Customer chats
          </span>
          <span className="ml-auto text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
            {active.length}/{threads.length} live
          </span>
        </div>
        <ul className="mt-3 space-y-2">
          {threads.slice(0, 5).map((t) => {
            const title = t.title || t.project_title || t.gig_title || "—";
            const isProject = t.scope_type === "project";
            const closed = t.status === "closed";
            return (
              <li key={t.thread_id}>
                <button
                  type="button"
                  onClick={() => open(t)}
                  data-testid={`worker-inbox-row-${t.thread_id}`}
                  className="w-full flex items-center gap-3 bg-white border border-[#E5E7EB] px-3 py-2 text-left hover:border-[#0044FF]"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-[#030712] text-white">
                    {isProject ? (
                      <UsersThree size={14} weight="duotone" />
                    ) : (
                      <ChatCircleDots size={14} weight="duotone" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-[#030712] truncate">
                        {title}
                      </span>
                      {isProject && (
                        <span className="shrink-0 text-[9px] font-mono uppercase tracking-widest px-1 py-0.5 bg-[#0044FF] text-white">
                          Project
                        </span>
                      )}
                      {closed && (
                        <span className="shrink-0 text-[9px] font-mono uppercase tracking-widest px-1 py-0.5 bg-[#9CA3AF] text-white">
                          Ended
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-[#6B7280] truncate">
                      {t.customer_first_name && (
                        <span className="text-[#030712] font-medium">
                          {t.customer_first_name}:
                        </span>
                      )}{" "}
                      {t.last_message_preview || (
                        <span className="italic">No messages yet</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end shrink-0">
                    {t.last_message_at && (
                      <span className="text-[10px] text-[#9CA3AF]">
                        {_shortTime(t.last_message_at)}
                      </span>
                    )}
                    <CaretRight size={12} className="text-[#9CA3AF]" />
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
        {threads.length > 5 && (
          <div className="mt-2 text-center text-[10px] text-[#6B7280]">
            +{threads.length - 5} more · open an assignment to see all
          </div>
        )}
      </div>
    </div>
  );
}
