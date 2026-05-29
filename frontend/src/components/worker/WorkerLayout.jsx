import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  House,
  CheckSquare,
  User,
  SignOut,
  Lightning,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";

const tabs = [
  { to: "/app", label: "Feed", icon: House, end: true },
  { to: "/app/accepted", label: "Accepted", icon: CheckSquare, end: false },
  { to: "/app/profile", label: "Profile", icon: User, end: false },
];

export default function WorkerLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const onLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

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
          <Outlet />
        </main>

        <nav
          data-testid="worker-bottom-nav"
          className="sticky bottom-0 z-10 grid grid-cols-3 border-t border-[#E5E7EB] bg-white"
        >
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              data-testid={`tab-${t.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-1 py-3 text-[10px] font-semibold uppercase tracking-widest ${
                  isActive ? "text-[#0044FF]" : "text-[#4B5563]"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <t.icon size={22} weight={isActive ? "fill" : "duotone"} />
                  {t.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
