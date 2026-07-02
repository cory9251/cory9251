import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { categoryLabel, money } from "@/lib/ledgerOptions";

const thisMonth = () => {
  const d = new Date();
  const first = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
  return [first, d.toISOString().slice(0, 10)];
};
const ytd = () => {
  const d = new Date();
  return [`${d.getFullYear()}-01-01`, d.toISOString().slice(0, 10)];
};
const lastMonth = () => {
  const d = new Date();
  const y = d.getMonth() === 0 ? d.getFullYear() - 1 : d.getFullYear();
  const m = d.getMonth() === 0 ? 12 : d.getMonth();
  const last = new Date(y, m, 0).getDate();
  const mm = String(m).padStart(2, "0");
  return [`${y}-${mm}-01`, `${y}-${mm}-${last}`];
};

const PRESETS = [
  { key: "this_month", label: "This month", range: thisMonth },
  { key: "last_month", label: "Last month", range: lastMonth },
  { key: "ytd", label: "YTD", range: ytd },
  { key: "all", label: "All time", range: () => ["", ""] },
];

export const BookOverview = () => {
  const [[from, to], setRange] = useState(ytd());
  const [preset, setPreset] = useState("ytd");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    api.get(`/admin/ledger/summary?${params}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(getErr(e)));
  }, [from, to]);

  const maxCat = Math.max(1, ...(data?.expenses_by_category || []).map((c) => c.amount));

  return (
    <div data-testid="book-overview">
      {/* Date range */}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            data-testid={`book-preset-${p.key}`}
            onClick={() => { setPreset(p.key); setRange(p.range()); }}
            className={`border px-3 py-1.5 text-xs font-semibold uppercase tracking-widest ${
              preset === p.key ? "border-[#030712] bg-[#030712] text-white" : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {p.label}
          </button>
        ))}
        <div className="ml-2 flex items-center gap-2">
          <Input data-testid="book-date-from" type="date" value={from} onChange={(e) => { setPreset(""); setRange([e.target.value, to]); }} className="h-8 w-36 rounded-none border-[#E5E7EB] text-xs" />
          <span className="text-xs text-[#9CA3AF]">→</span>
          <Input data-testid="book-date-to" type="date" value={to} onChange={(e) => { setPreset(""); setRange([from, e.target.value]); }} className="h-8 w-36 rounded-none border-[#E5E7EB] text-xs" />
        </div>
      </div>

      {err && <div className="mb-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{err}</div>}
      {!data ? (
        <div className="font-mono-label">Loading…</div>
      ) : (
        <>
          {/* KPIs */}
          <div className="mb-6 grid gap-3 md:grid-cols-4">
            <div className="border border-[#E5E7EB] bg-white p-4" data-testid="book-kpi-income">
              <div className="font-mono-label">Income</div>
              <div className="mt-1 font-display text-3xl font-black text-emerald-700">{money(data.totals.income)}</div>
            </div>
            <div className="border border-[#E5E7EB] bg-white p-4" data-testid="book-kpi-expenses">
              <div className="font-mono-label">Expenses</div>
              <div className="mt-1 font-display text-3xl font-black text-red-600">{money(data.totals.expenses)}</div>
            </div>
            <div className="border-2 border-[#030712] bg-white p-4" data-testid="book-kpi-net">
              <div className="font-mono-label">Net P&amp;L</div>
              <div className={`mt-1 font-display text-3xl font-black ${data.totals.net >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                {money(data.totals.net)}
              </div>
            </div>
            <div className="border border-[#E5E7EB] bg-white p-4" data-testid="book-kpi-count">
              <div className="font-mono-label">Entries</div>
              <div className="mt-1 font-display text-3xl font-black">{data.entry_count}</div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Monthly chart */}
            <section className="border border-[#E5E7EB] bg-white p-5" data-testid="book-monthly-chart">
              <div className="font-mono-label mb-4">Income vs expenses by month</div>
              {data.by_month.length === 0 ? (
                <div className="py-10 text-center text-sm text-[#9CA3AF]">No entries in this range.</div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.by_month} margin={{ top: 4, right: 4, left: -14, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v, name) => [money(v), name]} />
                    <Bar dataKey="income" name="Income" fill="#059669" />
                    <Bar dataKey="expenses" name="Expenses" fill="#DC2626" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </section>

            {/* Expense categories */}
            <section className="border border-[#E5E7EB] bg-white p-5" data-testid="book-category-breakdown">
              <div className="font-mono-label mb-4">Expenses by category</div>
              {data.expenses_by_category.length === 0 ? (
                <div className="py-10 text-center text-sm text-[#9CA3AF]">No expenses in this range.</div>
              ) : (
                <div className="space-y-3">
                  {data.expenses_by_category.map((c) => (
                    <div key={c.category}>
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold">{categoryLabel(c.category)}</span>
                        <span>{money(c.amount)} · {((c.amount / Math.max(1, data.totals.expenses)) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="mt-1 h-2 bg-[#F3F4F6]">
                        <div className="h-2 bg-[#DC2626]" style={{ width: `${(c.amount / maxCat) * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Per-project profitability */}
          <section className="mt-6 border border-[#E5E7EB] bg-white" data-testid="book-project-table">
            <div className="font-mono-label border-b border-[#E5E7EB] px-5 py-3">Per-project profitability</div>
            {data.by_project.length === 0 ? (
              <div className="p-6 text-sm text-[#9CA3AF]">No entries linked to projects yet. Link income/expenses to projects when adding transactions.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-[#F9FAFB]">
                  <tr className="text-left font-mono uppercase text-[10px] tracking-widest text-[#4B5563]">
                    <th className="px-5 py-2.5">Project</th>
                    <th className="px-5 py-2.5">Income</th>
                    <th className="px-5 py-2.5">Expenses</th>
                    <th className="px-5 py-2.5">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_project.map((p) => (
                    <tr key={p.project_id} className="border-t border-[#E5E7EB]">
                      <td className="px-5 py-2.5 font-semibold">{p.title || p.project_id}</td>
                      <td className="px-5 py-2.5 text-emerald-700">{money(p.income)}</td>
                      <td className="px-5 py-2.5 text-red-600">{money(p.expenses)}</td>
                      <td className={`px-5 py-2.5 font-bold ${p.net >= 0 ? "text-emerald-700" : "text-red-600"}`}>{money(p.net)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
};
