import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Plus,
  MagnifyingGlass,
  ArrowRight,
  Archive,
  ArrowUUpLeft,
  Users,
  Briefcase,
  CalendarBlank,
  User as UserIcon,
} from "@phosphor-icons/react";
import CreateProjectDialog from "@/components/admin/CreateProjectDialog";

export default function AdminProjects() {
  const nav = useNavigate();
  const [search, setSearch] = useSearchParams();
  const [items, setItems] = useState([]);
  const archived = search.get("archived") === "true";
  const setArchived = (v) => {
    const next = new URLSearchParams(search);
    if (v) next.set("archived", "true");
    else next.delete("archived");
    setSearch(next, { replace: true });
  };
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const load = async () => {
    try {
      const params = new URLSearchParams();
      params.set("archived", archived ? "true" : "false");
      if (q.trim()) params.set("q", q.trim());
      const { data } = await api.get(`/projects?${params.toString()}`);
      setItems(data || []);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [archived]);

  return (
    <div data-testid="admin-projects">
      <div className="flex flex-col gap-3 border-b border-[#E5E7EB] px-4 py-5 md:flex-row md:items-end md:justify-between md:gap-4 md:px-10 md:py-8">
        <div>
          <div className="font-mono-label">Projects</div>
          <h1 className="mt-1 font-display text-3xl font-black tracking-tight md:text-4xl">
            {archived ? "Archived" : "Active"} projects
          </h1>
          <p className="mt-1 text-xs text-[#4B5563] md:text-sm">
            Group 2+ gigs that share a job site so crews can coordinate.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex overflow-hidden border border-[#E5E7EB]">
            {[
              { v: false, label: "Active" },
              { v: true, label: "Archived" },
            ].map((opt) => (
              <button
                key={String(opt.v)}
                data-testid={`proj-filter-${opt.label.toLowerCase()}`}
                onClick={() => setArchived(opt.v)}
                className={`h-9 px-3 font-mono-label text-[10px] tracking-[0.18em] md:h-10 ${
                  archived === opt.v
                    ? "bg-[#030712] text-white"
                    : "bg-white text-[#4B5563] hover:bg-[#F9FAFB]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button
            data-testid="new-project-btn"
            onClick={() => setCreateOpen(true)}
            className="h-9 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc] md:h-10"
          >
            <Plus size={16} className="mr-1" /> New project
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2 border-b border-[#E5E7EB] px-4 py-3 md:px-10">
        <MagnifyingGlass size={16} className="text-[#4B5563]" />
        <Input
          data-testid="proj-search"
          placeholder="Search by title or client name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          className="h-9 rounded-none border-[#E5E7EB]"
        />
        <Button
          onClick={load}
          variant="outline"
          className="h-9 rounded-none border-[#E5E7EB]"
        >
          Search
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 md:gap-4 md:p-10 lg:grid-cols-3">
        {items.length === 0 ? (
          <div className="col-span-full border border-dashed border-[#E5E7EB] bg-[#F9FAFB] p-10 text-center">
            <div className="font-display text-base font-bold">
              No {archived ? "archived" : "active"} projects yet.
            </div>
            <p className="mt-1 text-xs text-[#4B5563]">
              Create a project to bundle gigs that share a job site.
            </p>
            {!archived && (
              <Button
                onClick={() => setCreateOpen(true)}
                className="mt-3 h-9 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              >
                <Plus size={14} className="mr-1" /> Create your first project
              </Button>
            )}
          </div>
        ) : (
          items.map((p) => (
            <button
              key={p.project_id}
              data-testid={`proj-card-${p.project_id}`}
              onClick={() => nav(`/ops/projects/${p.project_id}`)}
              className="group relative flex flex-col gap-3 border border-[#E5E7EB] bg-white p-5 text-left transition-all hover:-translate-y-0.5 hover:border-[#030712] hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.18)]"
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="font-mono-label flex items-center gap-1 text-[10px]">
                    {p.client_name ? (
                      <>
                        <UserIcon size={11} weight="duotone" />
                        {p.client_name}
                      </>
                    ) : (
                      "Project"
                    )}
                  </div>
                  <div className="mt-1 font-display text-lg font-black leading-tight">
                    {p.title || "(Untitled project)"}
                  </div>
                </div>
                {p.archived && (
                  <span className="font-mono-label rounded bg-[#F3F4F6] px-2 py-0.5 text-[9px]">
                    Archived
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 border-t border-[#E5E7EB] pt-3 text-xs">
                <Stat icon={Briefcase} value={p.gig_count} label="gigs" />
                <Stat
                  icon={Users}
                  value={`${p.slots_filled}/${p.slots_total}`}
                  label="slots"
                />
                <Stat
                  icon={CalendarBlank}
                  value={p.first_scheduled_at ? fmtDate(p.first_scheduled_at) : "—"}
                  label="starts"
                />
              </div>
              <div className="font-mono-label mt-1 inline-flex items-center gap-1 text-[10px] text-[#0044FF] opacity-0 transition-opacity group-hover:opacity-100">
                Open <ArrowRight size={11} weight="bold" />
              </div>
            </button>
          ))
        )}
      </div>

      <CreateProjectDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(p) => nav(`/ops/projects/${p.project_id}`)}
      />
    </div>
  );
}

const fmtDate = (iso) => {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
};

function Stat({ icon: Icon, value, label }) {
  return (
    <div className="leading-tight">
      <div className="font-mono-label flex items-center gap-1 text-[9px] text-[#4B5563]">
        {Icon && <Icon size={10} weight="bold" />} {label}
      </div>
      <div className="mt-0.5 font-display text-sm font-black">{value}</div>
    </div>
  );
}
