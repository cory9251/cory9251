import React, { useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { AnnouncementsPopup } from "@/components/announcements/AnnouncementsPopup";
import {
  House,
  CheckSquare,
  User,
  SignOut,
  Lightning,
  ChatCircleDots,
  Handshake,
  DotsThree,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { useUnreadMessages } from "@/lib/useUnreadMessages";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";

// Primary tabs shown in the bottom bar (4 slots)
const primaryTabs = [
  { to: "/crew", label: "Feed", icon: House, end: true },
  { to: "/crew/my-assignments", label: "My work", icon: CheckSquare, end: false },
  { to: "/crew/messages", label: "Messages", icon: ChatCircleDots, end: false, badge: "messages" },
];

// Items behind the "More" dropdown
const moreItems = [
  { to: "/crew/refer", label: "Refer · earn 10%", icon: Handshake, end: false },
  { to: "/crew/me", label: "Profile", icon: User, end: false },
];

export default function WorkerLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const { count: messagesUnread } = useUnreadMessages();
  const [moreOpen, setMoreOpen] = useState(false);

  const onLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  const isMoreActive = moreItems.some((m) =>
    m.end ? location.pathname === m.to : location.pathname.startsWith(m.to)
  );

  return (
    <div className="min-h-screen bg-[#F9FAFB]" data-testid="worker-layout">
      <div className="mx-auto flex min-h-screen max-w-md flex-col bg-[#F9FAFB] shadow-[0_0_0_1px_#E5E7EB]">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[#E5E7EB] bg-white px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={14} />
            </div>
            <div>
              <div className="font-display text-base font-black leading-none">HCOB Network</div>
              <div className="font-mono-label text-[9px]">{user?.name}</div>
            </div>
          </div>
          <button
            data-testid="worker-logout-btn"
            onClick={onLogout}
            className="grid h-9 w-9 place-items-center border border-[#E5E7EB] text-[#030712] hover:bg-[#030712] hover:text-white"
            aria-label="sign out"
          >
            <SignOut size={16} />
          </button>
        </header>

        <main className="flex-1 overflow-y-auto pb-24">
          <AnnouncementsPopup />
          <Outlet />
        </main>

        <nav
          data-testid="worker-bottom-nav"
          className="sticky bottom-0 z-10 grid grid-cols-4 border-t border-[#E5E7EB] bg-white"
        >
          {primaryTabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              data-testid={`tab-${t.label.toLowerCase().replace(/ /g, "-")}`}
              className={({ isActive }) =>
                `relative flex flex-col items-center justify-center gap-1 py-3 text-[10px] font-semibold uppercase tracking-widest ${
                  isActive ? "text-[#0044FF]" : "text-[#4B5563]"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="relative">
                    <t.icon size={22} weight={isActive ? "fill" : "duotone"} />
                    {t.badge === "messages" && messagesUnread > 0 && (
                      <span
                        data-testid="worker-tab-messages-badge"
                        className="absolute -right-2 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center bg-[#F59E0B] px-1 text-[9px] font-bold tracking-widest text-white"
                      >
                        {messagesUnread > 99 ? "99+" : messagesUnread}
                      </span>
                    )}
                  </div>
                  {t.label}
                </>
              )}
            </NavLink>
          ))}

          {/* "More" popover — collapses Refer + Profile */}
          <Popover open={moreOpen} onOpenChange={setMoreOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                data-testid="tab-more"
                aria-label="More"
                aria-expanded={moreOpen}
                className={`relative flex flex-col items-center justify-center gap-1 py-3 text-[10px] font-semibold uppercase tracking-widest ${
                  isMoreActive || moreOpen ? "text-[#0044FF]" : "text-[#4B5563]"
                }`}
              >
                <DotsThree size={26} weight={isMoreActive || moreOpen ? "bold" : "bold"} />
                More
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="end"
              side="top"
              sideOffset={8}
              className="w-56 p-1"
              data-testid="worker-more-menu"
            >
              {moreItems.map((it) => (
                <NavLink
                  key={it.to}
                  to={it.to}
                  end={it.end}
                  onClick={() => setMoreOpen(false)}
                  data-testid={`more-${it.label.toLowerCase().replace(/[ ·]+/g, "-")}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm ${
                      isActive
                        ? "bg-[#F0F4FF] font-semibold text-[#030712]"
                        : "text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                    }`
                  }
                >
                  <it.icon size={18} weight="duotone" />
                  <span className="flex-1">{it.label}</span>
                </NavLink>
              ))}
            </PopoverContent>
          </Popover>
        </nav>
      </div>
    </div>
  );
}
