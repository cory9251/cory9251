import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Phone,
  EnvelopeSimple,
  MapPin,
  CheckCircle,
  Trash,
  ArrowsClockwise,
  ChatCircle,
  Sparkle,
} from "@phosphor-icons/react";

const STATUS_OPTIONS = [
  { v: "new", label: "New" },
  { v: "contacted", label: "Contacted" },
  { v: "won", label: "Won" },
  { v: "lost", label: "Lost" },
  { v: "dismissed", label: "Dismissed" },
];

export default function AdminQuotes() {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [filter, setFilter] = useState("new");

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (filter !== "all") params.set("status", filter);
      const { data } = await api.get(`/admin/quote-requests?${params}`);
      setItems(data?.items || []);
      setCounts(data?.counts || {});
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const setStatus = async (quote_id, status) => {
    try {
      await api.patch(`/admin/quote-requests/${quote_id}`, { status });
      toast.success(`Marked ${status}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="px-5 py-8 md:px-10 md:py-10" data-testid="admin-quotes-page">
      <div className="font-mono-label">Lead inbox</div>
      <h1 className="mt-1 font-display text-4xl md:text-5xl font-black tracking-tight">
        Quote requests
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Customer leads from the <code>/customers</code> page. Twilio also texts
        the on-call number when a new request lands.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {[{ v: "all", label: "All" }, ...STATUS_OPTIONS].map((opt) => (
          <button
            key={opt.v}
            data-testid={`quote-filter-${opt.v}`}
            onClick={() => setFilter(opt.v)}
            className={`flex items-center gap-2 border px-3 py-2 text-xs font-semibold ${
              filter === opt.v
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#030712] hover:bg-[#F9FAFB]"
            }`}
          >
            {opt.label}
            {opt.v !== "all" && (
              <span
                className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold ${
                  filter === opt.v ? "bg-white/15 text-white" : "bg-[#F3F4F6] text-[#4B5563]"
                }`}
              >
                {counts[opt.v] ?? 0}
              </span>
            )}
          </button>
        ))}
        <Button
          variant="outline"
          onClick={load}
          className="ml-auto rounded-none border-[#030712]"
          data-testid="quote-refresh"
        >
          <ArrowsClockwise size={14} className="mr-1" /> Refresh
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="mt-10 border border-dashed border-[#E5E7EB] bg-[#F9FAFB] p-10 text-center">
          <Sparkle size={20} className="mx-auto text-[#4B5563]" />
          <div className="mt-3 font-display text-lg font-black">
            No {filter === "all" ? "" : filter} quote requests yet.
          </div>
          <div className="mt-1 text-xs text-[#4B5563]">
            New leads from the customers page will appear here.
          </div>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {items.map((q) => (
            <li
              key={q.quote_id}
              data-testid={`quote-row-${q.quote_id}`}
              className="border border-[#E5E7EB] bg-white p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-display text-lg font-black tracking-tight">
                      {q.name}
                    </div>
                    <StatusPill status={q.status} />
                    {q.sms_sent ? (
                      <span
                        title="HCOB owner was notified by SMS"
                        className="inline-flex items-center gap-1 bg-[#ECFDF5] px-2 py-0.5 text-[10px] font-bold text-[#22C55E]"
                      >
                        <CheckCircle size={10} weight="fill" /> SMS sent
                      </span>
                    ) : (
                      <span
                        title={q.sms_error || "SMS not sent"}
                        className="inline-flex items-center gap-1 bg-[#FEF2F2] px-2 py-0.5 text-[10px] font-bold text-[#EF4444]"
                      >
                        SMS · not sent
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-[#030712]">
                    <a
                      href={`tel:${q.phone}`}
                      className="inline-flex items-center gap-1 font-bold hover:text-[#0044FF]"
                    >
                      <Phone size={12} weight="fill" /> {q.phone}
                    </a>
                    {q.email && (
                      <a
                        href={`mailto:${q.email}`}
                        className="inline-flex items-center gap-1 hover:text-[#0044FF]"
                      >
                        <EnvelopeSimple size={12} /> {q.email}
                      </a>
                    )}
                    {q.address && (
                      <span className="inline-flex items-center gap-1 text-[#4B5563]">
                        <MapPin size={12} /> {q.address}
                      </span>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 text-xs">
                    <div>
                      <span className="font-mono-label text-[10px] text-[#4B5563]">
                        Service
                      </span>
                      <div className="font-semibold">{q.service}</div>
                    </div>
                    <div>
                      <span className="font-mono-label text-[10px] text-[#4B5563]">
                        Timeline
                      </span>
                      <div className="font-semibold">{q.timeline}</div>
                    </div>
                  </div>
                  {q.message && (
                    <div className="mt-3 border-l-2 border-[#E5E7EB] pl-3 text-sm text-[#030712]">
                      <ChatCircle
                        size={12}
                        className="mr-1 inline text-[#4B5563]"
                      />
                      {q.message}
                    </div>
                  )}
                  <div className="mt-3 font-mono-label text-[10px] text-[#4B5563]">
                    Received {formatDate(q.created_at)}
                  </div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-[#F3F4F6] pt-3">
                {STATUS_OPTIONS.filter((o) => o.v !== q.status).map((o) => (
                  <button
                    key={o.v}
                    data-testid={`quote-mark-${o.v}-${q.quote_id}`}
                    onClick={() => setStatus(q.quote_id, o.v)}
                    className="border border-[#E5E7EB] bg-white px-3 py-1.5 text-[11px] font-semibold hover:border-[#030712]"
                  >
                    Mark {o.label.toLowerCase()}
                  </button>
                ))}
                <button
                  data-testid={`quote-dismiss-${q.quote_id}`}
                  onClick={() => setStatus(q.quote_id, "dismissed")}
                  className="ml-auto inline-flex items-center gap-1 border border-[#E5E7EB] bg-white px-3 py-1.5 text-[11px] font-semibold text-[#9CA3AF] hover:border-[#EF4444] hover:text-[#EF4444]"
                  title="Dismiss (hide spam / duplicate)"
                >
                  <Trash size={11} /> Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    new: { bg: "bg-[#0044FF]", text: "text-white", label: "NEW" },
    contacted: { bg: "bg-[#F59E0B]", text: "text-white", label: "CONTACTED" },
    won: { bg: "bg-[#22C55E]", text: "text-white", label: "WON" },
    lost: { bg: "bg-[#9CA3AF]", text: "text-white", label: "LOST" },
    dismissed: { bg: "bg-[#F3F4F6]", text: "text-[#4B5563]", label: "DISMISSED" },
  };
  const m = map[status] || map.new;
  return (
    <span
      className={`${m.bg} ${m.text} px-2 py-0.5 text-[10px] font-bold tracking-widest`}
    >
      {m.label}
    </span>
  );
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso || "";
  }
}
