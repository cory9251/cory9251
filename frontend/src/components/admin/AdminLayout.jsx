import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  House,
  CalendarBlank,
  Briefcase,
  UsersThree,
  Gear,
  SignOut,
  Lightning,
  ClockCounterClockwise,
  ChartBar,
  FolderSimplePlus,
  EnvelopeOpen,
  List,
  X,
  Handshake,
  CurrencyDollar,
  Buildings,
  Kanban,
  Receipt,
  ChatCircleDots,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { useUnreadMessages } from "@/lib/useUnreadMessages";

const nav = [
  { to: "/ops", label: "Dashboard", icon: House, end: true },
  { to: "/ops/calendar", label: "Calendar", icon: CalendarBlank, end: false },
  { to: "/ops/requests", label: "Requests", icon: ClockCounterClockwise, end: false, badge: "pending" },
  { to: "/ops/quotes", label: "Quotes", icon: EnvelopeOpen, end: false, badge: "quotes" },
  { to: "/ops/gigs", label: "Gigs", icon: Briefcase, end: false },
  { to: "/ops/projects", label: "Projects", icon: FolderSimplePlus, end: false },
  { to: "/ops/workers", label: "Workers", icon: UsersThree, end: false },
  { to: "/ops/messages", label: "Messages", icon: ChatCircleDots, end: false, badge: "messages" },
  { to: "/ops/reports", label: "Reports", icon: ChartBar, end: false },
  { to: "/ops/settings", label: "Settings", icon: Gear, end: false },
];

const vaNav = [
  { to: "/ops/va-program", label: "VA Overview", icon: Handshake, end: true },
  { to: "/ops/va-program/pipeline", label: "Lead Pipeline", icon: Kanban, end: false },
  { to: "/ops/va-program/commissions", label: "Commissions", icon: CurrencyDollar, end: false, badge: "va_queue" },
  { to: "/ops/va-program/vas", label: "VA Accounts", icon: UsersThree, end: false },
  { to: "/ops/va-program/commercial", label: "Commercial", icon: Buildings, end: false },
];

const ownerNav = [
  { to: "/ops/payouts", label: "Payouts (Owner)", icon: Receipt, end: false, badge: "payouts" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(null);
  const [quotesCount, setQuotesCount] = useState(null);
  const [vaQueueCount, setVaQueueCount] = useState(0);
  const [payoutsCount, setPayoutsCount] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { count: messagesUnread } = useUnreadMessages();

  const refreshPending = async () => {
    try {
      const { data } = await api.get("/admin/stats");
      setPendingCount(data?.pending_requests ?? 0);
    } catch {
      // silent
    }
  };

  const refreshQuotes = async () => {
    try {
      const { data } = await api.get("/admin/quote-requests?status=new&limit=1");
      setQuotesCount(data?.counts?.new ?? 0);
    } catch {
      // silent
    }
  };

  const refreshVAQueue = async () => {
    try {
      const { data } = await api.get("/pm/commissions");
      setVaQueueCount(data?.items?.length ?? 0);
    } catch {
      setVaQueueCount(0);
    }
  };

  const refreshPayouts = async () => {
    if (!user?.is_owner) return;
    try {
      const { data } = await api.get("/owner/payouts/queue");
      setPayoutsCount(data?.items?.length ?? 0);
    } catch {
      setPayoutsCount(0);
    }
  };

  useEffect(() => {
    /* eslint-disable */
    refreshPending();
    refreshQuotes();
    refreshVAQueue();
    refreshPayouts();
    /* eslint-enable */
    const onChange = () => {
      refreshPending();
      refreshQuotes();
      refreshVAQueue();
      refreshPayouts();
    };
    window.addEventListener("hcob:requests-changed", onChange);
    window.addEventListener("hcob:va-changed", onChange);
    return () => {
      window.removeEventListener("hcob:requests-changed", onChange);
      window.removeEventListener("hcob:va-changed", onChange);
    };
  }, [location.pathname, user?.is_owner]);

  // Close the mobile drawer whenever the route changes
  useEffect(() => {
    setMobileOpen(false); // eslint-disable-line
  }, [location.pathname]);

  // ESC closes drawer + body scroll-lock while drawer is open
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [mobileOpen]);

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  // Friendly section name for the mobile header — derived from the active nav.
  const allNav = [...nav, ...vaNav, ...ownerNav];
  const activeItem = [...allNav]
    .sort((a, b) => b.to.length - a.to.length)
    .find((n) =>
      n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)
    );
  const currentLabel = activeItem ? activeItem.label : "HCOB Network";
  return (
    <div className="flex min-h-screen flex-col bg-white md:flex-row" data-testid="admin-layout">
      <aside className="hidden md:flex w-64 flex-col border-r border-[#E5E7EB] bg-white">
        <div className="flex items-center gap-2 border-b border-[#E5E7EB] px-6 py-5">
          <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
            <Lightning weight="fill" size={18} />
          </div>
          <div>
            <div className="font-display text-lg font-black leading-none">HCOB Network</div>
            <div className="font-mono-label text-[10px]">Operations Console</div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-6">
          <div className="font-mono-label mb-3 px-3">Manage</div>
          <div className="space-y-1">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                data-testid={`nav-${n.label.toLowerCase()}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm transition-colors ${
                    isActive
                      ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                      : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                  }`
                }
              >
                <n.icon size={18} weight="duotone" />
                <span className="flex-1">{n.label}</span>
                {n.badge === "pending" && pendingCount > 0 && (
                  <span
                    data-testid="nav-requests-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {pendingCount > 99 ? "99+" : pendingCount}
                  </span>
                )}
                {n.badge === "quotes" && quotesCount > 0 && (
                  <span
                    data-testid="nav-quotes-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#0044FF] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {quotesCount > 99 ? "99+" : quotesCount}
                  </span>
                )}
                {n.badge === "messages" && messagesUnread > 0 && (
                  <span
                    data-testid="nav-messages-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {messagesUnread > 99 ? "99+" : messagesUnread}
                  </span>
                )}
              </NavLink>
            ))}
          </div>

          {/* VA Commission Program — Mechie + any admin */}
          <div className="font-mono-label mb-3 mt-6 px-3">VA Commission</div>
          <div className="space-y-1">
            {vaNav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                data-testid={`nav-${n.label.toLowerCase().replace(/ /g, "-")}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm transition-colors ${
                    isActive
                      ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                      : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                  }`
                }
              >
                <n.icon size={18} weight="duotone" />
                <span className="flex-1">{n.label}</span>
                {n.badge === "va_queue" && vaQueueCount > 0 && (
                  <span
                    data-testid="nav-va-queue-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {vaQueueCount > 99 ? "99+" : vaQueueCount}
                  </span>
                )}
              </NavLink>
            ))}
          </div>

          {/* Owner-only — final payout sign-off */}
          {user?.is_owner && (
            <>
              <div className="font-mono-label mb-3 mt-6 px-3">Owner</div>
              <div className="space-y-1">
                {ownerNav.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.end}
                    data-testid={`nav-${n.label.toLowerCase().replace(/[ ()]/g, "-")}`}
                    className={({ isActive }) =>
                      `flex items-center gap-3 border-l-2 px-3 py-2.5 text-sm transition-colors ${
                        isActive
                          ? "border-violet-600 bg-violet-50 font-semibold text-[#030712]"
                          : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                      }`
                    }
                  >
                    <n.icon size={18} weight="duotone" />
                    <span className="flex-1">{n.label}</span>
                    {n.badge === "payouts" && payoutsCount > 0 && (
                      <span
                        data-testid="nav-payouts-count"
                        className="inline-flex h-5 min-w-[20px] items-center justify-center bg-violet-600 px-1.5 text-[10px] font-bold tracking-widest text-white"
                      >
                        {payoutsCount > 99 ? "99+" : payoutsCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            </>
          )}
        </nav>
        <div className="border-t border-[#E5E7EB] p-4">
          <div className="text-xs text-[#4B5563]">Signed in as</div>
          <div className="truncate text-sm font-semibold">{user?.email}</div>
          <button
            data-testid="admin-logout-btn"
            onClick={onLogout}
            className="mt-3 flex w-full items-center justify-center gap-2 border border-[#E5E7EB] py-2 text-xs hover:bg-[#F9FAFB]"
          >
            <SignOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden flex w-full flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[#E5E7EB] bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              data-testid="admin-mobile-menu-btn"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              className="-ml-2 grid h-10 w-10 place-items-center rounded-md text-[#030712] hover:bg-[#F3F4F6]"
            >
              <List size={22} weight="bold" />
              {(pendingCount > 0 || quotesCount > 0 || messagesUnread > 0) && (
                <span
                  data-testid="admin-mobile-menu-badge"
                  className="absolute mt-[-22px] ml-[18px] inline-flex h-4 min-w-[16px] items-center justify-center bg-[#F59E0B] px-1 text-[9px] font-bold tracking-widest text-white"
                >
                  {(() => {
                    const c = (pendingCount || 0) + (quotesCount || 0) + (messagesUnread || 0);
                    return c > 99 ? "99+" : c;
                  })()}
                </span>
              )}
            </button>
            <div className="flex items-center gap-2">
              <div className="grid h-7 w-7 place-items-center bg-[#030712] text-white">
                <Lightning weight="fill" size={14} />
              </div>
              <div className="font-display text-base font-black leading-none">
                {currentLabel}
              </div>
            </div>
          </div>
          <button
            data-testid="admin-mobile-logout"
            onClick={onLogout}
            aria-label="Sign out"
            className="grid h-9 w-9 place-items-center border border-[#E5E7EB] text-[#030712] hover:bg-[#030712] hover:text-white"
          >
            <SignOut size={14} />
          </button>
        </header>

        {/* Slide-out drawer + backdrop */}
        <div
          aria-hidden={!mobileOpen}
          className={`fixed inset-0 z-40 md:hidden ${
            mobileOpen ? "pointer-events-auto" : "pointer-events-none"
          }`}
        >
          {/* Backdrop */}
          <div
            data-testid="admin-mobile-backdrop"
            onClick={() => setMobileOpen(false)}
            className={`absolute inset-0 bg-[#030712] transition-opacity duration-200 ${
              mobileOpen ? "opacity-60" : "opacity-0"
            }`}
          />
          {/* Drawer */}
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Operations menu"
            data-testid="admin-mobile-drawer"
            className={`absolute inset-y-0 left-0 flex w-[85%] max-w-[320px] transform flex-col bg-white shadow-2xl transition-transform duration-200 ease-out ${
              mobileOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
                  <Lightning weight="fill" size={16} />
                </div>
                <div>
                  <div className="font-display text-base font-black leading-none">
                    HCOB Network
                  </div>
                  <div className="font-mono-label text-[10px]">
                    Operations Console
                  </div>
                </div>
              </div>
              <button
                data-testid="admin-mobile-close"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="grid h-9 w-9 place-items-center text-[#030712] hover:bg-[#F3F4F6]"
              >
                <X size={18} weight="bold" />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto px-3 py-5">
              <div className="font-mono-label mb-3 px-3">Manage</div>
              <div className="space-y-1">
                {nav.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.end}
                    onClick={() => setMobileOpen(false)}
                    data-testid={`mobile-nav-${n.label.toLowerCase()}`}
                    className={({ isActive }) =>
                      `flex items-center gap-3 border-l-2 px-3 py-3 text-sm transition-colors ${
                        isActive
                          ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                          : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                      }`
                    }
                  >
                    <n.icon size={20} weight="duotone" />
                    <span className="flex-1">{n.label}</span>
                    {n.badge === "pending" && pendingCount > 0 && (
                      <span
                        data-testid="mobile-nav-requests-count"
                        className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                      >
                        {pendingCount > 99 ? "99+" : pendingCount}
                      </span>
                    )}
                    {n.badge === "quotes" && quotesCount > 0 && (
                      <span
                        data-testid="mobile-nav-quotes-count"
                        className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#0044FF] px-1.5 text-[10px] font-bold tracking-widest text-white"
                      >
                        {quotesCount > 99 ? "99+" : quotesCount}
                      </span>
                    )}
                    {n.badge === "messages" && messagesUnread > 0 && (
                      <span
                        data-testid="mobile-nav-messages-count"
                        className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                      >
                        {messagesUnread > 99 ? "99+" : messagesUnread}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>

              <div className="font-mono-label mb-3 mt-6 px-3">VA Commission</div>
              <div className="space-y-1">
                {vaNav.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.end}
                    onClick={() => setMobileOpen(false)}
                    data-testid={`mobile-nav-${n.label.toLowerCase().replace(/ /g, "-")}`}
                    className={({ isActive }) =>
                      `flex items-center gap-3 border-l-2 px-3 py-3 text-sm transition-colors ${
                        isActive
                          ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                          : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                      }`
                    }
                  >
                    <n.icon size={20} weight="duotone" />
                    <span className="flex-1">{n.label}</span>
                    {n.badge === "va_queue" && vaQueueCount > 0 && (
                      <span className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white">
                        {vaQueueCount > 99 ? "99+" : vaQueueCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>

              {user?.is_owner && (
                <>
                  <div className="font-mono-label mb-3 mt-6 px-3">Owner</div>
                  <div className="space-y-1">
                    {ownerNav.map((n) => (
                      <NavLink
                        key={n.to}
                        to={n.to}
                        end={n.end}
                        onClick={() => setMobileOpen(false)}
                        data-testid={`mobile-nav-${n.label.toLowerCase().replace(/[ ()]/g, "-")}`}
                        className={({ isActive }) =>
                          `flex items-center gap-3 border-l-2 px-3 py-3 text-sm transition-colors ${
                            isActive
                              ? "border-violet-600 bg-violet-50 font-semibold text-[#030712]"
                              : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                          }`
                        }
                      >
                        <n.icon size={20} weight="duotone" />
                        <span className="flex-1">{n.label}</span>
                        {n.badge === "payouts" && payoutsCount > 0 && (
                          <span className="inline-flex h-5 min-w-[20px] items-center justify-center bg-violet-600 px-1.5 text-[10px] font-bold tracking-widest text-white">
                            {payoutsCount > 99 ? "99+" : payoutsCount}
                          </span>
                        )}
                      </NavLink>
                    ))}
                  </div>
                </>
              )}
            </nav>
            <div className="border-t border-[#E5E7EB] p-4">
              <div className="text-xs text-[#4B5563]">Signed in as</div>
              <div className="truncate text-sm font-semibold">{user?.email}</div>
              <button
                data-testid="admin-mobile-drawer-logout"
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
        <Outlet />
      </main>
    </div>
  );
}
