import React, { useEffect, useMemo, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ChartBar,
  Download,
  Table as TableIcon,
  CheckCircle,
  CurrencyDollar,
  Clock,
  Funnel,
  WarningCircle,
} from "@phosphor-icons/react";

// First day of the current month (local). Returns YYYY-MM-DD.
function firstOfMonth() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function AdminReports() {
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(todayISO());
  const [onlyApproved, setOnlyApproved] = useState(false);
  const [workerFilter, setWorkerFilter] = useState("");
  const [workers, setWorkers] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [settings, setSettings] = useState(null);
  const [lastExportUrl, setLastExportUrl] = useState(null);

  // Load workers for filter
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/admin/workers");
        setWorkers(data);
      } catch {
        // silent
      }
    })();
    (async () => {
      try {
        const { data } = await api.get("/admin/settings");
        setSettings(data);
      } catch {
        // silent
      }
    })();
  }, []);

  const buildParams = () => {
    const p = { only_approved: onlyApproved };
    // Treat the dates as full days inclusive — pad end to end-of-day
    if (start) p.start = `${start}T00:00:00`;
    if (end) p.end = `${end}T23:59:59`;
    if (workerFilter) p.worker_id = workerFilter;
    return p;
  };

  const run = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/reports/timesheets", {
        params: buildParams(),
      });
      setData(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  // Auto-load on mount
  useEffect(() => {
    run();
    // eslint-disable-next-line
  }, []);

  const downloadCsv = () => {
    const p = buildParams();
    const qs = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const url = `${API}/admin/reports/timesheets.csv?${qs.toString()}`;
    // Use a credentialed fetch + blob to preserve auth cookie
    (async () => {
      try {
        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const dl = document.createElement("a");
        const objectUrl = URL.createObjectURL(blob);
        dl.href = objectUrl;
        dl.download = `hcob-timesheets-${todayISO()}.csv`;
        document.body.appendChild(dl);
        dl.click();
        dl.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
        toast.success("CSV downloaded");
      } catch (e) {
        toast.error("CSV download failed");
      }
    })();
  };

  const exportToSheets = async () => {
    setExporting(true);
    setLastExportUrl(null);
    try {
      const { data } = await api.post(
        "/admin/reports/export-google-sheets",
        buildParams()
      );
      setLastExportUrl(data.url);
      toast.success(`Sheet created — ${data.rows} rows exported`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setExporting(false);
    }
  };

  const totals = data?.totals;
  const rows = data?.rows || [];

  // Group rows by date (YYYY-MM-DD of clock_in_at)
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
    <div data-testid="admin-reports">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label flex items-center gap-2">
          <ChartBar size={14} weight="duotone" /> Insights
        </div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          Timesheet reports
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Track hours worked, pay rates, and total earnings across your crew.
          Download a CSV or push the report straight into a fresh Google Sheet.
        </p>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-0 border-b border-[#E5E7EB] md:grid-cols-2 lg:grid-cols-5">
        <div className="border-b border-r border-[#E5E7EB] p-5 md:border-b-0">
          <Label className="font-mono-label flex items-center gap-1.5">
            <Funnel size={11} /> Start date
          </Label>
          <Input
            data-testid="report-start-date"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="mt-2 h-11 rounded-none border-[#030712]"
          />
        </div>
        <div className="border-b border-r border-[#E5E7EB] p-5 md:border-b-0">
          <Label className="font-mono-label">End date</Label>
          <Input
            data-testid="report-end-date"
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="mt-2 h-11 rounded-none border-[#030712]"
          />
        </div>
        <div className="border-b border-r border-[#E5E7EB] p-5 md:border-b-0">
          <Label className="font-mono-label">Worker</Label>
          <select
            data-testid="report-worker-filter"
            value={workerFilter}
            onChange={(e) => setWorkerFilter(e.target.value)}
            className="mt-2 h-11 w-full border border-[#030712] bg-white px-2"
          >
            <option value="">All workers</option>
            {workers.map((w) => (
              <option key={w.user_id} value={w.user_id}>
                {`${w.name} · ${w.email}`}
              </option>
            ))}
          </select>
        </div>
        <div className="border-b border-r border-[#E5E7EB] p-5 md:border-b-0">
          <Label className="font-mono-label">Filter</Label>
          <label className="mt-2 flex h-11 cursor-pointer items-center gap-2 border border-[#030712] bg-white px-3">
            <input
              data-testid="report-only-approved"
              type="checkbox"
              checked={onlyApproved}
              onChange={(e) => setOnlyApproved(e.target.checked)}
              className="accent-[#0044FF]"
            />
            <span className="text-sm">Only approved timesheets</span>
          </label>
        </div>
        <div className="p-5">
          <Label className="font-mono-label opacity-0">Run</Label>
          <Button
            data-testid="run-report-btn"
            onClick={run}
            disabled={loading}
            className="mt-2 h-11 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            {loading ? "Running…" : "Run report"}
          </Button>
        </div>
      </div>

      {/* Totals strip */}
      <div className="grid grid-cols-2 border-b border-[#E5E7EB] lg:grid-cols-4">
        <Kpi
          testId="kpi-rows"
          icon={TableIcon}
          label="Timesheets"
          value={totals?.rows ?? "—"}
        />
        <Kpi
          testId="kpi-hours"
          icon={Clock}
          label="Hours"
          value={totals ? `${(totals.hours ?? 0).toFixed(2)}h` : "—"}
        />
        <Kpi
          testId="kpi-earnings"
          icon={CurrencyDollar}
          label="Total earnings"
          value={totals ? `$${(totals.earnings ?? 0).toFixed(2)}` : "—"}
        />
        <Kpi
          testId="kpi-approved-earnings"
          icon={CheckCircle}
          label="Approved earnings"
          value={totals ? `$${(totals.approved_earnings ?? 0).toFixed(2)}` : "—"}
        />
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E7EB] px-6 py-4 md:px-10">
        <Button
          data-testid="download-csv-btn"
          onClick={downloadCsv}
          disabled={!rows.length}
          variant="outline"
          className="h-10 rounded-none border-[#030712]"
        >
          <Download size={14} className="mr-2" /> Download CSV
        </Button>
        <Button
          data-testid="export-sheets-btn"
          onClick={exportToSheets}
          disabled={exporting || !rows.length || !settings?.google_sheets_ready}
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
            <a className="ml-1 underline" href="/admin/settings">
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

      {/* Data table grouped by date */}
      <div className="px-6 py-6 md:px-10">
        {rows.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No timesheets match these filters. Try widening the date range.
          </div>
        ) : (
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
                    <span className="font-mono-label">
                      {g.rows.length} entries
                    </span>
                    <span className="font-semibold">
                      <Clock size={12} className="mr-1 inline" />{" "}
                      {g.hours.toFixed(2)}h
                    </span>
                    <span className="font-bold text-[#10B981]">
                      ${g.earnings.toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className="overflow-x-auto border border-[#E5E7EB]">
                  <table className="w-full text-sm">
                    <thead className="bg-[#F9FAFB]">
                      <tr className="text-left">
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Worker
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Gig
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          In
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Out
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Hours
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Rate
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          Earned
                        </th>
                        <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                          TS
                        </th>
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
                            {r.worker_name || "—"}
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
                            {r.earnings != null
                              ? `$${r.earnings.toFixed(2)}`
                              : "—"}
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
        )}
      </div>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, testId }) {
  return (
    <div
      data-testid={testId}
      className="flex items-center gap-3 border-r border-[#E5E7EB] p-5 last:border-r-0"
    >
      <div className="grid h-10 w-10 place-items-center bg-[#0044FF] text-white">
        <Icon size={18} weight="duotone" />
      </div>
      <div>
        <div className="font-mono-label">{label}</div>
        <div className="mt-1 font-display text-2xl font-black tracking-tight">
          {value}
        </div>
      </div>
    </div>
  );
}
