import React, { useState } from "react";
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

const SUBCATS = {
  cleaning: ["deep", "routine", "moveout", "specialty"],
  labor: ["general", "moving", "warehouse", "event"],
  driver: ["worker_transport", "delivery", "rideshare"],
};

export default function CreateGigDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "cleaning",
    subcategory: "deep",
    location: "",
    scheduled_date: "",
    pay_rate: "",
    pay_type: "hourly",
    slots: 1,
    duration_hours: "",
    contact_phone: "",
  });
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/gigs", {
        ...form,
        pay_rate: parseFloat(form.pay_rate || 0),
        slots: parseInt(form.slots || 1),
        duration_hours: form.duration_hours
          ? parseFloat(form.duration_hours)
          : null,
      });
      toast.success("Gig created");
      onOpenChange(false);
      onCreated && onCreated();
      setForm({
        title: "",
        description: "",
        category: "cleaning",
        subcategory: "deep",
        location: "",
        scheduled_date: "",
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
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2">
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
            <Label className="font-mono-label">Location</Label>
            <Input
              data-testid="gig-location"
              required
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="123 Main St, City"
            />
          </div>

          <div>
            <Label className="font-mono-label">When</Label>
            <Input
              data-testid="gig-date"
              required
              value={form.scheduled_date}
              onChange={(e) => set("scheduled_date", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
              placeholder="Fri Mar 14 · 9:00 AM"
            />
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

          <div className="md:col-span-2 mt-2 flex justify-end gap-3">
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
