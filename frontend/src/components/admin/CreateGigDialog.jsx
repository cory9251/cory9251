import React, { useEffect, useState } from "react";
import { format } from "date-fns";
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
import {
  CalendarBlank,
  Clock,
  EyeSlash,
  Repeat,
  Sparkle,
  UserCircle,
  CheckCircle,
  MapPin,
  CaretDown,
  CaretUp,
} from "@phosphor-icons/react";

const SUBCATS = {
  cleaning: ["deep", "routine", "moveout", "specialty"],
  labor: ["general", "moving", "warehouse", "event"],
  driver: ["worker_transport", "delivery", "rideshare"],
};

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = ["00", "15", "30", "45"];

function buildScheduledAt(date, hour12, minute, ampm) {
  if (!date) return { iso: null, local: null, display: "" };
  const h12 = parseInt(hour12, 10);
  const min = parseInt(minute, 10);
  let h24 = h12 % 12;
  if (ampm === "PM") h24 += 12;
  const d = new Date(date);
  d.setHours(h24, min, 0, 0);
  // Wall-clock string (no TZ) — the single source of truth for display.
  const pad = (n) => String(n).padStart(2, "0");
  const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return {
    iso: d.toISOString(),
    local,
    display: format(d, "EEE MMM d · h:mm a"),
  };
}

export default function CreateGigDialog({
  open,
  onOpenChange,
  onCreated,
  initialDate,
  projectId,
  projectDefaults,
}) {
  const today = new Date();
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
    backup_slots: 0,
    duration_hours: "",
    break_minutes: 0,
    payment_timeline: "2_3_days",
    payment_timeline_note: "",
    contact_phone: "",
    required_badge_id: "",
    target_trade: "",
  });
  const [date, setDate] = useState(initialDate || today);
  const [hour, setHour] = useState("9");
  const [minute, setMinute] = useState("00");
  const [ampm, setAmpm] = useState("AM");
  const [recurrence, setRecurrence] = useState("none");
  const [repeatCount, setRepeatCount] = useState(4);
  // Suggested workers panel: collapsed by default on mobile so it doesn't
  // hide the form. Auto-expanded on first render on desktop.
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined") {
      setSuggestionsOpen(window.matchMedia("(min-width: 768px)").matches);
    }
  }, []);
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

  // Specialist trades for the "target trade" blast gate.
  const [tradeOptions, setTradeOptions] = useState([]);
  useEffect(() => {
    if (!open) return;
    api
      .get("/trades/definitions")
      .then(({ data }) => setTradeOptions(data?.trades || []))
      .catch(() => {});
  }, [open]);

  // Sync initialDate when reopened from calendar cell
  React.useEffect(() => {
    if (open && initialDate) setDate(initialDate);
  }, [open, initialDate]);

  // Pre-fill from project defaults when the dialog opens for a project. Only
  // applies to empty fields so the admin's typed values are never clobbered.
  React.useEffect(() => {
    if (!open) return;
    if (!projectDefaults) return;
    setForm((f) => ({
      ...f,
      location: f.location || projectDefaults.location || f.location,
      address_line:
        f.address_line || projectDefaults.address_line || f.address_line,
      payment_timeline:
        projectDefaults.payment_timeline || f.payment_timeline,
      payment_timeline_note:
        projectDefaults.payment_timeline_note || f.payment_timeline_note,
      contact_phone:
        f.contact_phone || projectDefaults.contact_phone || f.contact_phone,
    }));
  }, [open, projectDefaults]);

  // Auto-suggest matching workers as category + location change.
  // Parses a 5-digit ZIP out of the public location string.
  const [suggested, setSuggested] = useState([]);
  const zipMatch = (form.location || "").match(/\b(\d{5})\b/);
  const zipFromLoc = zipMatch ? zipMatch[1] : "";
  useEffect(() => {
    if (!open) return;
    if (!form.category) {
      setSuggested([]);
      return;
    }
    const controller = new AbortController();
    const t = setTimeout(async () => {
      try {
        const params = { category: form.category, limit: 6 };
        if (zipFromLoc) params.zip_code = zipFromLoc;
        const { data } = await api.get("/admin/workers/match", {
          params,
          signal: controller.signal,
        });
        setSuggested(data || []);
      } catch (e) {
        if (e.name !== "CanceledError" && e.name !== "AbortError") {
          // Non-blocking; just hide suggestions on error
          setSuggested([]);
        }
      }
    }, 300);
    return () => {
      controller.abort();
      clearTimeout(t);
    };
  }, [open, form.category, zipFromLoc]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    const { iso, local, display } = buildScheduledAt(date, hour, minute, ampm);
    if (!iso) {
      toast.error("Pick a date");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/gigs", {
        ...form,
        scheduled_date: display,
        scheduled_at: iso,
        scheduled_local: local,
        pay_rate: parseFloat(form.pay_rate || 0),
        slots: parseInt(form.slots || 1),
        backup_slots: parseInt(form.backup_slots || 0),
        duration_hours: form.duration_hours
          ? parseFloat(form.duration_hours)
          : null,
        break_minutes: parseInt(form.break_minutes || 0),
        address_line: form.address_line.trim() || null,
        required_badge_id: form.required_badge_id || null,
        target_trade: form.target_trade || null,
        recurrence,
        repeat_count: recurrence === "none" ? 1 : parseInt(repeatCount || 1),
      });
      const count = res?.data?.created_count || 1;
      toast.success(count > 1 ? `Created ${count} recurring gigs` : "Gig created");
      onOpenChange(false);
      onCreated && onCreated();
      // Reset only the volatile fields
      setForm({
        title: "",
        description: "",
        category: "cleaning",
        subcategory: "deep",
        location: "",
        address_line: "",
        pay_rate: "",
        pay_type: "hourly",
        slots: 1,
        backup_slots: 0,
        duration_hours: "",
        break_minutes: 0,
        payment_timeline: "2_3_days",
        payment_timeline_note: "",
        contact_phone: "",
        required_badge_id: "",
        target_trade: "",
      });
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl rounded-none border-[#030712] p-0"
        data-testid="create-gig-dialog"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-2xl font-black tracking-tight">
            Post a new assignment
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="grid max-h-[70vh] grid-cols-1 gap-4 overflow-y-auto p-6 md:max-h-[80vh] md:grid-cols-2"
        >
          <div className="md:col-span-2">
            <Label className="font-mono-label">Title</Label>
            <Input
              data-testid="gig-title"
              required
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="e.g. Deep clean — 4BR home"
            />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Description</Label>
            <div className="mt-2">
              <MarkdownEditor
                value={form.description}
                onChange={(v) => set("description", v)}
                placeholder="What's the job? Use **bold**, _italic_, and - bullets for clarity. Include arrival instructions, what to bring, parking notes, etc."
                testIdPrefix="gig-description"
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
              <SelectTrigger
                data-testid="gig-category"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
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
              <SelectTrigger
                data-testid="gig-subcategory"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
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
            <Label className="font-mono-label">Required certification (optional)</Label>
            <Select
              value={form.required_badge_id || "none"}
              onValueChange={(v) => set("required_badge_id", v === "none" ? "" : v)}
            >
              <SelectTrigger
                data-testid="gig-required-badge"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None — open to all workers</SelectItem>
                {badgeOptions.map((b) => (
                  <SelectItem key={b.badge_id} value={b.badge_id}>
                    {b.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Only workers HCOB-certified for this specialty can request the assignment.
            </div>
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Specialist trade targeting (optional)</Label>
            <Select
              value={form.target_trade || "none"}
              onValueChange={(v) => set("target_trade", v === "none" ? "" : v)}
            >
              <SelectTrigger
                data-testid="gig-target-trade"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None — open to the whole category</SelectItem>
                {tradeOptions.map((t) => (
                  <SelectItem key={t.trade_id} value={t.trade_id}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Blast + claiming restricted to workers with this trade verified (equipment proof on file).
            </div>
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Public location (street + zip)</Label>
            <Input
              data-testid="gig-location"
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
              data-testid="gig-address"
              value={form.address_line}
              onChange={(e) => set("address_line", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="123 Oak Ave, Baltimore, MD 21201"
            />
            <div className="mt-1 text-[11px] text-[#4B5563]">
              Hidden from unverified workers and anyone who hasn't accepted.
            </div>
          </div>

          {/* Date picker + time row */}
          <div>
            <Label className="font-mono-label flex items-center gap-1.5">
              <CalendarBlank size={12} /> Date
            </Label>
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  data-testid="gig-date-trigger"
                  className="mt-2 flex h-11 w-full items-center justify-between border border-[#030712] bg-white px-3 text-sm hover:bg-[#F9FAFB]"
                >
                  <span>{date ? format(date, "EEE MMM d, yyyy") : "Pick a date"}</span>
                  <CalendarBlank size={16} className="text-[#4B5563]" />
                </button>
              </PopoverTrigger>
              <PopoverContent
                className="w-auto rounded-none border-[#030712] p-0"
                align="start"
                data-testid="gig-date-popover"
              >
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
                <SelectTrigger
                  data-testid="gig-hour"
                  className="h-11 rounded-none border-[#030712]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {h}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={minute} onValueChange={setMinute}>
                <SelectTrigger
                  data-testid="gig-minute"
                  className="h-11 rounded-none border-[#030712]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MINUTES.map((m) => (
                    <SelectItem key={m} value={m}>
                      :{m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={ampm} onValueChange={setAmpm}>
                <SelectTrigger
                  data-testid="gig-ampm"
                  className="h-11 rounded-none border-[#030712]"
                >
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
              data-testid="gig-duration"
              type="number"
              step="0.5"
              value={form.duration_hours}
              onChange={(e) => set("duration_hours", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="4"
            />
          </div>

          <div>
            <Label className="font-mono-label">Break (min)</Label>
            <Input
              data-testid="gig-break-minutes"
              type="number"
              min="0"
              step="5"
              value={form.break_minutes}
              onChange={(e) => set("break_minutes", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="0"
            />
            <div className="mt-1 text-[10px] text-[#4B5563]">
              Unpaid break deducted from clocked time
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Pay type</Label>
            <Select
              value={form.pay_type}
              onValueChange={(v) => set("pay_type", v)}
            >
              <SelectTrigger
                data-testid="gig-paytype"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
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
              data-testid="gig-rate"
              type="number"
              step="0.01"
              required
              value={form.pay_rate}
              onChange={(e) => set("pay_rate", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="25"
            />
          </div>

          <div>
            <Label className="font-mono-label">Slots</Label>
            <Input
              data-testid="gig-slots"
              type="number"
              min={1}
              required
              value={form.slots}
              onChange={(e) => set("slots", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">
              Backup slots <span className="text-[#9CA3AF]">(optional)</span>
            </Label>
            <Input
              data-testid="gig-backup-slots"
              type="number"
              min={0}
              value={form.backup_slots}
              onChange={(e) => set("backup_slots", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="0"
            />
            <p className="mt-1 text-[10px] text-[#4B5563]">
              Auto-promoted to primary if a worker cancels. 0 = no backups.
            </p>
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Payment timeline</Label>
            <Select
              value={form.payment_timeline}
              onValueChange={(v) => set("payment_timeline", v)}
            >
              <SelectTrigger
                data-testid="gig-payment-timeline"
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
                data-testid="gig-payment-timeline-note"
                placeholder="e.g. paid Friday by Cash App after walkthrough"
                value={form.payment_timeline_note}
                onChange={(e) => set("payment_timeline_note", e.target.value)}
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            )}
          </div>

          <div>
            <Label className="font-mono-label">Contact phone</Label>
            <Input
              data-testid="gig-contact"
              value={form.contact_phone}
              onChange={(e) => set("contact_phone", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="+1 555 …"
            />
          </div>

          <div className="md:col-span-2 border-t border-[#E5E7EB] pt-4">
            <Label className="font-mono-label flex items-center gap-1.5">
              <Repeat size={12} /> Recurrence
            </Label>
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              <Select value={recurrence} onValueChange={setRecurrence}>
                <SelectTrigger
                  data-testid="gig-recurrence"
                  className="h-11 rounded-none border-[#030712]"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">One-time (no repeat)</SelectItem>
                  <SelectItem value="daily">Every day</SelectItem>
                  <SelectItem value="weekly">Every week</SelectItem>
                  <SelectItem value="biweekly">Every 2 weeks</SelectItem>
                  <SelectItem value="monthly">Every month</SelectItem>
                </SelectContent>
              </Select>
              {recurrence !== "none" && (
                <Input
                  data-testid="gig-repeat-count"
                  type="number"
                  min={2}
                  max={52}
                  value={repeatCount}
                  onChange={(e) => setRepeatCount(e.target.value)}
                  className="h-11 rounded-none border-[#030712]"
                  placeholder="How many occurrences? (max 52)"
                />
              )}
            </div>
            {recurrence !== "none" && (
              <div className="mt-1 text-[11px] text-[#4B5563]">
                Creates {repeatCount || 0} gigs spaced{" "}
                {recurrence === "daily"
                  ? "1 day"
                  : recurrence === "weekly"
                  ? "1 week"
                  : recurrence === "biweekly"
                  ? "2 weeks"
                  : "1 month"}{" "}
                apart, starting from the date above.
              </div>
            )}
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
              data-testid="submit-create-gig"
              type="submit"
              disabled={loading}
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {loading ? "Posting…" : "Post gig"}
            </Button>
          </div>
        </form>

        {/* Suggested workers — auto-updates from category + ZIP in location.
            Collapsed by default on mobile so it doesn't hide the form. */}
        {suggested.length > 0 && (
          <div
            data-testid="suggested-workers-panel"
            className="border-t border-[#E5E7EB] bg-[#F9FAFB]"
          >
            <button
              type="button"
              data-testid="suggested-workers-toggle"
              onClick={() => setSuggestionsOpen((v) => !v)}
              className="flex w-full items-center gap-2 px-6 py-4 text-left hover:bg-[#F0F4FF]"
              aria-expanded={suggestionsOpen}
            >
              <Sparkle size={14} weight="duotone" className="text-[#0044FF]" />
              <span className="font-mono-label">
                Best-fit workers
                <span className="ml-1.5 inline-flex items-center rounded-full bg-[#0044FF] px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-white">
                  {suggested.length}
                </span>
              </span>
              {zipFromLoc && (
                <span className="hidden text-[10px] text-[#4B5563] sm:inline">
                  · {form.category} · ZIP {zipFromLoc}
                </span>
              )}
              <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-semibold text-[#4B5563]">
                {suggestionsOpen ? "Hide" : "Show"}
                {suggestionsOpen ? (
                  <CaretUp size={12} weight="bold" />
                ) : (
                  <CaretDown size={12} weight="bold" />
                )}
              </span>
            </button>
            {suggestionsOpen && (
              <div className="max-h-[50vh] overflow-y-auto px-6 pb-5">
                <p className="text-xs text-[#4B5563]">
                  Based on profile skills + ZIP. Post the gig, then approve their
                  request or use "Add a worker" to assign directly.
                </p>
                <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                  {suggested.map((w) => (
                    <div
                      key={w.user_id}
                      data-testid={`suggested-worker-${w.user_id}`}
                      className="flex items-start gap-3 border border-[#E5E7EB] bg-white p-3"
                    >
                      <div className="grid h-9 w-9 shrink-0 place-items-center bg-[#F0F4FF] text-[#0044FF]">
                        <UserCircle size={20} weight="duotone" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <div className="truncate font-display text-sm font-bold">
                            {w.name}
                          </div>
                          <span className="ml-auto inline-flex items-center gap-0.5 bg-[#0044FF] px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-white">
                            {w.score}
                          </span>
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px] text-[#4B5563]">
                          {w.zip_code && (
                            <span className="inline-flex items-center gap-0.5">
                              <MapPin size={9} weight="duotone" /> {w.zip_code}
                            </span>
                          )}
                          {w.id_verified && (
                            <span className="inline-flex items-center gap-0.5 text-[#10B981]">
                              <CheckCircle size={9} weight="fill" /> ID OK
                            </span>
                          )}
                        </div>
                        {w.reasons.length > 0 && (
                          <div className="mt-1 truncate text-[10px] text-[#4B5563]">
                            {w.reasons.join(" · ")}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
