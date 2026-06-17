import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Trophy, ArrowLeft, Crown } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";

/**
 * VA-facing leaderboard. Earnings are NOT shown — just leads + booked + conversion.
 * Period toggle: month (default), week, all.
 */
export default function VALeaderboard() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [period, setPeriod] = useState("month");
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/va/leaderboard?period=${period}`);
        setItems(data.items || []);
      } catch (e) {
        setErr(getErr(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [period]);

  return (
    <div className="p-6 md:p-10" data-testid="va-leaderboard">
      <button
        onClick={() => nav("/va")}
        data-testid="leaderboard-back"
        className="font-mono-label flex items-center gap-1 hover:underline"
      >
        <ArrowLeft size={12} /> Back to dashboard
      </button>

      <div className="mt-3 mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono-label">Leaderboard</div>
          <h1 className="font-display text-4xl font-black tracking-tight flex items-center gap-2">
            <Trophy size={32} weight="duotone" /> Top performers
          </h1>
          <p className="mt-1 text-sm text-[#4B5563]">
            Ranked by leads submitted. Earnings stay private.
          </p>
        </div>

        <div className="inline-flex border border-[#030712]">
          {[
            { v: "week", l: "This week" },
            { v: "month", l: "This month" },
            { v: "all", l: "All time" },
          ].map((opt) => (
            <button
              key={opt.v}
              data-testid={`leaderboard-period-${opt.v}`}
              onClick={() => setPeriod(opt.v)}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-widest border-l first:border-l-0 border-[#030712] ${
                period === opt.v ? "bg-[#030712] text-white" : "bg-white text-[#030712]"
              }`}
            >
              {opt.l}
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>
      )}
      {loading ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-[#E5E7EB] bg-white p-8 text-center">
          <div className="font-mono-label text-[#9CA3AF]">No data yet for this period</div>
        </div>
      ) : (
        <div className="overflow-x-auto border border-[#E5E7EB] bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-[#F9FAFB]">
              <tr className="text-left font-mono-label">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">VA</th>
                <th className="px-4 py-3 text-right">Leads</th>
                <th className="px-4 py-3 text-right">Booked</th>
                <th className="px-4 py-3 text-right">Conversion</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.va_user_id}
                  data-testid={`leaderboard-row-${row.rank}`}
                  className={`border-t border-[#E5E7EB] ${
                    row.is_self ? "bg-[#EFF6FF] font-bold" : "hover:bg-[#F9FAFB]"
                  }`}
                >
                  <td className="px-4 py-3 font-mono">
                    {row.rank === 1 ? (
                      <span className="inline-flex items-center gap-1 text-[#D97706]">
                        <Crown size={14} weight="fill" /> 1
                      </span>
                    ) : (
                      `#${row.rank}`
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {row.va_name}
                    {row.is_self && (
                      <span className="ml-2 inline-block bg-[#0044FF] px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-white">
                        You
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{row.leads}</td>
                  <td className="px-4 py-3 text-right font-mono">{row.booked}</td>
                  <td className="px-4 py-3 text-right font-mono">{row.conversion}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
