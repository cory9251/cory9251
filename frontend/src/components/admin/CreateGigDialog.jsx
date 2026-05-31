import React, { useState } from "react";
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
import { CalendarBlank, Clock, EyeSlash, Repeat } from "@phosphor-icons/react";

const SUBCATS = {
  cleaning: ["deep", "routine", "moveout", "specialty"],
  labor: ["general", "moving", "warehouse", "event"],
  driver: ["worker_transport", "delivery", "rideshare"],
};

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = ["00", "15", "30", "45"];

function buildScheduledAt(date, hour12, minute, ampm) {
  if (!date) return { iso: null, display: "" };
  const h12 = parseInt(hour12, 10);
  const min = parseInt(minute, 10);
  let h24 = h12 % 12;
  if (ampm === "PM") h24 += 12;
  const d = new Date(date);
  d.setHours(h24, min, 0, 0);
  return {
    iso: d.toISOString(),
    display: format(d, "EEE MMM d · h:mm a"),
  };
}

export default function CreateGigDialog({
  open,
  onOpenChange,
  onCreated,
  initialDate,
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
    duration_hours: "",
    contact_phone: "",
  });
  const [date, setDate] = useState(initialDate || today);
  const [hour, setHour] = useState("9");
  const [minute, setMinute] = useState("00");
  const [ampm, setAmpm] = useState("AM");
  const [recurrence, setRecurrence] = useState("none");
  const [repeatCount, setRepeatCount] = useState(4);
  const [loading, setLoading] = useState(false);

  // Sync initialDate when reopened from calendar cell
  React.useEffect(() => {
    if (open && initialDate) setDate(initialDate);
  }, [open, initialDate]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    const { iso, display } = buildScheduledAt(date, hour, minute, ampm);
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
        pay_rate: parseFloat(form.pay_rate || 0),
        slots: parseInt(form.slots || 1),
        duration_hours: form.duration_hours
          ? parseFloat(form.duration_hours)
          : null,
        address_line: form.address_line.trim() || null,
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
        duration_hours: "",
        contact_phone: "",
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
            Post a new gig
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="grid max-h-[80vh] grid-cols-1 gap-4 overflow-y-auto p-6 md:grid-cols-2"
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
            <Textarea
              data-testid="gig-description"
              required
              rows={3}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              className="mt-2 rounded-none border-[#030712]"
            />
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
              placeholder="123 Oak Ave, San Francisco, CA 94110"
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
      </DialogContent>
    </Dialog>
  );
}
