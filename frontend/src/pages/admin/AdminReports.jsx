import React, { useEffect, useMemo, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import WorkerLink from "@/components/admin/WorkerLink";
import {
  ChartBar,
  Download,
  Table as TableIcon,
  CheckCircle,
  CurrencyDollar,
  Clock,
  Funnel,
  WarningCircle,
  UsersThree,
  Briefcase,
  ChartLineUp,
  Wallet,
  ClockCounterClockwise,
  Megaphone,
} from "@phosphor-icons/react";

// First day of the current month (local). Returns YYYY-MM-DD.
function firstOfMonth() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
// 90 days ago — wider default so date-filtered reports show data on first load
function ninetyDaysAgo() {
  const d = new Date();
  d.setDate(d.getDate() - 90);
  return d.toISOString().slice(0, 10);
}

// Each report type defines: its label, icon, which filters apply, the URL
// segment, and how to render its KPI strip from `totals`.
const REPORTS = {
  timesheets: {
    label: "Timesheets",
    icon: ClockCounterClockwise,
    filters: ["start", "end", "worker", "only_approved"],
    blurb:
      "Every clock-in / clock-out with hours and earnings — perfect for payroll runs.",
    kpis: (t) => [
      { label: "Timesheets", value: t?.rows ?? "—" },
      { label: "Hours", value: t ? `${(t.hours ?? 0).toFixed(2)}h` : "—" },
      { label: "Total earnings", value: t ? `$${(t.earnings ?? 0).toFixed(2)}` : "—" },
      { label: "Approved earnings", value: t ? `$${(t.approved_earnings ?? 0).toFixed(2)}` : "—" },
    ],
  },
  workers: {
    label: "Workers",
    icon: UsersThree,
    filters: ["skills", "zip_code", "zip_prefix", "status", "profile_status", "include_pii"],
    blurb:
      "Roster with contact info, skills, ID status, lifetime jobs / hours / earnings.",
    kpis: (t) => [
      { label: "Workers", value: t?.rows ?? "—" },
      { label: "Jobs completed", value: t?.jobs_completed ?? "—" },
      { label: "Total hours", value: t ? `${(t.total_hours ?? 0).toFixed(2)}h` : "—" },
      { label: "Total earned", value: t ? `$${(t.total_earned ?? 0).toFixed(2)}` : "—" },
    ],
  },
  gigs: {
    label: "Gigs",
    icon: Briefcase,
    filters: ["start", "end", "category", "gig_status"],
    blurb: "Every gig with date, location, slots, workers assigned, and payout so far.",
    kpis: (t) => [
      { label: "Gigs", value: t?.rows ?? "—" },
      { label: "Workers assigned", value: t?.workers_assigned ?? "—" },
      { label: "Workers completed", value: t?.workers_completed ?? "—" },
      { label: "Total payout", value: t ? `$${(t.total_payout ?? 0).toFixed(2)}` : "—" },
    ],
  },
  activity: {
    label: "Worker activity",
    icon: ChartLineUp,
    filters: ["start", "end", "worker"],
    blurb:
      "Per-worker performance: requested, approved, completed, no-shows, hours, earnings.",
    kpis: (t) => [
      { label: "Workers", value: t?.rows ?? "—" },
      { label: "Completed", value: t?.completed ?? "—" },
      { label: "No-shows", value: t?.no_shows ?? "—" },
      { label: "Total earned", value: t ? `$${(t.total_earned ?? 0).toFixed(2)}` : "—" },
    ],
  },
  earnings: {
    label: "Earnings",
    icon: Wallet,
    filters: ["start", "end", "only_approved"],
    blurb: "Payroll summary — one line per worker for the date range.",
    kpis: (t) => [
      { label: "Workers", value: t?.rows ?? "—" },
      { label: "Approved $", value: t ? `$${(t.approved_earned ?? 0).toFixed(2)}` : "—" },
      { label: "Pending $", value: t ? `$${(t.pending_earned ?? 0).toFixed(2)}` : "—" },
      { label: "Total $", value: t ? `$${(t.total_earned ?? 0).toFixed(2)}` : "—" },
    ],
  },
  blasts: {
    label: "Blasts",
    icon: Megaphone,
    filters: ["start", "end", "channel", "blast_kind"],
    blurb:
      "Every gig & project blast — when, to which gig/project, how many workers, on which channels, and who sent it.",
    kpis: (t) => [
      { label: "Total blasts", value: t?.rows ?? "—" },
      { label: "Workers targeted", value: t?.workers_targeted ?? "—" },
      { label: "Email sent", value: t?.email ?? "—" },
      { label: "SMS sent", value: t?.sms ?? "—" },
    ],
  },
};

const SKILL_OPTIONS = [
  { value: "deep_cleaning", label: "Deep cleaning" },
  { value: "routine_cleaning", label: "Routine cleaning" },
  { value: "moveouts", label: "Move-outs" },
  { value: "detailing", label: "Detailing" },
  { value: "window_cleaning", label: "Window cleaning" },
  { value: "carpet_cleaning", label: "Carpet cleaning" },
  { value: "post_construction", label: "Post-construction" },
  { value: "hourly_labor", label: "Hourly labor" },
  { value: "heavy_lifting", label: "Heavy lifting" },
  { value: "forklift", label: "Forklift" },
  { value: "moving", label: "Moving" },
  { value: "warehouse", label: "Warehouse" },
  { value: "landscaping", label: "Landscaping" },
  { value: "painting", label: "Painting" },
  { value: "driving", label: "Driving" },
  { value: "delivery", label: "Delivery" },
  { value: "cdl", label: "CDL" },
  { value: "fast_learner", label: "Fast learner" },
  { value: "bilingual", label: "Bilingual" },
  { value: "team_lead", label: "Team lead" },
];

export default function AdminReports() {
  const [type, setType] = useState("timesheets");
  const [start, setStart] = useState(ninetyDaysAgo());
  const [end, setEnd] = useState(todayISO());
  const [onlyApproved, setOnlyApproved] = useState(false);
  const [workerFilter, setWorkerFilter] = useState("");
  const [skills, setSkills] = useState([]);
  const [zipCode, setZipCode] = useState("");
  const [zipPrefix, setZipPrefix] = useState("");
  const [statusFilter, setStatusFilter] = useState(""); // worker status
  const [gigStatusFilter, setGigStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [includePii, setIncludePii] = useState(false);
  const [channelFilter, setChannelFilter] = useState("");
  const [blastKindFilter, setBlastKindFilter] = useState("");
  const [workers, setWorkers] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [settings, setSettings] = useState(null);
  const [lastExportUrl, setLastExportUrl] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [{ data: ws }, { data: st }] = await Promise.all([
          api.get("/admin/workers"),
          api.get("/admin/settings"),
        ]);
        setWorkers(ws);
        setSettings(st);
      } catch {}
    })();
  }, []);

  const cfg = REPORTS[type];
  const showFilter = (k) => cfg.filters.includes(k);

  const buildParams = () => {
    const p = {};
    if (showFilter("start") && start) p.start = `${start}T00:00:00`;
    if (showFilter("end") && end) p.end = `${end}T23:59:59`;
    if (showFilter("worker") && workerFilter) p.worker_id = workerFilter;
    if (showFilter("only_approved")) p.only_approved = onlyApproved;
    if (showFilter("skills") && skills.length) p.skills = skills.join(",");
    if (showFilter("zip_code") && zipCode) p.zip_code = zipCode;
    if (showFilter("zip_prefix") && !zipCode && zipPrefix) p.zip_prefix = zipPrefix;
    if (showFilter("status") && statusFilter) p.status = statusFilter;
    if (showFilter("profile_status") && profileStatus) p.profile_status = profileStatus;
    if (showFilter("gig_status") && gigStatusFilter) p.status = gigStatusFilter;
    if (showFilter("category") && categoryFilter) p.category = categoryFilter;
    if (showFilter("include_pii")) p.include_pii = includePii;
    if (showFilter("channel") && channelFilter) p.channel = channelFilter;
    if (showFilter("blast_kind") && blastKindFilter) p.kind = blastKindFilter;
    return p;
  };

  const run = async () => {
    setLoading(true);
    setLastExportUrl(null);
    try {
      const { data } = await api.get(`/admin/reports/${type}`, {
        params: buildParams(),
      });
      // Normalize timesheets response shape — it returns rows but no columns
      if (type === "timesheets") {
        setData({
          rows: data.rows,
          totals: data.totals,
          columns: null, // built-in rendering below
        });
      } else {
        setData(data);
      }
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  // Re-fetch when type or any filter changes (debounced so multi-clicks don't
  // hammer the API). Clearing `data` on type change avoids rendering a stale
  // dataset with the wrong column shape — which previously crashed the page.
  useEffect(() => {
    setData(null);
    setLastExportUrl(null);
    // Gigs report works against `scheduled_date` strings — many of which are
    // free-text ("today", "Fri Mar 6 · 9:00 AM"). Clear the default 90-day
    // window so the admin sees ALL gigs and can opt-in to a range.
    if (type === "gigs") {
      setStart("");
      setEnd("");
    } else if (!start && !end) {
      // Restore defaults when leaving Gigs
      setStart(ninetyDaysAgo());
      setEnd(todayISO());
    }
  }, [type]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const t = setTimeout(() => {
      run();
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [
    type, start, end, onlyApproved, workerFilter, skills, zipCode,
    zipPrefix, statusFilter, gigStatusFilter, categoryFilter,
    profileStatus, includePii, channelFilter, blastKindFilter,
  ]);

  const downloadCsv = () => {
    const p = buildParams();
    const qs = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "" && v !== false) qs.set(k, String(v));
    });
    const url = `${API}/admin/reports/${type}.csv?${qs.toString()}`;
    (async () => {
      try {
        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const dl = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        dl.href = objectUrl;
        dl.download = `hcob-${type}-${todayISO()}.csv`;
        document.body.appendChild(dl);
        dl.click();
        dl.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
        toast.success("CSV downloaded");
      } catch {
        toast.error("CSV download failed");
      }
    })();
  };

  const exportToSheets = async () => {
    setExporting(true);
    setLastExportUrl(null);
    try {
      const { data } = await api.post("/admin/reports/export-google-sheets", {
        report_type: type,
        ...buildParams(),
      });
      setLastExportUrl(data.url);
      toast.success(`Sheet created — ${data.rows} rows exported`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setExporting(false);
    }
  };

  const toggleSkill = (v) =>
    setSkills((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));

  // Build KPI tiles
  const kpis = useMemo(() => {
    if (!data) return cfg.kpis(null);
    const totals = data.totals;
    return cfg.kpis(totals);
  }, [data, cfg]);

  return (
    <div data-testid="admin-reports">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label flex items-center gap-2">
          <ChartBar size={14} weight="duotone" /> Insights
        </div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          Reports
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Pick a report type, set filters, then download a CSV or push to a
          fresh Google Sheet.
        </p>
      </div>

      {/* Report-type tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        {Object.entries(REPORTS).map(([key, c]) => {
          const Icon = c.icon;
          const active = key === type;
          return (
            <button
              key={key}
              data-testid={`report-tab-${key}`}
              onClick={() => setType(key)}
              className={`inline-flex items-center gap-2 px-3 py-2 text-xs font-bold tracking-widest uppercase ${
                active
                  ? "bg-[#030712] text-white"
                  : "border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
              }`}
            >
              <Icon size={14} weight={active ? "fill" : "duotone"} />
              {c.label}
            </button>
          );
        })}
      </div>

      {/* Blurb */}
      <div className="border-b border-[#E5E7EB] bg-[#F9FAFB] px-6 py-3 text-xs text-[#4B5563] md:px-10">
        {cfg.blurb}
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-0 border-b border-[#E5E7EB] md:grid-cols-2 lg:grid-cols-4">
        {showFilter("start") && (
          <FilterCell label="Start date">
            <Input
              data-testid="report-start-date"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="h-11 rounded-none border-[#030712]"
            />
          </FilterCell>
        )}
        {showFilter("end") && (
          <FilterCell label="End date">
            <Input
              data-testid="report-end-date"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="h-11 rounded-none border-[#030712]"
            />
          </FilterCell>
        )}
        {showFilter("worker") && (
          <FilterCell label="Worker">
            <select
              data-testid="report-worker-filter"
              value={workerFilter}
              onChange={(e) => setWorkerFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All workers</option>
              {workers.map((w) => (
                <option key={w.user_id} value={w.user_id}>
                  {`${w.name} · ${w.email}`}
                </option>
              ))}
            </select>
          </FilterCell>
        )}
        {showFilter("category") && (
          <FilterCell label="Category">
            <select
              data-testid="report-category-filter"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All categories</option>
              <option value="cleaning">Cleaning</option>
              <option value="labor">Labor</option>
              <option value="driver">Driver</option>
            </select>
          </FilterCell>
        )}
        {showFilter("gig_status") && (
          <FilterCell label="Gig status">
            <select
              data-testid="report-gig-status-filter"
              value={gigStatusFilter}
              onChange={(e) => setGigStatusFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="filled">Filled</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </FilterCell>
        )}
        {showFilter("channel") && (
          <FilterCell label="Channel">
            <select
              data-testid="report-channel-filter"
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All channels</option>
              <option value="in_app">In-app</option>
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="push">Push</option>
            </select>
          </FilterCell>
        )}
        {showFilter("blast_kind") && (
          <FilterCell label="Blast type">
            <select
              data-testid="report-blast-kind-filter"
              value={blastKindFilter}
              onChange={(e) => setBlastKindFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">Gigs + Projects</option>
              <option value="gig">Gig only</option>
              <option value="project">Project only</option>
            </select>
          </FilterCell>
        )}
        {showFilter("status") && (
          <FilterCell label="Worker status">
            <select
              data-testid="report-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All statuses</option>
              <option value="approved">Approved</option>
              <option value="pending">Pending</option>
              <option value="rejected">Rejected</option>
              <option value="suspended">Suspended</option>
            </select>
          </FilterCell>
        )}
        {showFilter("zip_code") && (
          <FilterCell label="ZIP (exact)">
            <Input
              data-testid="report-zip"
              value={zipCode}
              onChange={(e) => {
                setZipCode(e.target.value.replace(/\D/g, "").slice(0, 5));
                if (e.target.value) setZipPrefix("");
              }}
              maxLength={5}
              inputMode="numeric"
              placeholder="94110"
              className="h-11 rounded-none border-[#030712]"
            />
          </FilterCell>
        )}
        {showFilter("zip_prefix") && (
          <FilterCell label="ZIP starts with">
            <Input
              data-testid="report-zip-prefix"
              value={zipPrefix}
              onChange={(e) => {
                setZipPrefix(e.target.value.replace(/\D/g, "").slice(0, 3));
                if (e.target.value) setZipCode("");
              }}
              maxLength={3}
              inputMode="numeric"
              placeholder="941"
              className="h-11 rounded-none border-[#030712]"
            />
          </FilterCell>
        )}
        {showFilter("profile_status") && (
          <FilterCell label="Profile">
            <select
              data-testid="report-profile-status-filter"
              value={profileStatus}
              onChange={(e) => setProfileStatus(e.target.value)}
              className="h-11 w-full border border-[#030712] bg-white px-2"
            >
              <option value="">All</option>
              <option value="complete">Complete</option>
              <option value="incomplete">Incomplete</option>
            </select>
          </FilterCell>
        )}
        {showFilter("only_approved") && (
          <FilterCell label="Approved only">
            <label className="flex h-11 cursor-pointer items-center gap-2 border border-[#030712] bg-white px-3">
              <input
                data-testid="report-only-approved"
                type="checkbox"
                checked={onlyApproved}
                onChange={(e) => setOnlyApproved(e.target.checked)}
                className="accent-[#0044FF]"
              />
              <span className="text-sm">Only approved</span>
            </label>
          </FilterCell>
        )}
        {showFilter("include_pii") && (
          <FilterCell label="Personal info">
            <label className="flex h-11 cursor-pointer items-center gap-2 border border-[#030712] bg-white px-3">
              <input
                data-testid="report-include-pii"
                type="checkbox"
                checked={includePii}
                onChange={(e) => setIncludePii(e.target.checked)}
                className="accent-[#0044FF]"
              />
              <span className="text-sm">Include DOB, address, emergency</span>
            </label>
          </FilterCell>
        )}
        {showFilter("skills") && (
          <div className="col-span-1 border-b border-[#E5E7EB] p-5 md:col-span-2 lg:col-span-4">
            <Label className="font-mono-label">Worker skills</Label>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {SKILL_OPTIONS.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  data-testid={`report-skill-${s.value}`}
                  onClick={() => toggleSkill(s.value)}
                  className={`border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
                    skills.includes(s.value)
                      ? "border-[#0044FF] bg-[#0044FF] text-white"
                      : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#0044FF]"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}
        <FilterCell label="Run">
          <Button
            data-testid="run-report-btn"
            onClick={run}
            disabled={loading}
            className="h-11 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            {loading ? "Running…" : "Run report"}
          </Button>
        </FilterCell>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 border-b border-[#E5E7EB] lg:grid-cols-4">
        {kpis.map((k, i) => (
          <Kpi key={i} label={k.label} value={k.value} testId={`kpi-${i}`} />
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E7EB] px-6 py-4 md:px-10">
        <Button
          data-testid="download-csv-btn"
          onClick={downloadCsv}
          disabled={!data?.rows?.length}
          variant="outline"
          className="h-10 rounded-none border-[#030712]"
        >
          <Download size={14} className="mr-2" /> Download CSV
        </Button>
        <Button
          data-testid="export-sheets-btn"
          onClick={exportToSheets}
          disabled={
            exporting || !data?.rows?.length || !settings?.google_sheets_ready
          }
          className="h-10 rounded-none bg-[#10B981] text-white hover:bg-[#0e9971]"
          title={
            !settings?.google_sheets_ready
              ? "Configure Google Sheets in Settings first"
              : ""
          }
        >
          <TableIcon size={14} className="mr-2" />
          {exporting ? "Exporting…" : "Export to Google Sheets"}
        </Button>
        {!settings?.google_sheets_ready && (
          <span className="inline-flex items-center gap-1 text-xs text-[#92400E]">
            <WarningCircle size={12} weight="fill" /> Google Sheets not
            configured.{" "}
            <a className="ml-1 underline" href="/ops/settings">
              Set it up →
            </a>
          </span>
        )}
        {lastExportUrl && (
          <a
            data-testid="last-export-link"
            href={lastExportUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-2 border border-[#10B981] bg-[#ECFDF5] px-3 py-1.5 text-xs font-semibold text-[#065F46]"
          >
            <CheckCircle size={12} weight="fill" /> Open exported sheet
          </a>
        )}
      </div>

      {/* Data table */}
      <div className="px-6 py-6 md:px-10">
        <ReportTableErrorBoundary>
          {!data ? (
            <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
              {loading ? "Loading…" : "Run a report to see data."}
            </div>
          ) : !Array.isArray(data.rows) || data.rows.length === 0 ? (
            <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
              No data matches these filters.
            </div>
          ) : type === "timesheets" ? (
            <TimesheetTable rows={data.rows} />
          ) : (
            <DataTable rows={data.rows} columns={data.columns} />
          )}
        </ReportTableErrorBoundary>
      </div>
    </div>
  );
}

/**
 * Local error boundary so a render error in the data table never blanks the
 * whole reports page. Shows a friendly recovery message + reload hint.
 */
class ReportTableErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("AdminReports table crashed:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div
          data-testid="report-table-error"
          className="border border-[#EF4444]/30 bg-[#FEF2F2] p-6 text-sm"
        >
          <div className="font-display text-base font-bold text-[#991B1B]">
            Couldn't render this report.
          </div>
          <div className="mt-1 text-xs text-[#991B1B]/80">
            Try switching to another tab and back, or hit Run report again.
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-3 border border-[#EF4444] px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-[#EF4444]"
          >
            Dismiss
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function FilterCell({ label, children }) {
  return (
    <div className="border-b border-r border-[#E5E7EB] p-5 last:border-r-0 md:border-b-0">
      <Label className="font-mono-label">{label}</Label>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Kpi({ label, value, testId }) {
  return (
    <div
      data-testid={testId}
      className="flex items-center gap-3 border-r border-[#E5E7EB] p-5 last:border-r-0"
    >
      <div className="grid h-10 w-10 place-items-center bg-[#0044FF] text-white">
        <ChartBar size={18} weight="duotone" />
      </div>
      <div className="min-w-0">
        <div className="font-mono-label truncate">{label}</div>
        <div className="mt-1 font-display text-2xl font-black tracking-tight">
          {value}
        </div>
      </div>
    </div>
  );
}

/**
 * Generic data table that respects the {key, label} column metadata returned
 * by the backend. Cells are rendered as text — numbers / currency formatting
 * already done server-side where applicable.
 */
function DataTable({ rows, columns }) {
  // Defensive: if backend ever returns a report without columns metadata,
  // fall back to keys of the first row so we never crash the page.
  const cols = Array.isArray(columns) && columns.length
    ? columns
    : (rows && rows[0]
        ? Object.keys(rows[0]).map((k) => ({ key: k, label: k }))
        : []);
  if (!cols.length) {
    return (
      <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
        No columns to display.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto border border-[#E5E7EB]">
      <table className="w-full text-sm">
        <thead className="bg-[#F9FAFB]">
          <tr className="text-left">
            {cols.map((c) => (
              <th
                key={c.key}
                className="whitespace-nowrap border-b border-[#E5E7EB] px-3 py-2 font-mono-label"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.blast_id || r.user_id || r.gig_id || i}
              data-testid={`report-row-${r.blast_id || r.user_id || r.gig_id || i}`}
              className="hover:bg-[#F9FAFB]"
            >
              {cols.map((c) => (
                <td
                  key={c.key}
                  className="whitespace-nowrap border-b border-[#E5E7EB] px-3 py-2"
                >
                  {formatCell(r[c.key], c.key, c.fmt)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(v, key, fmt) {
  if (v === null || v === undefined || v === "") return "—";
  if (fmt === "dt" || key === "sent_at" || key === "clock_in_at" || key === "clock_out_at") {
    try {
      const d = new Date(v);
      if (Number.isNaN(d.getTime())) return String(v);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        year: "2-digit",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return String(v);
    }
  }
  if (
    key === "total_earned" ||
    key === "approved_earned" ||
    key === "pending_earned" ||
    key === "total_payout" ||
    key === "pay_rate"
  ) {
    return `$${Number(v).toFixed(2)}`;
  }
  if (key === "total_hours" || key === "duration_hours") {
    return `${Number(v).toFixed(2)}h`;
  }
  if (key === "kind") {
    return String(v).charAt(0).toUpperCase() + String(v).slice(1);
  }
  return String(v);
}

/** Timesheet legacy renderer — keeps the day-grouping behavior. */
function TimesheetTable({ rows }) {
  const grouped = useMemo(() => {
    const m = new Map();
    for (const r of rows) {
      const key = r.clock_in_at ? r.clock_in_at.slice(0, 10) : "no-date";
      if (!m.has(key)) m.set(key, { date: key, rows: [], hours: 0, earnings: 0 });
      const g = m.get(key);
      g.rows.push(r);
      g.hours += r.hours_worked || 0;
      g.earnings += r.earnings || 0;
    }
    return [...m.values()].sort((a, b) => (a.date < b.date ? 1 : -1));
  }, [rows]);

  return (
    <div className="space-y-8">
      {grouped.map((g) => (
        <div key={g.date} data-testid={`day-block-${g.date}`}>
          <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="font-mono-label">Day</div>
              <div className="font-display text-2xl font-black">
                {g.date === "no-date" ? "—" : g.date}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="font-mono-label">{g.rows.length} entries</span>
              <span className="font-semibold">
                <Clock size={12} className="mr-1 inline" /> {g.hours.toFixed(2)}h
              </span>
              <span className="font-bold text-[#10B981]">${g.earnings.toFixed(2)}</span>
            </div>
          </div>
          <div className="overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left">
                  {[
                    "Worker", "Gig", "In", "Out", "Hours", "Rate", "Earned", "TS",
                  ].map((h) => (
                    <th
                      key={h}
                      className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {g.rows.map((r) => (
                  <tr
                    key={r.acceptance_id}
                    data-testid={`report-row-${r.acceptance_id}`}
                    className="hover:bg-[#F9FAFB]"
                  >
                    <td className="border-b border-[#E5E7EB] px-3 py-2 font-semibold">
                      <WorkerLink workerId={r.worker_id} name={r.worker_name || "—"} />
                      <div className="text-[10px] font-normal text-[#4B5563]">
                        {r.worker_email}
                      </div>
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2">
                      {r.gig_title || "—"}
                      <div className="text-[10px] font-normal text-[#4B5563]">
                        {r.gig_scheduled_date}
                      </div>
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                      {r.clock_in_at
                        ? new Date(r.clock_in_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                      {r.clock_out_at
                        ? new Date(r.clock_out_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2 font-bold">
                      {r.hours_worked != null
                        ? `${r.hours_worked.toFixed(2)}h`
                        : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                      {r.pay_rate_applied != null
                        ? `$${r.pay_rate_applied.toFixed(2)}${
                            r.pay_type_applied === "hourly" ? "/hr" : " flat"
                          }`
                        : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2 font-bold text-[#10B981]">
                      {r.earnings != null ? `$${r.earnings.toFixed(2)}` : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-2">
                      {r.timesheet_approved ? (
                        <span className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                          <CheckCircle size={9} weight="fill" /> OK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                          PENDING
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
