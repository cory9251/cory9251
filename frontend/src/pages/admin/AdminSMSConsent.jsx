import React, { useEffect, useMemo, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  ChatText,
  Download,
  MagnifyingGlass,
  ShieldCheck,
  Warning,
} from "@phosphor-icons/react";

/**
 * SMS Consent Log — Twilio A2P 10DLC compliance evidence.
 *
 * Renders a per-worker table of who has opted in to receive SMS, when they
 * opted in, and from where. This is the file we hand to a carrier auditor
 * if they ever challenge the consent trail for our texting campaigns.
 *
 * Data is READ-ONLY here. The opt-in flag itself is stamped at signup in
 * routes/auth.py; if a worker needs to be re-consented, they must submit
 * a new form.
 */
const FILTERS = [
  { key: "all", label: "All workers" },
  { key: "opted_in", label: "Opted in" },
  { key: "opted_out", label: "Not opted in" },
];

export default function AdminSMSConsent() {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({ total: 0, opted_in: 0, opted_out: 0 });
  const [filter, setFilter] = useState("opted_in");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/sms-consent", {
        params: {
          filter,
          search: search.trim() || undefined,
        },
      });
      setRows(data.rows || []);
      setCounts(data.counts || { total: 0, opted_in: 0, opted_out: 0 });
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [filter]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
  }, [search]);

  const downloadCsv = async () => {
    try {
      const qs = new URLSearchParams({ filter, format: "csv" });
      if (search.trim()) qs.set("search", search.trim());
      const res = await fetch(`${API}/admin/sms-consent?${qs.toString()}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const dl = document.createElement("a");
      const objectUrl = URL.createObjectURL(blob);
      dl.href = objectUrl;
      const today = new Date().toISOString().slice(0, 10);
      dl.download = `hcob-sms-consent-${today}.csv`;
      document.body.appendChild(dl);
      dl.click();
      dl.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
      toast.success("CSV downloaded");
    } catch {
      toast.error("CSV download failed");
    }
  };

  const optInRate = useMemo(() => {
    const total = counts.opted_in + counts.opted_out;
    if (!total) return "—";
    return `${Math.round((counts.opted_in / total) * 100)}%`;
  }, [counts]);

  return (
    <div data-testid="admin-sms-consent">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">Compliance</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          SMS Consent Log
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Per-worker record of who agreed to receive text messages, when they
          agreed, and from where. Export this as CSV if a carrier or Twilio
          asks for A2P&nbsp;10DLC consent evidence.
        </p>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-1 gap-px border-b border-[#E5E7EB] bg-[#E5E7EB] sm:grid-cols-3">
        <StatCell
          label="Opted in"
          value={counts.opted_in}
          testId="sms-stat-opted-in"
          accent="text-[#0044FF]"
        />
        <StatCell
          label="Not opted in"
          value={counts.opted_out}
          testId="sms-stat-opted-out"
          accent="text-[#92400E]"
        />
        <StatCell
          label="Opt-in rate"
          value={optInRate}
          testId="sms-stat-rate"
          accent="text-[#065F46]"
        />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E7EB] px-6 py-4 md:px-10">
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              data-testid={`sms-filter-${f.key}`}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 text-xs font-bold tracking-widest uppercase ${
                filter === f.key
                  ? "bg-[#030712] text-white"
                  : "border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative min-w-[220px] flex-1 max-w-sm">
          <MagnifyingGlass
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4B5563]"
          />
          <Input
            data-testid="sms-consent-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, email, phone"
            className="h-10 rounded-none border-[#030712] pl-9"
          />
        </div>
        <Button
          data-testid="sms-consent-export-csv"
          onClick={downloadCsv}
          className="ml-auto h-10 rounded-none bg-[#030712] px-4 text-white hover:bg-[#111827]"
        >
          <Download size={14} weight="bold" className="mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Table */}
      <div className="px-6 py-6 md:px-10">
        {loading ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            Loading…
          </div>
        ) : rows.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No workers match this filter.
          </div>
        ) : (
          <div className="overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB] text-left">
                <tr className="font-mono-label">
                  <th className="px-4 py-3">Worker</th>
                  <th className="px-4 py-3">Phone</th>
                  <th className="px-4 py-3">Consent</th>
                  <th className="px-4 py-3">Opted-in on</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.user_id}
                    data-testid={`sms-consent-row-${r.user_id}`}
                    className="border-t border-[#E5E7EB] align-top hover:bg-[#F9FAFB]"
                  >
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[#030712]">
                        {r.name || "—"}
                      </div>
                      <div className="text-xs text-[#4B5563]">{r.email}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[#030712]">
                      {r.phone || (
                        <span className="text-[#9CA3AF]">no phone</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {r.sms_opt_in ? (
                        <span className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#065F46]">
                          <ShieldCheck size={10} weight="fill" /> OPTED IN
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#92400E]">
                          <Warning size={10} weight="fill" /> NOT OPTED IN
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[#4B5563]">
                      {r.sms_opt_in_at
                        ? new Date(r.sms_opt_in_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {r.sms_opt_in_source ? (
                        <span className="inline-flex items-center gap-1 bg-[#0044FF]/10 px-2 py-1 font-bold tracking-widest text-[#0044FF]">
                          <ChatText size={9} weight="fill" />
                          {r.sms_opt_in_source.replace(/_/g, " ").toUpperCase()}
                        </span>
                      ) : (
                        <span className="text-[#9CA3AF]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-4 text-xs text-[#9CA3AF]">
          All outbound SMS automatically appends &ldquo;Reply STOP to opt
          out.&rdquo; for carrier compliance. Consent is captured on the
          worker signup form and stored per user with a timestamp.
        </p>
      </div>
    </div>
  );
}

function StatCell({ label, value, testId, accent = "" }) {
  return (
    <div
      data-testid={testId}
      className="bg-white px-6 py-5 md:px-10"
    >
      <div className="font-mono-label">{label}</div>
      <div className={`mt-1 font-display text-3xl font-black ${accent}`}>
        {value}
      </div>
    </div>
  );
}
