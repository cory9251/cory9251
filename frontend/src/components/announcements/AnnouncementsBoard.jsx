import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Megaphone, CaretDown, CaretUp, Check } from "@phosphor-icons/react";

export const AnnouncementsBoard = () => {
  const [items, setItems] = useState([]);
  const [expanded, setExpanded] = useState(null);

  const load = () => {
    api.get("/announcements").then((r) => setItems(r.data.items || [])).catch(() => {});
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const markRead = async (a) => {
    try {
      await api.post(`/announcements/${a.announcement_id}/dismiss`);
      setItems((prev) => prev.map((x) => (x.announcement_id === a.announcement_id ? { ...x, dismissed: true } : x)));
    } catch {
      /* non-blocking */
    }
  };

  if (items.length === 0) return null;
  const unread = items.filter((a) => !a.dismissed).length;

  return (
    <section data-testid="announcements-board" className="mt-4 rounded-xl border border-[#030712] bg-white">
      <div className="flex items-center gap-2 border-b border-[#E5E7EB] px-4 py-3">
        <Megaphone size={16} weight="fill" className="text-[#0044FF]" />
        <span className="text-sm font-black">Announcements</span>
        {unread > 0 && (
          <span data-testid="announcements-unread-badge" className="ml-1 rounded-full bg-[#0044FF] px-2 py-0.5 text-[10px] font-bold text-white">
            {unread} new
          </span>
        )}
      </div>
      <div className="divide-y divide-[#F3F4F6]">
        {items.map((a) => {
          const open = expanded === a.announcement_id;
          return (
            <div key={a.announcement_id} data-testid={`announcement-item-${a.announcement_id}`} className="px-4 py-3">
              <button
                type="button"
                onClick={() => setExpanded(open ? null : a.announcement_id)}
                className="flex w-full items-start justify-between gap-3 text-left"
                data-testid={`announcement-toggle-${a.announcement_id}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`truncate text-sm ${a.dismissed ? "font-semibold text-[#4B5563]" : "font-black text-[#030712]"}`}>
                      {a.title}
                    </span>
                    {!a.dismissed && <span className="h-2 w-2 shrink-0 rounded-full bg-[#0044FF]" />}
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#9CA3AF]">
                    {new Date(a.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                    {a.created_by_name ? ` · ${a.created_by_name}` : ""}
                  </div>
                </div>
                {open ? <CaretUp size={14} className="mt-1 shrink-0" /> : <CaretDown size={14} className="mt-1 shrink-0" />}
              </button>
              {open && (
                <div className="mt-2">
                  <p className="whitespace-pre-line text-sm leading-relaxed text-[#374151]">{a.body}</p>
                  {!a.dismissed && (
                    <button
                      data-testid={`announcement-mark-read-${a.announcement_id}`}
                      onClick={() => markRead(a)}
                      className="mt-3 inline-flex items-center gap-1 border border-[#030712] px-3 py-1.5 text-xs font-bold hover:bg-[#030712] hover:text-white"
                    >
                      <Check size={12} /> Mark as read
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
