import React, { useRef, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import GigPhoto from "@/components/GigPhoto";
import { Camera, X, Plus } from "@phosphor-icons/react";

export const DEFAULT_SPEC = {
  photos: [],
  quantity_count: "",
  quantity_unit: "items",
  custom_unit: "",
  condition_notes: "",
  materials_provided: [],
  materials_bring: [],
  est_hours_min: "",
  est_hours_max: "",
  access_notes: "",
  pay_mode: "flat",
  pay_rate: "",
  pay_range_min: "",
  pay_range_max: "",
  pay_range_reason: "",
  date_mode: "fixed",
  window_start: "",
  window_end: "",
  window_arrival_time: "09:00",
};

const UNITS = ["items", "doors", "rooms", "windows", "sq ft", "linear ft", "loads", "custom"];

export function resolvedUnit(spec) {
  return spec.quantity_unit === "custom" ? spec.custom_unit.trim() : spec.quantity_unit;
}

export function validateSpecialist(spec, isoFixed) {
  const photos = spec.photos || [];
  if (photos.length < 2) return "Add at least 2 photos — the first becomes the card thumbnail";
  if (photos.length > 6) return "Max 6 photos";
  if (!parseFloat(spec.quantity_count) || !resolvedUnit(spec))
    return "Quantity + unit are required (e.g. 1 door, 2 rooms)";
  if (!spec.condition_notes.trim()) return "Condition notes are required";
  if (!spec.materials_provided.length && !spec.materials_bring.length)
    return "Fill the materials split — what HCOB provides vs what the pro brings";
  const mn = parseFloat(spec.est_hours_min);
  const mx = parseFloat(spec.est_hours_max);
  if (!mn || !mx || mx < mn) return "Estimated time range is required (min ≤ max)";
  if (spec.pay_mode === "range") {
    const a = parseFloat(spec.pay_range_min);
    const b = parseFloat(spec.pay_range_max);
    if (!a || !b || b <= a) return "Pay range needs a valid min < max";
    if (!spec.pay_range_reason.trim())
      return "A pay range cannot be published without a reason";
  } else if (!parseFloat(spec.pay_rate)) {
    return "Pay rate is required";
  }
  if (spec.date_mode === "fixed" && !isoFixed) return "Pick the fixed date";
  if (
    spec.date_mode === "window" &&
    (!spec.window_start || !spec.window_end || spec.window_end < spec.window_start)
  )
    return "Pick a valid date window (start ≤ end)";
  return null;
}

export function specPayload(spec) {
  const range = spec.pay_mode === "range";
  return {
    template: "specialist_project",
    photos: spec.photos,
    quantity_count: parseFloat(spec.quantity_count),
    quantity_unit: resolvedUnit(spec),
    condition_notes: spec.condition_notes.trim(),
    materials_provided: spec.materials_provided,
    materials_bring: spec.materials_bring,
    est_hours_min: parseFloat(spec.est_hours_min),
    est_hours_max: parseFloat(spec.est_hours_max),
    access_notes: spec.access_notes.trim() || null,
    pay_mode: spec.pay_mode,
    pay_rate: range ? null : parseFloat(spec.pay_rate),
    pay_type: spec.pay_mode === "hourly_estimate" ? "hourly" : "flat",
    pay_range_min: range ? parseFloat(spec.pay_range_min) : null,
    pay_range_max: range ? parseFloat(spec.pay_range_max) : null,
    pay_range_reason: range ? spec.pay_range_reason.trim() : null,
    date_mode: spec.date_mode,
    window_start: spec.date_mode === "window" ? spec.window_start : null,
    window_end: spec.date_mode === "window" ? spec.window_end : null,
    window_arrival_time:
      spec.date_mode === "window" ? spec.window_arrival_time || "09:00" : null,
  };
}

const shortDay = (s) => {
  try {
    const [y, m, d] = String(s).split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return s;
  }
};

export function specDateDisplay(spec) {
  if (spec.date_mode === "window")
    return `${shortDay(spec.window_start)}–${shortDay(spec.window_end)} — pick your day`;
  return "Flexible scheduling — we'll work around you";
}

function ChipListInput({ label, hint, items, onChange, testId, accent }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onChange([...items, v]);
    setDraft("");
  };
  return (
    <div>
      <div className="font-mono-label" style={{ color: accent }}>{label}</div>
      {hint && <div className="text-[10px] text-[#4B5563]">{hint}</div>}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span key={`${it}-${i}`} className="inline-flex items-center gap-1 border border-[#E5E7EB] bg-white px-2 py-1 text-xs font-semibold">
            {it}
            <button type="button" onClick={() => onChange(items.filter((_, x) => x !== i))} className="text-[#EF4444]">
              <X size={11} weight="bold" />
            </button>
          </span>
        ))}
      </div>
      <div className="mt-1.5 flex gap-2">
        <Input
          data-testid={testId}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder="Type an item, press Enter"
          className="h-9 rounded-none border-[#030712] text-sm"
        />
        <button type="button" data-testid={`${testId}-add`} onClick={add} className="grid h-9 w-9 shrink-0 place-items-center bg-[#030712] text-white">
          <Plus size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}

function ModeBtn({ active, onClick, title, sub, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`flex-1 border-2 px-3 py-2.5 text-left ${
        active ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#E5E7EB] bg-white hover:border-[#0044FF]/40"
      }`}
    >
      <div className="text-xs font-black">{title}</div>
      <div className="text-[10px] text-[#4B5563]">{sub}</div>
    </button>
  );
}

export default function SpecialistGigFields({ spec, patch }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file) => {
    if (!file) return;
    if ((spec.photos || []).length >= 6) {
      toast.error("Max 6 photos");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/gig-photos", fd);
      patch({ photos: [...spec.photos, data.path] });
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="md:col-span-2 space-y-4 border-2 border-[#0044FF]/30 bg-[#F8FAFF] p-4" data-testid="specialist-fields">
      <div className="font-mono-label text-[#0044FF]">Specialist project details</div>

      {/* Photos */}
      <div>
        <Label className="font-mono-label">Photos (2–6 · first = card thumbnail) *</Label>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          data-testid="spec-photo-input"
          onChange={(e) => upload(e.target.files?.[0])}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {(spec.photos || []).map((p, i) => (
            <div key={p} className="relative">
              <GigPhoto path={p} className="h-20 w-28 border border-[#E5E7EB] object-cover" />
              {i === 0 && (
                <span className="absolute left-1 top-1 bg-[#030712] px-1 py-0.5 text-[8px] font-bold text-white">THUMB</span>
              )}
              <button
                type="button"
                data-testid={`spec-photo-remove-${i}`}
                onClick={() => patch({ photos: spec.photos.filter((x) => x !== p) })}
                className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-[#EF4444] text-white"
              >
                <X size={10} weight="bold" />
              </button>
            </div>
          ))}
          <button
            type="button"
            data-testid="spec-photo-add"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
            className="flex h-20 w-28 flex-col items-center justify-center gap-1 border border-dashed border-[#0044FF]/50 bg-white text-[#0044FF]"
          >
            <Camera size={18} weight="duotone" />
            <span className="text-[10px] font-bold">{uploading ? "Uploading…" : "Add photo"}</span>
          </button>
        </div>
      </div>

      {/* Quantity + unit */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <div>
          <Label className="font-mono-label">Quantity *</Label>
          <Input
            data-testid="spec-quantity"
            type="number"
            step="0.5"
            min="0"
            value={spec.quantity_count}
            onChange={(e) => patch({ quantity_count: e.target.value })}
            className="mt-2 h-10 rounded-none border-[#030712]"
            placeholder="1"
          />
        </div>
        <div>
          <Label className="font-mono-label">Unit *</Label>
          <select
            data-testid="spec-unit"
            value={spec.quantity_unit}
            onChange={(e) => patch({ quantity_unit: e.target.value })}
            className="mt-2 h-10 w-full border border-[#030712] bg-white px-2 text-sm"
          >
            {UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
        {spec.quantity_unit === "custom" && (
          <div>
            <Label className="font-mono-label">Custom unit</Label>
            <Input
              data-testid="spec-custom-unit"
              value={spec.custom_unit}
              onChange={(e) => patch({ custom_unit: e.target.value })}
              className="mt-2 h-10 rounded-none border-[#030712]"
              placeholder="e.g. fixtures"
            />
          </div>
        )}
      </div>

      {/* Condition */}
      <div>
        <Label className="font-mono-label">Condition notes *</Label>
        <textarea
          data-testid="spec-condition"
          value={spec.condition_notes}
          onChange={(e) => patch({ condition_notes: e.target.value })}
          rows={2}
          className="mt-2 w-full border border-[#030712] bg-white p-2 text-sm"
          placeholder="e.g. Old door off track, frame in good shape"
        />
      </div>

      {/* Materials split */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ChipListInput
          label="We provide *"
          hint="Materials/hardware on site"
          accent="#10B981"
          items={spec.materials_provided}
          onChange={(v) => patch({ materials_provided: v })}
          testId="spec-materials-provided"
        />
        <ChipListInput
          label="You bring"
          hint="What the pro supplies"
          accent="#0044FF"
          items={spec.materials_bring}
          onChange={(v) => patch({ materials_bring: v })}
          testId="spec-materials-bring"
        />
      </div>

      {/* Est time */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="font-mono-label">Est. hours min *</Label>
          <Input data-testid="spec-est-min" type="number" step="0.5" min="0" value={spec.est_hours_min}
            onChange={(e) => patch({ est_hours_min: e.target.value })}
            className="mt-2 h-10 rounded-none border-[#030712]" placeholder="1" />
        </div>
        <div>
          <Label className="font-mono-label">Est. hours max *</Label>
          <Input data-testid="spec-est-max" type="number" step="0.5" min="0" value={spec.est_hours_max}
            onChange={(e) => patch({ est_hours_max: e.target.value })}
            className="mt-2 h-10 rounded-none border-[#030712]" placeholder="2" />
        </div>
      </div>

      {/* Pay mode */}
      <div>
        <Label className="font-mono-label">Pay *</Label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <ModeBtn testId="spec-pay-flat" active={spec.pay_mode === "flat"} onClick={() => patch({ pay_mode: "flat" })}
            title="Flat" sub='"$180 flat"' />
          <ModeBtn testId="spec-pay-hourly" active={spec.pay_mode === "hourly_estimate"} onClick={() => patch({ pay_mode: "hourly_estimate" })}
            title="Hourly + estimate" sub='"$45/hr · est 3–4 hrs"' />
          <ModeBtn testId="spec-pay-range" active={spec.pay_mode === "range"} onClick={() => patch({ pay_mode: "range" })}
            title="Range (interest only)" sub='"$150–$250" · reason required' />
        </div>
        {spec.pay_mode !== "range" ? (
          <div className="mt-2">
            <Input data-testid="spec-pay-rate" type="number" step="0.01" min="0" value={spec.pay_rate}
              onChange={(e) => patch({ pay_rate: e.target.value })}
              className="h-10 rounded-none border-[#030712]"
              placeholder={spec.pay_mode === "flat" ? "180 (total)" : "45 (per hour)"} />
          </div>
        ) : (
          <div className="mt-2 space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <Input data-testid="spec-range-min" type="number" step="1" min="0" value={spec.pay_range_min}
                onChange={(e) => patch({ pay_range_min: e.target.value })}
                className="h-10 rounded-none border-[#030712]" placeholder="Min, e.g. 150" />
              <Input data-testid="spec-range-max" type="number" step="1" min="0" value={spec.pay_range_max}
                onChange={(e) => patch({ pay_range_max: e.target.value })}
                className="h-10 rounded-none border-[#030712]" placeholder="Max, e.g. 250" />
            </div>
            <Input data-testid="spec-range-reason" value={spec.pay_range_reason}
              onChange={(e) => patch({ pay_range_reason: e.target.value })}
              className="h-10 rounded-none border-[#F59E0B] bg-[#FFFBEB]"
              placeholder='Reason (required) — e.g. "depends on frame condition"' />
            <div className="text-[10px] font-bold text-[#92400E]">
              Range pay → workers can only tap "I'm Interested". You lock the final price in a direct offer.
            </div>
          </div>
        )}
      </div>

      {/* Date mode */}
      <div>
        <Label className="font-mono-label">Date *</Label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <ModeBtn testId="spec-date-fixed" active={spec.date_mode === "fixed"} onClick={() => patch({ date_mode: "fixed" })}
            title="Fixed" sub="Use the date & time pickers above" />
          <ModeBtn testId="spec-date-window" active={spec.date_mode === "window"} onClick={() => patch({ date_mode: "window" })}
            title="Window" sub="Pro picks their day at claim" />
          <ModeBtn testId="spec-date-tbd" active={spec.date_mode === "tbd"} onClick={() => patch({ date_mode: "tbd" })}
            title="TBD (interest only)" sub={"\u201cWe\u2019ll work around you\u201d"} />
        </div>
        {spec.date_mode === "window" && (
          <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-3">
            <div>
              <Label className="font-mono-label">Window start</Label>
              <Input data-testid="spec-window-start" type="date" value={spec.window_start}
                onChange={(e) => patch({ window_start: e.target.value })}
                className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Window end</Label>
              <Input data-testid="spec-window-end" type="date" value={spec.window_end}
                onChange={(e) => patch({ window_end: e.target.value })}
                className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Arrival time</Label>
              <Input data-testid="spec-window-arrival" type="time" value={spec.window_arrival_time}
                onChange={(e) => patch({ window_arrival_time: e.target.value })}
                className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
          </div>
        )}
      </div>

      {/* Access notes */}
      <div>
        <Label className="font-mono-label">Access notes (optional)</Label>
        <Input
          data-testid="spec-access-notes"
          value={spec.access_notes}
          onChange={(e) => patch({ access_notes: e.target.value })}
          className="mt-2 h-10 rounded-none border-[#030712]"
          placeholder='e.g. "Lockbox on site" — never post codes here'
        />
      </div>
    </div>
  );
}
