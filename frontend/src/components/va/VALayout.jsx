import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Gauge,
  PlusCircle,
  Kanban,
  CurrencyDollar,
  SignOut,
  Lightning,
  List,
  X,
  WarningCircle,
  ChatCircleDots,
  Trophy,
  Lightbulb,
  BookOpenText,
  Monitor,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { useUnreadMessages } from "@/lib/useUnreadMessages";

const tabs = [
  { to: "/va", label: "Dashboard", icon: Gauge, end: true, requiresApproved: false },
  { to: "/va/submit", label: "Submit Lead", icon: PlusCircle, end: false, requiresApproved: true },
  { to: "/va/leads", label: "My Leads", icon: Kanban, end: false, requiresApproved: true },
  { to: "/va/digital", label: "Digital Services", icon: Monitor, end: false, requiresApproved: true },
  { to: "/va/earnings", label: "Earnings", icon: CurrencyDollar, end: false, requiresApproved: true },
  { to: "/va/leaderboard", label: "Leaderboard", icon: Trophy, end: false, requiresApproved: false },
  { to: "/va/templates", label: "Templates", icon: Lightbulb, end: false, requiresApproved: false },
  { to: "/va/training", label: "Training", icon: BookOpenText, end: false, requiresApproved: false },
  { to: "/va/messages", label: "Messages", icon: ChatCircleDots, end: false, badge: "messages", requiresApproved: true },
];

export default function VALayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { count: messagesUnread } = useUnreadMessages();

  useEffect(() => {
    setMobileOpen(false); // eslint-disable-line
  }, [location.pathname]);

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const pending = user?.va_status === "pending";
  const suspended = user?.va_status === "suspended";
  const approved = user?.va_status === "approved";
  // While pending/suspended, only show tabs that don't require approval.
  const visibleTabs = approved ? tabs : tabs.filter((t) => !t.requiresApproved);

  return (
    <div className="flex min-h-screen flex-col bg-[#F8F7F4] md:flex-row" data-testid="va-layout">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-64 flex-col border-r border-[#E5E7EB] bg-white">
        <div className="flex items-center gap-2 border-b border-[#E5E7EB] px-6 py-5">
          <div className="grid h-8 w-8 place-items-center bg-[#0044FF] text-white">
            <Lightning weight="fill" size={18} />
          </div>
          <div>
            <div className="font-display text-lg font-black leading-none">HCOB · VA</div>
            <div className="font-mono-label text-[10px]">Commission Program</div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-6">
          <div className="font-mono-label mb-3 px-3">Menu</div>
          <div className="space-y-1">
            {visibleTabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                data-testid={`va-nav-${t.label.toLowerCase().replace(/ /g, "-")}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm transition-colors ${
                    isActive
                      ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                      : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                  }`
                }
              >
                <t.icon size={18} weight="duotone" />
                <span className="flex-1">{t.label}</span>
                {t.badge === "messages" && messagesUnread > 0 && (
                  <span
                    data-testid="va-nav-messages-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {messagesUnread > 99 ? "99+" : messagesUnread}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </nav>
        <div className="border-t border-[#E5E7EB] p-4">
          <div className="text-xs text-[#4B5563]">Signed in as</div>
          <div className="truncate text-sm font-semibold">{user?.name}</div>
          <div className="truncate text-[10px] text-[#4B5563]">{user?.email}</div>
          <button
            data-testid="va-logout-btn"
            onClick={onLogout}
            className="mt-3 flex w-full items-center justify-center gap-2 border border-[#E5E7EB] py-2 text-xs hover:bg-[#F9FAFB]"
          >
            <SignOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="md:hidden flex w-full flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[#E5E7EB] bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              data-testid="va-mobile-menu-btn"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              className="-ml-2 grid h-10 w-10 place-items-center rounded-md text-[#030712] hover:bg-[#F3F4F6]"
            >
              <List size={22} weight="bold" />
            </button>
            <div className="flex items-center gap-2">
              <div className="grid h-7 w-7 place-items-center bg-[#0044FF] text-white">
                <Lightning weight="fill" size={14} />
              </div>
              <div className="font-display text-base font-black leading-none">HCOB · VA</div>
            </div>
          </div>
          <button
            data-testid="va-mobile-logout"
            onClick={onLogout}
            aria-label="Sign out"
            className="grid h-9 w-9 place-items-center border border-[#E5E7EB] text-[#030712] hover:bg-[#030712] hover:text-white"
          >
            <SignOut size={14} />
          </button>
        </header>

        <div
          className={`fixed inset-0 z-40 md:hidden ${
            mobileOpen ? "pointer-events-auto" : "pointer-events-none"
          }`}
        >
          <div
            data-testid="va-mobile-backdrop"
            onClick={() => setMobileOpen(false)}
            className={`absolute inset-0 bg-[#030712] transition-opacity duration-200 ${
              mobileOpen ? "opacity-60" : "opacity-0"
            }`}
          />
          <aside
            role="dialog"
            data-testid="va-mobile-drawer"
            className={`absolute inset-y-0 left-0 flex w-[85%] max-w-[320px] transform flex-col bg-white shadow-2xl transition-transform duration-200 ease-out ${
              mobileOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center bg-[#0044FF] text-white">
                  <Lightning weight="fill" size={16} />
                </div>
                <div className="font-display text-base font-black leading-none">HCOB · VA</div>
              </div>
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="grid h-9 w-9 place-items-center text-[#030712] hover:bg-[#F3F4F6]"
              >
                <X size={18} weight="bold" />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto px-3 py-5">
              <div className="space-y-1">
                {visibleTabs.map((t) => (
                  <NavLink
                    key={t.to}
                    to={t.to}
                    end={t.end}
                    onClick={() => setMobileOpen(false)}
                    data-testid={`va-mobile-nav-${t.label.toLowerCase().replace(/ /g, "-")}`}
                    className={({ isActive }) =>
                      `flex items-center gap-3 border-l-2 px-3 py-3 text-sm transition-colors ${
                        isActive
                          ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                          : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                      }`
                    }
                  >
                    <t.icon size={20} weight="duotone" />
                    <span className="flex-1">{t.label}</span>
                    {t.badge === "messages" && messagesUnread > 0 && (
                      <span
                        data-testid="va-mobile-nav-messages-count"
                        className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                      >
                        {messagesUnread > 99 ? "99+" : messagesUnread}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </nav>
            <div className="border-t border-[#E5E7EB] p-4">
              <div className="text-xs text-[#4B5563]">Signed in as</div>
              <div className="truncate text-sm font-semibold">{user?.name}</div>
              <button
                onClick={onLogout}
                className="mt-3 flex w-full items-center justify-center gap-2 border border-[#E5E7EB] py-2.5 text-xs hover:bg-[#F9FAFB]"
              >
                <SignOut size={14} /> Sign out
              </button>
            </div>
          </aside>
        </div>
      </div>

      <main className="flex-1 overflow-y-auto">
        {(pending || suspended) && (
          <div
            data-testid="va-status-banner"
            className={`flex items-center gap-3 border-b px-6 py-3 text-sm ${
              pending
                ? "border-amber-200 bg-amber-50 text-amber-900"
                : "border-red-200 bg-red-50 text-red-900"
            }`}
          >
            <WarningCircle size={20} weight="duotone" />
            <div>
              {pending && (
                <>
                  <span className="font-semibold">Pending approval.</span>{" "}
                  While we review your account, you can study the Training playbook, browse Templates, and watch the Leaderboard. Submit Lead, My Leads, Earnings, and Messages unlock once your Program Manager approves you.
                </>
              )}
              {suspended && (
                <>
                  <span className="font-semibold">Account suspended.</span>{" "}
                  Contact the Program Manager for next steps.
                </>
              )}
            </div>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
