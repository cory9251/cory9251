/**
 * Shared notification bell — used in both AdminLayout and WorkerLayout.
 *
 * Polls GET /notifications every 30s. Shows an unread count badge on the
 * bell icon. Clicking opens a popover with the latest 10 notifications;
 * clicking a row marks it read + navigates to the linked context (gig,
 * project, or /crew/messages fallback).
 *
 * Hidden entirely for VAs and other roles that don't have notification data
 * to consume (the API still works but returns []).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";

function shortTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return "now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d`;
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

/**
 * `variant="light"` = dark bell on light header (worker/admin default).
 * `variant="dark"`  = white bell on dark header (unused today; kept for reuse).
 */
export default function NotificationBell({ variant = "light", homePath = "/" }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();

  const load = async () => {
    try {
      const { data } = await api.get("/notifications");
      setItems(Array.isArray(data) ? data : []);
    } catch {
      // silent — bell just shows zero if the API hiccups
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    const onEvent = () => load();
    window.addEventListener("hcob:notifications-changed", onEvent);
    return () => {
      clearInterval(id);
      window.removeEventListener("hcob:notifications-changed", onEvent);
    };
  }, []);

  const unreadCount = useMemo(
    () => items.filter((n) => !n.read).length,
    [items]
  );

  const markRead = async (n) => {
    if (n.read) return;
    // Optimistic — update local state first, then hit API
    setItems((prev) =>
      prev.map((x) => (x.notification_id === n.notification_id ? { ...x, read: true } : x))
    );
    try {
      await api.post(`/notifications/${n.notification_id}/read`);
    } catch {
      // silent — will re-sync on next poll
    }
  };

  const markAllRead = async () => {
    const unread = items.filter((n) => !n.read);
    if (unread.length === 0) return;
    setItems((prev) => prev.map((x) => ({ ...x, read: true })));
    await Promise.allSettled(
      unread.map((n) => api.post(`/notifications/${n.notification_id}/read`))
    );
  };

  const openNotification = (n) => {
    markRead(n);
    setOpen(false);
    // Prefer the notification's explicit target, then infer from linked ids
    if (n.url) {
      nav(n.url);
      return;
    }
    if (n.project_id) {
      nav(`${homePath === "/crew" ? "/crew/projects" : "/ops/projects"}/${n.project_id}`);
      return;
    }
    if (n.gig_id) {
      nav(
        homePath === "/crew"
          ? `/crew/assignments/${n.gig_id}`
          : `/ops/assignments/${n.gig_id}`
      );
      return;
    }
    // Fallback — send them to the messages/home surface
    nav(homePath);
  };

  const iconColor = variant === "dark" ? "text-white" : "text-[#030712]";
  const hoverBg = variant === "dark" ? "hover:bg-white/10" : "hover:bg-[#F3F4F6]";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="notification-bell"
          aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ""}`}
          className={`relative grid h-9 w-9 place-items-center border border-transparent ${iconColor} ${hoverBg}`}
        >
          <Bell size={18} weight={unreadCount > 0 ? "fill" : "duotone"} />
          {unreadCount > 0 && (
            <span
              data-testid="notification-bell-count"
              className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#EF4444] px-1 text-[9px] font-bold text-white"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={8}
        className="w-80 p-0"
        data-testid="notification-bell-popover"
      >
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-4 py-3">
          <div className="font-display text-sm font-black">Notifications</div>
          {unreadCount > 0 && (
            <button
              type="button"
              data-testid="notification-mark-all-read"
              onClick={markAllRead}
              className="text-xs text-[#0044FF] hover:underline"
            >
              Mark all read
            </button>
          )}
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          {items.length === 0 ? (
            <div
              data-testid="notification-empty"
              className="px-4 py-8 text-center text-xs text-[#4B5563]"
            >
              You&apos;re all caught up.
            </div>
          ) : (
            <ul className="divide-y divide-[#F3F4F6]">
              {items.slice(0, 15).map((n) => (
                <li key={n.notification_id}>
                  <button
                    type="button"
                    onClick={() => openNotification(n)}
                    data-testid={`notification-item-${n.notification_id}`}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[#F9FAFB] ${
                      !n.read ? "bg-[#F0F4FF]/40" : ""
                    }`}
                  >
                    <div
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        n.read ? "bg-transparent" : "bg-[#0044FF]"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-[#030712]">
                        {n.title || "Notification"}
                      </div>
                      {n.body && (
                        <div className="mt-0.5 line-clamp-2 text-xs text-[#4B5563]">
                          {n.body}
                        </div>
                      )}
                      <div className="mt-1 text-[10px] font-mono uppercase tracking-widest text-[#9CA3AF]">
                        {shortTime(n.created_at)}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
