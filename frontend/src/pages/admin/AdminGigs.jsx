import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import {
  Plus,
  Megaphone,
  Broom,
  Wrench,
  Car,
  FolderSimple,
  ArrowUp,
  ArrowDown,
  ArrowsDownUp,
} from "@phosphor-icons/react";
import { TAG_CONFIG, getOrderedTags } from "@/lib/gigTags";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

// Sortable column definitions. `getValue(g)` returns the comparable value.
const SORT_COLS = {
  title: {
    label: "Title",
    getValue: (g) => (g.title || "").toLowerCase(),
  },
  category: {
    label: "Category",
    getValue: (g) => g.category || "",
  },
  scheduled: {
    label: "When",
    // scheduled_at is a real ISO datetime when present, scheduled_date is
    // free-text fallback. Sort by ISO when we have it.
    getValue: (g) => g.scheduled_at || g.scheduled_date || "",
  },
  pay: {
    label: "Pay",
    getValue: (g) => Number(g.pay_rate || 0),
  },
  slots: {
    label: "Slots",
    // Composite sort: filled-ratio descending makes "fullest first" useful,
    // but raw open-slots gives "needs-staffing first". Default to open slots
    // remaining (slots - filled) ascending so empty/at-risk gigs surface.
    getValue: (g) => Math.max(0, Number(g.slots || 0) - Number(g.slots_filled || 0)),
  },
  workers: {
    label: "Workers",
    getValue: (g) => Number(g.slots || 0),
  },
  status: {
    label: "Status",
    getValue: (g) => g.status || "",
  },
  blasts: {
    label: "Blasts",
    getValue: (g) => Number(g.blast_count || 0),
  },
  created: {
    label: "Posted",
    getValue: (g) => g.created_at || "",
  },
};

function compareValues(a, b) {
  if (a === b) return 0;
  if (a === null || a === undefined || a === "") return 1;
  if (b === null || b === undefined || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

function SortHeader({ k, align = "left", sortBy, sortDir, onSort }) {
  const col = SORT_COLS[k];
  const active = sortBy === k;
  const Icon = !active ? ArrowsDownUp : sortDir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      className={`whitespace-nowrap border-b border-[#E5E7EB] px-4 py-3 font-mono-label ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <button
        type="button"
        data-testid={`sort-${k}`}
        onClick={() => onSort(k)}
        className={`inline-flex items-center gap-1 hover:text-[#030712] ${
          active ? "text-[#030712]" : ""
        }`}
      >
        <span>{col.label}</span>
        <Icon
          size={12}
          weight={active ? "bold" : "regular"}
          className={active ? "text-[#0044FF]" : "text-[#9CA3AF]"}
        />
      </button>
    </th>
  );
}

export default function AdminGigs() {
  const [gigs, setGigs] = useState([]);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState(false);
  const [sortBy, setSortBy] = useState("created");
  const [sortDir, setSortDir] = useState("desc");
  const nav = useNavigate();

  useEffect(() => {
    const ctrl = { cancelled: false };
    (async () => {
      try {
        const params = {};
        if (category !== "all") params.category = category;
        if (status !== "all") params.status = status;
        const { data } = await api.get("/gigs", { params });
        if (!ctrl.cancelled) setGigs(data);
      } catch (e) {
        if (!ctrl.cancelled) toast.error(getErr(e));
      }
    })();
    return () => {
      ctrl.cancelled = true;
    };
  }, [category, status]);

  // Reload after the create-gig dialog reports success.
  const refresh = async () => {
    try {
      const params = {};
      if (category !== "all") params.category = category;
      if (status !== "all") params.status = status;
      const { data } = await api.get("/gigs", { params });
      setGigs(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const sortedGigs = useMemo(() => {
    const col = SORT_COLS[sortBy];
    if (!col) return gigs;
    const copy = [...gigs];
    copy.sort((a, b) => {
      const av = col.getValue(a);
      const bv = col.getValue(b);
      const cmp = compareValues(av, bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [gigs, sortBy, sortDir]);

  // Click a header → toggle direction (or pick that column with default desc)
  const onSort = (key) => {
    if (sortBy === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      // Sensible default direction per column
      const numericDefaults = new Set(["pay", "blasts", "workers", "scheduled", "created"]);
      setSortDir(numericDefaults.has(key) ? "desc" : "asc");
    }
  };

  const headerProps = { sortBy, sortDir, onSort };

  return (
    <div data-testid="admin-gigs">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div>
          <div className="font-mono-label">Manage</div>
          <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
            Gigs
          </h1>
        </div>
        <Button
          data-testid="open-create-gig"
          onClick={() => setOpen(true)}
          className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
        >
          <Plus size={16} className="mr-2" /> New gig
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E7EB] px-6 py-4 md:px-10">
        <span className="font-mono-label">Filters</span>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="h-9 w-44 rounded-none border-[#030712]" data-testid="filter-category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            <SelectItem value="cleaning">Cleaning</SelectItem>
            <SelectItem value="labor">Labor</SelectItem>
            <SelectItem value="driver">Driver / Ride</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-9 w-40 rounded-none border-[#030712]" data-testid="filter-status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="filled">Filled</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort dropdown — alternative to clicking column headers */}
        <div className="ml-auto flex items-center gap-2">
          <span className="font-mono-label text-[#4B5563]">Sort by</span>
          <Select
            value={sortBy}
            onValueChange={(v) => {
              setSortBy(v);
              const numericDefaults = new Set(["pay", "blasts", "workers", "scheduled", "created"]);
              setSortDir(numericDefaults.has(v) ? "desc" : "asc");
            }}
          >
            <SelectTrigger className="h-9 w-44 rounded-none border-[#030712]" data-testid="sort-by-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(SORT_COLS).map(([k, c]) => (
                <SelectItem key={k} value={k}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            type="button"
            data-testid="sort-direction-toggle"
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
            className="inline-flex h-9 items-center gap-1.5 border border-[#030712] bg-white px-3 text-xs font-bold uppercase tracking-widest hover:bg-[#030712] hover:text-white"
            title={sortDir === "asc" ? "Ascending — click to flip" : "Descending — click to flip"}
          >
            {sortDir === "asc" ? <ArrowUp size={12} weight="bold" /> : <ArrowDown size={12} weight="bold" />}
            {sortDir === "asc" ? "Asc" : "Desc"}
          </button>
        </div>
      </div>

      <div className="px-6 md:px-10 py-6">
        {sortedGigs.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No gigs match. Try a different filter or post a new gig.
          </div>
        ) : (
          <div className="overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr>
                  <SortHeader k="title" {...headerProps} />
                  <SortHeader k="category" {...headerProps} />
                  <SortHeader k="scheduled" {...headerProps} />
                  <SortHeader k="pay" {...headerProps} />
                  <SortHeader k="slots" {...headerProps} />
                  <SortHeader k="status" {...headerProps} />
                  <SortHeader k="blasts" {...headerProps} />
                  <th className="border-b border-[#E5E7EB] px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {sortedGigs.map((g) => {
                  const Icon = CAT_ICON[g.category];
                  return (
                    <tr
                      key={g.gig_id}
                      data-testid={`gig-row-${g.gig_id}`}
                      className="hover:bg-[#F9FAFB]"
                    >
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <button
                            onClick={() => nav(`/ops/gigs/${g.gig_id}`)}
                            className="font-display text-base font-bold hover:text-[#0044FF]"
                          >
                            {g.title}
                          </button>
                          {getOrderedTags(g.tags).map((t) => {
                            const cfg = TAG_CONFIG[t];
                            const I = cfg.icon;
                            return (
                              <span
                                key={t}
                                data-testid={`tag-pill-${t}-${g.gig_id}`}
                                title={`${cfg.label} — pinned to top of feed`}
                                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-black tracking-widest ${cfg.pillClass}`}
                              >
                                <I size={9} weight="fill" /> {cfg.label}
                              </span>
                            );
                          })}
                          {g.project && (
                            <button
                              data-testid={`project-pill-${g.gig_id}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                nav(`/ops/projects/${g.project.project_id}`);
                              }}
                              title={`Part of project: ${g.project.title}`}
                              className="inline-flex max-w-[160px] items-center gap-1 truncate rounded-full bg-[#F3F4F6] px-2 py-0.5 text-[9px] font-black tracking-widest text-[#030712] hover:bg-[#E5E7EB]"
                            >
                              <FolderSimple size={9} weight="fill" />
                              <span className="truncate">{g.project.title}</span>
                            </button>
                          )}
                        </div>
                        <div className="text-xs text-[#4B5563]">{g.location}</div>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <span className="inline-flex items-center gap-2">
                          {Icon && <Icon size={16} weight="duotone" />}
                          <span className="text-xs uppercase tracking-wider">{g.category}</span>
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">{g.scheduled_date}</td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        ${Number(g.pay_rate).toFixed(2)} {g.pay_type === "hourly" ? "/hr" : "flat"}
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        {g.slots_filled}/{g.slots}
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <span
                          className={`px-2 py-1 text-[10px] font-bold tracking-widest ${
                            g.status === "open"
                              ? "bg-[#0044FF] text-white"
                              : "bg-[#030712] text-white"
                          }`}
                        >
                          {(g.status || "").toUpperCase()}
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        <span className="inline-flex items-center gap-1">
                          <Megaphone size={12} /> {g.blast_count || 0}
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-right">
                        <button
                          data-testid={`open-gig-${g.gig_id}`}
                          onClick={() => nav(`/ops/gigs/${g.gig_id}`)}
                          className="text-xs font-semibold text-[#0044FF] hover:underline"
                        >
                          Manage →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateGigDialog open={open} onOpenChange={setOpen} onCreated={refresh} />
    </div>
  );
}
