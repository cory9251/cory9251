import React, { useEffect, useState } from "react";
import { format, parseISO } from "date-fns";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import MarkdownEditor from "@/components/MarkdownEditor";
import { PAYMENT_TIMELINE_OPTIONS } from "@/lib/paymentTimeline";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { CalendarBlank, Clock, EyeSlash } from "@phosphor-icons/react";
import { TAG_PRIORITY, TAG_CONFIG } from "@/lib/gigTags";

const SUBCATS = {
  cleaning: ["deep", "routine", "moveout", "specialty"],
  labor: ["general", "moving", "warehouse", "event"],
  driver: ["worker_transport", "delivery", "rideshare"],
};

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = ["00", "15", "30", "45"];

function decomposeTime(gig) {
  // Prefer wall-clock (TZ-free) so the time editor opens with the EXACT hour
  // the admin originally entered, even if the viewer is in a different TZ
  // than the admin who created the gig.
  const wall = gig?.scheduled_local;
  let d;
  if (wall && typeof wall === "string") {
    const m = wall.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (m) {
      d = new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]), parseInt(m[4]), parseInt(m[5]), 0, 0);
    }
  }
  if (!d) {
    const iso = gig?.scheduled_at;
    if (!iso) return { date: new Date(), hour: "9", minute: "00", ampm: "AM" };
    d = parseISO(iso);
  }
  let h = d.getHours();
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  const m = d.getMinutes();
  const rounded = MINUTES.reduce(
    (best, cur) => (Math.abs(parseInt(cur) - m) < Math.abs(parseInt(best) - m) ? cur : best),
    "00"
  );
  return { date: d, hour: String(h), minute: rounded, ampm };
}

function buildScheduledAt(date, hour12, minute, ampm) {
  if (!date) return { iso: null, local: null, display: "" };
  const h12 = parseInt(hour12, 10);
  const min = parseInt(minute, 10);
  let h24 = h12 % 12;
  if (ampm === "PM") h24 += 12;
  const d = new Date(date);
  d.setHours(h24, min, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return { iso: d.toISOString(), local, display: format(d, "EEE MMM d · h:mm a") };
}

export default function EditGigDialog({ open, onOpenChange, gig, onSaved }) {
  const init = decomposeTime(gig);
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "cleaning",
    subcategory: "deep",
    location: "",
    address_line: "",
    pay_rate: "",
    pay_type: "hourly",
    slots: 1,
    duration_hours: "",
    break_minutes: "0",
    payment_timeline: "2_3_days",
    payment_timeline_note: "",
    contact_phone: "",
    required_badge_id: "",
  });
  const [date, setDate] = useState(init.date);
  const [hour, setHour] = useState(init.hour);
  const [minute, setMinute] = useState(init.minute);
  const [ampm, setAmpm] = useState(init.ampm);
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(false);

  // Certification badges for the "required certification" gate select.
  const [badgeOptions, setBadgeOptions] = useState([]);
  useEffect(() => {
    if (!open) return;
    api
      .get("/admin/badges")
      .then(({ data }) => setBadgeOptions((data || []).filter((b) => b.active)))
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (open && gig) {
      setForm({
        title: gig.title || "",
        description: gig.description || "",
        category: gig.category || "cleaning",
        subcategory: gig.subcategory || SUBCATS[gig.category || "cleaning"][0],
        location: gig.location || "",
        address_line: gig.address_line || "",
        pay_rate: gig.pay_rate != null ? String(gig.pay_rate) : "",
        pay_type: gig.pay_type || "hourly",
        slots: gig.slots ?? 1,
        duration_hours: gig.duration_hours != null ? String(gig.duration_hours) : "",
        break_minutes: gig.break_minutes != null ? String(gig.break_minutes) : "0",
        payment_timeline: gig.payment_timeline || "2_3_days",
        payment_timeline_note: gig.payment_timeline_note || "",
        contact_phone: gig.contact_phone || "",
        required_badge_id: gig.required_badge_id || "",
      });
      const d = decomposeTime(gig);
      setDate(d.date);
      setHour(d.hour);
      setMinute(d.minute);
      setAmpm(d.ampm);
      setTags(Array.isArray(gig.tags) ? gig.tags.filter((t) => TAG_PRIORITY.includes(t)) : []);
    }
  }, [open, gig]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleTag = (t) =>
    setTags((curr) => (curr.includes(t) ? curr.filter((x) => x !== t) : [...curr, t]));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { iso, local, display } = buildScheduledAt(date, hour, minute, ampm);
      await api.put(`/gigs/${gig.gig_id}`, {
        ...form,
        scheduled_date: display,
        scheduled_at: iso,
        scheduled_local: local,
        pay_rate: parseFloat(form.pay_rate || 0),
        slots: parseInt(form.slots || 1),
        duration_hours: form.duration_hours
          ? parseFloat(form.duration_hours)
          : null,
        break_minutes: parseInt(form.break_minutes || 0),
        // empty string clears address_line (treated as null on backend)
        address_line: form.address_line.trim() || null,
      });
      // Sync tags separately (independent endpoint) — only call if changed
      const before = (gig.tags || []).slice().sort().join(",");
      const after = tags.slice().sort().join(",");
      if (before !== after) {
        await api.put(`/gigs/${gig.gig_id}/tags`, { tags });
      }
      toast.success("Gig updated");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  if (!gig) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl rounded-none border-[#030712] p-0"
        data-testid="edit-gig-dialog"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-2xl font-black tracking-tight">
            Edit gig
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="grid max-h-[80vh] grid-cols-1 gap-4 overflow-y-auto p-6 md:grid-cols-2"
        >
          <div className="md:col-span-2">
            <Label className="font-mono-label">Title</Label>
            <Input
              data-testid="edit-gig-title"
              required
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Description</Label>
            <div className="mt-2">
              <MarkdownEditor
                value={form.description}
                onChange={(v) => set("description", v)}
                placeholder="What's the job? Use **bold**, _italic_, and - bullets for clarity."
                testIdPrefix="edit-gig-description"
                rows={5}
              />
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Category</Label>
            <Select
              value={form.category}
              onValueChange={(v) => {
                set("category", v);
                set("subcategory", SUBCATS[v][0]);
              }}
            >
              <SelectTrigger className="mt-2 h-11 rounded-none border-[#030712]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cleaning">Cleaning</SelectItem>
                <SelectItem value="labor">Labor</SelectItem>
                <SelectItem value="driver">Driver / Ride</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="font-mono-label">Subcategory</Label>
            <Select
              value={form.subcategory}
              onValueChange={(v) => set("subcategory", v)}
            >
              <SelectTrigger className="mt-2 h-11 rounded-none border-[#030712]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SUBCATS[form.category].map((s) => (
                  <SelectItem key={s} value={s}>
                    {s.replace("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Public location (street + zip)</Label>
            <Input
              data-testid="edit-gig-location"
              required
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="Oak Ave · 94110"
            />
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Shown to everyone. Keep it vague — no street number.
            </div>
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label flex items-center gap-1.5">
              <EyeSlash size={12} /> Full address (revealed on acceptance)
            </Label>
            <Input
              data-testid="edit-gig-address"
              value={form.address_line}
              onChange={(e) => set("address_line", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="123 Oak Ave, Baltimore, MD 21201"
            />
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Hidden from unverified workers and anyone who hasn't accepted.
            </div>
          </div>

          <div>
            <Label className="font-mono-label flex items-center gap-1.5">
              <CalendarBlank size={12} /> Date
            </Label>
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="mt-2 flex h-11 w-full items-center justify-between border border-[#030712] bg-white px-3 text-sm hover:bg-[#F9FAFB]"
                >
                  <span>{date ? format(date, "EEE MMM d, yyyy") : "Pick a date"}</span>
                  <CalendarBlank size={16} className="text-[#4B5563]" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-auto rounded-none border-[#030712] p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={(d) => d && setDate(d)}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </div>

          <div>
            <Label className="font-mono-label flex items-center gap-1.5">
              <Clock size={12} /> Time
            </Label>
            <div className="mt-2 grid grid-cols-3 gap-2">
              <Select value={hour} onValueChange={setHour}>
                <SelectTrigger className="h-11 rounded-none border-[#030712]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>{h}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={minute} onValueChange={setMinute}>
                <SelectTrigger className="h-11 rounded-none border-[#030712]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MINUTES.map((m) => (
                    <SelectItem key={m} value={m}>:{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={ampm} onValueChange={setAmpm}>
                <SelectTrigger className="h-11 rounded-none border-[#030712]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AM">AM</SelectItem>
                  <SelectItem value="PM">PM</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Duration (hrs)</Label>
            <Input
              type="number"
              step="0.5"
              value={form.duration_hours}
              onChange={(e) => set("duration_hours", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Break (min)</Label>
            <Input
              data-testid="edit-gig-break-minutes"
              type="number"
              min="0"
              step="5"
              value={form.break_minutes}
              onChange={(e) => set("break_minutes", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
            <div className="mt-1 text-[10px] text-[#4B5563]">
              Unpaid break deducted from clocked time
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Pay type</Label>
            <Select value={form.pay_type} onValueChange={(v) => set("pay_type", v)}>
              <SelectTrigger className="mt-2 h-11 rounded-none border-[#030712]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hourly">Hourly</SelectItem>
                <SelectItem value="flat">Flat rate</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="font-mono-label">Rate (USD)</Label>
            <Input
              type="number"
              step="0.01"
              required
              value={form.pay_rate}
              onChange={(e) => set("pay_rate", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Slots</Label>
            <Input
              data-testid="edit-gig-slots"
              type="number"
              min={1}
              required
              value={form.slots}
              onChange={(e) => set("slots", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
            {gig.slots_filled > 0 && (
              <div className="mt-1 text-[11px] text-[#4B5563]">
                {gig.slots_filled} worker(s) already accepted — slots can't go below this.
              </div>
            )}
          </div>

          <div>
            <Label className="font-mono-label">Contact phone</Label>
            <Input
              value={form.contact_phone}
              onChange={(e) => set("contact_phone", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Payment timeline</Label>
            <Select
              value={form.payment_timeline}
              onValueChange={(v) => set("payment_timeline", v)}
            >
              <SelectTrigger
                data-testid="edit-gig-payment-timeline"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAYMENT_TIMELINE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="mt-1 text-[10px] text-[#4B5563]">
              When workers get paid — shown as a pill on their feed and the gig detail
            </div>
            {form.payment_timeline === "custom" && (
              <Input
                data-testid="edit-gig-payment-timeline-note"
                placeholder="e.g. paid Friday by Cash App after walkthrough"
                value={form.payment_timeline_note}
                onChange={(e) => set("payment_timeline_note", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            )}
          </div>

          <div className="md:col-span-2 mt-2 border-t border-[#E5E7EB] pt-4">
            <Label className="font-mono-label">Pin tags</Label>
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Any active tag pins the gig to the top of the worker feed and the
              public landing snippet. Multiple are allowed.
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {TAG_PRIORITY.map((t) => {
                const cfg = TAG_CONFIG[t];
                const I = cfg.icon;
                const on = tags.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    data-testid={`edit-tag-toggle-${t}`}
                    onClick={() => toggleTag(t)}
                    className={`flex items-center justify-center gap-1.5 px-2 py-2 text-[10px] font-black tracking-[0.16em] transition-colors ${
                      on
                        ? cfg.pillClass
                        : "border border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
                    }`}
                  >
                    <I
                      size={12}
                      weight="fill"
                      className={on && cfg.pulse ? "animate-pulse" : ""}
                    />
                    {cfg.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="md:col-span-2 mt-2 flex justify-end gap-3 border-t border-[#E5E7EB] pt-4">
            <Button
              type="button"
              variant="outline"
              className="rounded-none"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              data-testid="submit-edit-gig"
              type="submit"
              disabled={loading}
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {loading ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
