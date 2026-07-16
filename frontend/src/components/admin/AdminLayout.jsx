import React, { useEffect, useMemo, useState } from "react";
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
  PaperPlaneTilt,
  List,
  X,
  Handshake,
  CurrencyDollar,
  Buildings,
  Kanban,
  Receipt,
  HandCoins,
  ChatCircleDots,
  Monitor,
  Calculator,
  Megaphone,
  Percent,
  Sparkle,
  Tag,
  SealCheck,
  Wrench,
  CaretDown,
  Coins,
  UserPlus,
  ShieldCheck,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { useUnreadMessages } from "@/lib/useUnreadMessages";
import NotificationBell from "@/components/NotificationBell";

// Flat items at the top (no dropdown wrapper)
const homeItems = [
  { to: "/ops", label: "Dashboard", icon: House, end: true },
  { to: "/ops/calendar", label: "Calendar", icon: CalendarBlank, end: false },
];

// Grouped items — each group is a collapsible dropdown
const groups = [
  {
    key: "work",
    label: "Work Pipeline",
    icon: Briefcase,
    items: [
      { to: "/ops/requests", label: "Requests", icon: ClockCounterClockwise, end: false, badge: "pending" },
      { to: "/ops/quotes", label: "Quotes", icon: EnvelopeOpen, end: false, badge: "quotes" },
      { to: "/ops/assignments", label: "Assignments", icon: Briefcase, end: false },
      { to: "/ops/ai-assignment", label: "AI Assignment", icon: Sparkle, end: false },
      { to: "/ops/projects", label: "Projects", icon: FolderSimplePlus, end: false },
    ],
  },
  {
    key: "people",
    label: "People",
    icon: UsersThree,
    items: [
      { to: "/ops/workers", label: "Workers", icon: UsersThree, end: false },
      { to: "/ops/badges", label: "Certifications", icon: SealCheck, end: false },
      { to: "/ops/trades", label: "Trades", icon: Wrench, end: false },
      { to: "/ops/referrals", label: "Referrals", icon: Handshake, end: false },
      { to: "/ops/messages", label: "Messages", icon: ChatCircleDots, end: false, badge: "messages" },
    ],
  },
  {
    key: "growth",
    label: "Growth",
    icon: Megaphone,
    items: [
      { to: "/ops/email-blast", label: "Blast", icon: PaperPlaneTilt, end: false },
      { to: "/ops/sms-consent", label: "SMS Consent", icon: ShieldCheck, end: false },
      { to: "/ops/services", label: "Service Catalog", icon: Tag, end: false },
      { to: "/ops/announcements", label: "Announcements", icon: Megaphone, end: false },
      { to: "/ops/reports", label: "Reports", icon: ChartBar, end: false },
    ],
  },
  {
    key: "finance",
    label: "Finance",
    icon: Coins,
    items: [
      { to: "/ops/bookkeeping", label: "Bookkeeping", icon: Calculator, end: false },
      { to: "/ops/worker-pay", label: "Worker Pay", icon: HandCoins, end: false },
      // { to: "/ops/payouts", ... } appended conditionally for owners
    ],
  },
];

const settingsItem = { to: "/ops/settings", label: "Settings", icon: Gear, end: false };

const vaNav = [
  { to: "/ops/va-program", label: "VA Overview", icon: Handshake, end: true },
  { to: "/ops/va-program/applications", label: "Applications", icon: UserPlus, end: false },
  { to: "/ops/va-program/pipeline", label: "Lead Pipeline", icon: Kanban, end: false },
  { to: "/ops/va-program/digital", label: "Digital Services", icon: Monitor, end: false },
  { to: "/ops/va-program/jobs", label: "Digital Jobs", icon: Briefcase, end: false },
  { to: "/ops/va-program/rates", label: "Rates", icon: Percent, end: false },
  { to: "/ops/va-program/teams", label: "Teams", icon: UsersThree, end: false },
  { to: "/ops/va-program/commissions", label: "Commissions", icon: CurrencyDollar, end: false, badge: "va_queue" },
  { to: "/ops/va-program/vas", label: "VA Accounts", icon: UsersThree, end: false },
  { to: "/ops/va-program/commercial", label: "Commercial", icon: Buildings, end: false },
];

const ownerPayoutsItem = { to: "/ops/payouts", label: "Payouts (Owner)", icon: Receipt, end: false, badge: "payouts" };

/**
 * Compute which group key contains the currently-active path.
 * Falls back to null (nothing open) if the path is in the flat home/settings section.
 */
function activeGroupKey(pathname, groupsWithItems) {
  // sort items in each group by descending prefix length for accurate match
  for (const g of groupsWithItems) {
    const match = [...g.items].sort((a, b) => b.to.length - a.to.length).find((n) =>
      n.end ? pathname === n.to : pathname === n.to || pathname.startsWith(n.to + "/")
    );
    if (match) return g.key;
  }
  return null;
}

function itemBadgeCount(item, counts) {
  if (item.badge === "pending") return counts.pending;
  if (item.badge === "quotes") return counts.quotes;
  if (item.badge === "messages") return counts.messages;
  if (item.badge === "payouts") return counts.payouts;
  if (item.badge === "va_queue") return counts.vaQueue;
  return 0;
}

function groupBadgeCount(group, counts) {
  return group.items.reduce((sum, it) => sum + (itemBadgeCount(it, counts) || 0), 0);
}

function badgeClassForItem(item) {
  // Distinct colors: quotes = blue, everything else = amber
  if (item.badge === "quotes") return "bg-[#0044FF] text-white";
  return "bg-[#F59E0B] text-white";
}

function NavItem({ item, counts, onNavigate, testPrefix, size = "desktop" }) {
  const count = itemBadgeCount(item, counts);
  const padY = size === "mobile" ? "py-3" : "py-2.5";
  const iconSize = size === "mobile" ? 20 : 18;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      data-testid={`${testPrefix}-${item.label.toLowerCase().replace(/ /g, "-")}`}
      className={({ isActive }) =>
        `flex items-center gap-3 border-l-2 pl-8 pr-3 ${padY} text-sm transition-colors ${
          isActive
            ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
            : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
        }`
      }
    >
      <item.icon size={iconSize} weight="duotone" />
      <span className="flex-1">{item.label}</span>
      {count > 0 && (
        <span
          data-testid={`${testPrefix}-${item.label.toLowerCase().replace(/ /g, "-")}-count`}
          className={`inline-flex h-5 min-w-[20px] items-center justify-center px-1.5 text-[10px] font-bold tracking-widest ${badgeClassForItem(item)}`}
        >
          {count > 99 ? "99+" : count}
        </span>
      )}
    </NavLink>
  );
}

function NavGroup({ group, isOpen, onToggle, counts, onNavigate, testPrefix, size = "desktop" }) {
  const groupCount = groupBadgeCount(group, counts);
  const padY = size === "mobile" ? "py-3" : "py-2.5";
  const iconSize = size === "mobile" ? 20 : 18;
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        data-testid={`${testPrefix}-group-${group.key}`}
        className={`flex w-full items-center gap-3 border-l-2 border-transparent px-3 ${padY} text-sm font-semibold text-[#030712] transition-colors hover:bg-[#F9FAFB]`}
      >
        <group.icon size={iconSize} weight="duotone" />
        <span className="flex-1 text-left">{group.label}</span>
        {!isOpen && groupCount > 0 && (
          <span
            data-testid={`${testPrefix}-group-${group.key}-count`}
            className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
          >
            {groupCount > 99 ? "99+" : groupCount}
          </span>
        )}
        <CaretDown
          size={14}
          weight="bold"
          className={`transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>
      {isOpen && (
        <div className="mt-1 space-y-1">
          {group.items.map((it) => (
            <NavItem
              key={it.to}
              item={it}
              counts={counts}
              onNavigate={onNavigate}
              testPrefix={testPrefix}
              size={size}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);
  const [quotesCount, setQuotesCount] = useState(0);
  const [vaQueueCount, setVaQueueCount] = useState(0);
  const [payoutsCount, setPayoutsCount] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { count: messagesUnread } = useUnreadMessages();

  // Groups w/ conditional Payouts (Owner) appended to Finance
  const effectiveGroups = useMemo(() => {
    return groups.map((g) => {
      if (g.key === "finance" && user?.is_owner) {
        return { ...g, items: [...g.items, ownerPayoutsItem] };
      }
      return g;
    });
  }, [user?.is_owner]);

  // Which group is auto-open based on active route (single-group open at a time)
  const openKey = useMemo(
    () => activeGroupKey(location.pathname, effectiveGroups),
    [location.pathname, effectiveGroups]
  );

  // VA is its own collapsible section — auto-open when route is under /ops/va-program
  const vaAutoOpen = location.pathname.startsWith("/ops/va-program");
  const [vaManualState, setVaManualState] = useState(null); // null = follow auto; true/false = user override for this session
  const vaOpen = vaManualState === null ? vaAutoOpen : vaManualState;

  // Manual override for the primary groups (per-mount session): null = follow auto
  const [manualOpenKey, setManualOpenKey] = useState(null);
  const effectiveOpenKey = manualOpenKey === undefined || manualOpenKey === null ? openKey : manualOpenKey;

  // Reset manual override whenever the active route changes to a different group
  useEffect(() => {
    setManualOpenKey(null);
    setVaManualState(null);
  }, [location.pathname]);

  const toggleGroup = (key) => {
    setManualOpenKey((prev) => {
      const current = prev === null ? openKey : prev;
      return current === key ? "" : key; // "" = all closed
    });
  };

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

  const counts = {
    pending: pendingCount,
    quotes: quotesCount,
    messages: messagesUnread,
    payouts: payoutsCount,
    vaQueue: vaQueueCount,
  };

  // Friendly section name for the mobile header — derived from the active nav.
  const allNav = [
    ...homeItems,
    ...effectiveGroups.flatMap((g) => g.items),
    ...vaNav,
    settingsItem,
  ];
  const activeItem = [...allNav]
    .sort((a, b) => b.to.length - a.to.length)
    .find((n) =>
      n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)
    );
  const currentLabel = activeItem ? activeItem.label : "HCOB Network";

  const renderNavBody = (testPrefix, size, onNavigate) => (
    <>
      {/* Home (flat) */}
      <div className="font-mono-label mb-3 px-3">Home</div>
      <div className="space-y-1">
        {homeItems.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.end}
            onClick={onNavigate}
            data-testid={`${testPrefix}-${it.label.toLowerCase()}`}
            className={({ isActive }) =>
              `flex items-center gap-3 border-l-2 px-3 ${
                size === "mobile" ? "py-3" : "py-2.5"
              } text-sm transition-colors ${
                isActive
                  ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                  : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
              }`
            }
          >
            <it.icon size={size === "mobile" ? 20 : 18} weight="duotone" />
            <span className="flex-1">{it.label}</span>
          </NavLink>
        ))}
      </div>

      {/* Grouped dropdown sections */}
      <div className="font-mono-label mb-3 mt-6 px-3">Manage</div>
      <div className="space-y-1">
        {effectiveGroups.map((g) => (
          <NavGroup
            key={g.key}
            group={g}
            isOpen={effectiveOpenKey === g.key}
            onToggle={() => toggleGroup(g.key)}
            counts={counts}
            onNavigate={onNavigate}
            testPrefix={testPrefix}
            size={size}
          />
        ))}
      </div>

      {/* Settings (flat, bottom of Manage) */}
      <div className="mt-2 space-y-1">
        <NavLink
          to={settingsItem.to}
          end={settingsItem.end}
          onClick={onNavigate}
          data-testid={`${testPrefix}-settings`}
          className={({ isActive }) =>
            `flex items-center gap-3 border-l-2 px-3 ${
              size === "mobile" ? "py-3" : "py-2.5"
            } text-sm transition-colors ${
              isActive
                ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
            }`
          }
        >
          <settingsItem.icon size={size === "mobile" ? 20 : 18} weight="duotone" />
          <span className="flex-1">{settingsItem.label}</span>
        </NavLink>
      </div>

      {/* VA Commission section — its own collapsible group */}
      <div className="font-mono-label mb-3 mt-6 px-3">VA Commission</div>
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => setVaManualState(!vaOpen)}
          aria-expanded={vaOpen}
          data-testid={`${testPrefix}-group-va`}
          className={`flex w-full items-center gap-3 border-l-2 border-transparent px-3 ${
            size === "mobile" ? "py-3" : "py-2.5"
          } text-sm font-semibold text-[#030712] transition-colors hover:bg-[#F9FAFB]`}
        >
          <Handshake size={size === "mobile" ? 20 : 18} weight="duotone" />
          <span className="flex-1 text-left">VA Program</span>
          {!vaOpen && vaQueueCount > 0 && (
            <span
              data-testid={`${testPrefix}-group-va-count`}
              className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
            >
              {vaQueueCount > 99 ? "99+" : vaQueueCount}
            </span>
          )}
          <CaretDown
            size={14}
            weight="bold"
            className={`transition-transform duration-200 ${vaOpen ? "rotate-180" : ""}`}
          />
        </button>
        {vaOpen && (
          <div className="mt-1 space-y-1">
            {vaNav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                onClick={onNavigate}
                data-testid={`${testPrefix}-${n.label.toLowerCase().replace(/ /g, "-")}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 border-l-2 pl-8 pr-3 ${
                    size === "mobile" ? "py-3" : "py-2.5"
                  } text-sm transition-colors ${
                    isActive
                      ? "border-[#0044FF] bg-[#F0F4FF] font-semibold text-[#030712]"
                      : "border-transparent text-[#4B5563] hover:bg-[#F9FAFB] hover:text-[#030712]"
                  }`
                }
              >
                <n.icon size={size === "mobile" ? 20 : 18} weight="duotone" />
                <span className="flex-1">{n.label}</span>
                {n.badge === "va_queue" && vaQueueCount > 0 && (
                  <span
                    data-testid={`${testPrefix}-${n.label.toLowerCase().replace(/ /g, "-")}-count`}
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {vaQueueCount > 99 ? "99+" : vaQueueCount}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        )}
      </div>
    </>
  );

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
          {renderNavBody("nav", "desktop", undefined)}
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
          <div className="flex items-center gap-1">
            <NotificationBell variant="light" homePath="/ops" />
            <button
              data-testid="admin-mobile-logout"
              onClick={onLogout}
              aria-label="Sign out"
              className="grid h-9 w-9 place-items-center border border-[#E5E7EB] text-[#030712] hover:bg-[#030712] hover:text-white"
            >
              <SignOut size={14} />
            </button>
          </div>
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
              {renderNavBody("mobile-nav", "mobile", () => setMobileOpen(false))}
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
        {/* Desktop-only top action bar — houses the notification bell. Mobile
            already gets one in its sticky header. */}
        <div className="hidden md:flex sticky top-0 z-10 items-center justify-end gap-2 border-b border-[#E5E7EB] bg-white/95 backdrop-blur px-6 py-2">
          <NotificationBell variant="light" homePath="/ops" />
        </div>
        <Outlet />
      </main>
    </div>
  );
}
