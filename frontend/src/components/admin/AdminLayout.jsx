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
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

const nav = [
  { to: "/admin", label: "Dashboard", icon: House, end: true },
  { to: "/admin/calendar", label: "Calendar", icon: CalendarBlank, end: false },
  { to: "/admin/requests", label: "Requests", icon: ClockCounterClockwise, end: false, badge: true },
  { to: "/admin/gigs", label: "Gigs", icon: Briefcase, end: false },
  { to: "/admin/workers", label: "Workers", icon: UsersThree, end: false },
  { to: "/admin/settings", label: "Settings", icon: Gear, end: false },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(null);

  const refreshPending = async () => {
    try {
      const { data } = await api.get("/admin/stats");
      setPendingCount(data?.pending_requests ?? 0);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    refreshPending();
  }, [location.pathname]);

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };
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
        <nav className="flex-1 px-3 py-6">
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
                {n.badge && pendingCount > 0 && (
                  <span
                    data-testid="nav-requests-count"
                    className="inline-flex h-5 min-w-[20px] items-center justify-center bg-[#F59E0B] px-1.5 text-[10px] font-bold tracking-widest text-white"
                  >
                    {pendingCount > 99 ? "99+" : pendingCount}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
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
        <header className="flex items-center justify-between border-b border-[#E5E7EB] px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={14} />
            </div>
            <div className="font-display text-base font-black">HCOB Network</div>
          </div>
          <button
            data-testid="admin-mobile-logout"
            onClick={onLogout}
            className="text-xs font-semibold text-[#0044FF]"
          >
            Sign out
          </button>
        </header>
        <nav className="flex border-b border-[#E5E7EB]">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex-1 py-3 text-center text-xs font-semibold ${
                  isActive
                    ? "border-b-2 border-[#0044FF] text-[#030712]"
                    : "text-[#4B5563]"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
