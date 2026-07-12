import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UserPlus, ArrowSquareOut } from "@phosphor-icons/react";

const STATUS_META = {
  new: { label: "New", cls: "bg-[#0044FF] text-white" },
  contacted: { label: "Contacted", cls: "bg-amber-500 text-white" },
  onboarding: { label: "Onboarding", cls: "bg-indigo-600 text-white" },
  accepted: { label: "Accepted ✓", cls: "bg-emerald-700 text-white" },
  rejected: { label: "Rejected", cls: "bg-[#9CA3AF] text-white" },
};
const FILTERS = ["", "new", "contacted", "onboarding", "accepted", "rejected"];

const STREAM_LABELS = {
  commission_agent: "Commission Agent",
  gig_work: "Virtual Gig Work",
  both: "Both",
  not_sure: "Not sure yet",
};
const SKILL_LABELS = {
  graphic_design: "Graphic Design",
  web_development: "Web Development",
  seo: "SEO",
  social_media: "Social Media",
  data_entry: "Data Entry",
  admin_support: "Admin Support",
  digital_products: "Digital Products",
  marketing: "Marketing",
  none_yet: "None yet",
};

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function Row({ label, value }) {
  return (
    <div className="grid grid-cols-3 gap-2 border-b border-[#E5E7EB] py-2 text-sm last:border-0">
      <div className="font-mono-label text-[10px] pt-0.5">{label}</div>
      <div className="col-span-2 break-words">{value || "—"}</div>
    </div>
  );
}

function DetailDialog({ app, onClose, onUpdated }) {
  const [note, setNote] = useState(app?.admin_note || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => setNote(app?.admin_note || ""), [app]);
  if (!app) return null;

  const patch = async (payload, msg) => {
    setSaving(true);
    try {
      const { data } = await api.patch(`/admin/vp-applications/${app.application_id}`, payload);
      toast.success(msg);
      onUpdated(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={Boolean(app)} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="vp-app-detail-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black">{app.full_name}</DialogTitle>
          <DialogDescription>
            Applied {fmtDate(app.created_at)}
            {app.src ? ` · via ${app.src}` : ""}
          </DialogDescription>
        </DialogHeader>
        <div>
          <Row label="Email" value={app.email} />
          <Row label="Phone / WhatsApp" value={app.phone} />
          <Row
            label="Country / TZ"
            value={`${app.country}${app.timezone ? ` · ${app.timezone}` : ""}`}
          />
          <Row
            label="Streams"
            value={(app.streams || []).map((s) => STREAM_LABELS[s] || s).join(", ")}
          />
          <Row
            label="Skills"
            value={(app.skills || []).map((s) => SKILL_LABELS[s] || s).join(", ")}
          />
          <Row
            label="Portfolio"
            value={
              app.portfolio_url ? (
                <a
                  href={app.portfolio_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[#0044FF] hover:underline"
                >
                  {app.portfolio_url} <ArrowSquareOut size={13} />
                </a>
              ) : null
            }
          />
          <Row label="Hours / day" value={app.hours_per_day} />
          <Row label="Sales experience" value={app.sales_experience} />
          <Row label="Heard from" value={(app.heard_from || "").replace("_", " ")} />
          <Row label="Why join" value={app.why_join} />
        </div>
        <div className="space-y-3 border-t border-[#E5E7EB] pt-4">
          <div>
            <Label className="font-semibold">Status</Label>
            <Select
              value={app.status}
              onValueChange={(v) => patch({ status: v }, `Marked as ${STATUS_META[v].label}`)}
            >
              <SelectTrigger data-testid="vp-app-status-select" className="mt-1.5">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_META).map(([k, m]) => (
                  <SelectItem key={k} value={k}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="font-semibold">Internal note</Label>
            <Textarea
              data-testid="vp-app-note"
              className="mt-1.5"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Interview notes, routing decision, etc."
            />
            <Button
              data-testid="vp-app-save-note"
              size="sm"
              className="mt-2"
              disabled={saving}
              onClick={() => patch({ admin_note: note }, "Note saved")}
            >
              Save note
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminVPApplications() {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = async (status = filter) => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/vp-applications", {
        params: status ? { status } : {},
      });
      setItems(data.items);
      setCounts(data.counts || {});
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const onUpdated = (updated) => {
    setItems((prev) =>
      prev.map((it) => (it.application_id === updated.application_id ? updated : it))
    );
    setSelected(updated);
    load(filter);
  };

  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6" data-testid="admin-vp-applications">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2">
            <UserPlus size={26} weight="duotone" className="text-[#0044FF]" />
            VP Applications
          </h1>
          <p className="text-sm text-[#4B5563]">
            Virtual Professional applicants from the public recruiting page ·{" "}
            <a href="/vas" target="_blank" rel="noreferrer" className="text-[#0044FF] hover:underline">
              view page
            </a>
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f || "all"}
            data-testid={`vp-filter-${f || "all"}`}
            onClick={() => setFilter(f)}
            className={`border px-3 py-1.5 text-xs font-bold ${
              filter === f
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {f ? STATUS_META[f].label : "All"}{" "}
            <span className="opacity-60">({f ? counts[f] || 0 : total})</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-16 text-center text-sm text-[#9CA3AF]">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] py-16 text-center text-sm text-[#9CA3AF]">
          No applications{filter ? ` with status "${STATUS_META[filter].label}"` : " yet"}.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((app) => (
            <button
              key={app.application_id}
              data-testid={`vp-app-row-${app.application_id}`}
              onClick={() => setSelected(app)}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 border border-[#E5E7EB] bg-white p-4 text-left hover:border-[#030712] transition-colors"
            >
              <span
                className={`px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_META[app.status]?.cls || ""}`}
              >
                {STATUS_META[app.status]?.label || app.status}
              </span>
              <span className="font-bold">{app.full_name}</span>
              <span className="text-sm text-[#4B5563]">{app.country}</span>
              <span className="text-xs text-[#9CA3AF]">
                {(app.streams || []).map((s) => STREAM_LABELS[s] || s).join(" · ")}
              </span>
              <span className="ml-auto text-xs text-[#9CA3AF]">
                {app.hours_per_day} hrs/day · {fmtDate(app.created_at)}
              </span>
            </button>
          ))}
        </div>
      )}

      <DetailDialog app={selected} onClose={() => setSelected(null)} onUpdated={onUpdated} />
    </div>
  );
}
