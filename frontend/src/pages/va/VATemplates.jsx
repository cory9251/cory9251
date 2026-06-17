import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Copy, Lightbulb, MagnifyingGlass } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";

/**
 * VA pitch templates library — read-only. VAs copy a body to clipboard,
 * paste into Messages / Facebook / email.
 */
export default function VATemplates() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [channel, setChannel] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/va/templates");
        setItems(data.items || []);
      } catch (e) {
        setErr(getErr(e));
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    return items.filter((t) => {
      if (channel && t.channel !== channel && t.channel !== "any") return false;
      if (q) {
        const hay = `${t.title} ${t.body} ${t.category || ""}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [items, q, channel]);

  const copy = async (t) => {
    try {
      await navigator.clipboard.writeText(t.body);
      toast.success(`Copied "${t.title}" to clipboard`);
    } catch {
      toast.error("Copy failed — please select and copy manually");
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="va-templates">
      <button
        onClick={() => nav("/va")}
        data-testid="templates-back"
        className="font-mono-label flex items-center gap-1 hover:underline"
      >
        <ArrowLeft size={12} /> Back to dashboard
      </button>

      <div className="mt-3 mb-6">
        <div className="font-mono-label">VA Portal</div>
        <h1 className="font-display text-4xl font-black tracking-tight flex items-center gap-2">
          <Lightbulb size={32} weight="duotone" /> Pitch templates
        </h1>
        <p className="mt-1 text-sm text-[#4B5563]">
          Copy any template, then customize the {`{prospect_name}`} placeholder when sending.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
          <Input
            data-testid="templates-search"
            placeholder="Search templates…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-9 w-72 rounded-none border-[#030712] pl-9"
          />
        </div>
        <div className="inline-flex border border-[#030712]">
          {[
            { v: "", l: "All" },
            { v: "dm", l: "DM" },
            { v: "email", l: "Email" },
            { v: "sms", l: "SMS" },
          ].map((opt) => (
            <button
              key={opt.v || "all"}
              data-testid={`templates-channel-${opt.v || "all"}`}
              onClick={() => setChannel(opt.v)}
              className={`px-3 py-2 text-xs font-bold uppercase tracking-widest border-l first:border-l-0 border-[#030712] ${
                channel === opt.v ? "bg-[#030712] text-white" : "bg-white text-[#030712]"
              }`}
            >
              {opt.l}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>}

      {filtered.length === 0 ? (
        <div className="border border-[#E5E7EB] bg-white p-8 text-center">
          <div className="font-mono-label text-[#9CA3AF]">
            {items.length === 0
              ? "No templates yet — ask your Program Manager to add some."
              : "No templates match your filters"}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => (
            <div
              key={t.template_id}
              data-testid={`template-card-${t.template_id}`}
              className="flex flex-col gap-2 border border-[#E5E7EB] bg-white p-5"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-display text-lg font-black leading-tight">{t.title}</div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {t.category && (
                      <span className="bg-[#F3F4F6] px-2 py-0.5 text-[9px] uppercase tracking-widest text-[#4B5563]">
                        {t.category}
                      </span>
                    )}
                    <span className="bg-[#030712] px-2 py-0.5 text-[9px] uppercase tracking-widest text-white">
                      {t.channel}
                    </span>
                  </div>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm text-[#4B5563]">{t.body}</p>
              <button
                onClick={() => copy(t)}
                data-testid={`template-copy-${t.template_id}`}
                className="mt-auto inline-flex items-center gap-1 self-start border border-[#030712] bg-white px-3 py-1.5 text-xs font-semibold hover:bg-[#030712] hover:text-white"
              >
                <Copy size={12} weight="bold" /> Copy
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
