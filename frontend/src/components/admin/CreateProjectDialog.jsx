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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import MarkdownEditor from "@/components/MarkdownEditor";
import { PAYMENT_TIMELINE_OPTIONS } from "@/lib/paymentTimeline";

const EMPTY = {
  title: "",
  description: "",
  client_name: "",
  defaults: {
    location: "",
    scheduled_date: "",
    scheduled_at: "",
    payment_timeline: "",
    contact_phone: "",
  },
};

export default function CreateProjectDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setDefault = (k, v) =>
    setForm((f) => ({ ...f, defaults: { ...f.defaults, [k]: v } }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) {
      toast.error("Project title is required");
      return;
    }
    setSaving(true);
    try {
      // Clean empty default fields so backend keeps them null
      const cleanDefaults = Object.fromEntries(
        Object.entries(form.defaults).filter(([, v]) => v !== "" && v !== null)
      );
      const { data } = await api.post("/projects", {
        title: form.title.trim(),
        description: form.description || "",
        client_name: form.client_name.trim() || null,
        defaults:
          Object.keys(cleanDefaults).length > 0 ? cleanDefaults : null,
      });
      toast.success("Project created");
      setForm(EMPTY);
      onOpenChange(false);
      onCreated && onCreated(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="create-project-dialog"
        className="max-h-[92vh] max-w-2xl overflow-hidden rounded-none border-[#030712] p-0"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-xl font-black">
            New project
          </DialogTitle>
          <p className="text-xs text-[#4B5563]">
            Group 2+ gigs that share a job site. Defaults pre-fill new gigs.
          </p>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="grid max-h-[78vh] grid-cols-1 gap-4 overflow-y-auto p-6 md:grid-cols-2"
        >
          <div className="md:col-span-2">
            <Label className="font-mono-label">Project title</Label>
            <Input
              data-testid="project-title"
              value={form.title}
              onChange={(e) => setField("title", e.target.value)}
              required
              placeholder="e.g. Backyard cleanout — Westmoreland"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Client name (optional)</Label>
            <Input
              data-testid="project-client"
              value={form.client_name}
              onChange={(e) => setField("client_name", e.target.value)}
              placeholder="M. Johnson"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Description</Label>
            <div className="mt-2">
              <MarkdownEditor
                value={form.description}
                onChange={(v) => setField("description", v)}
                placeholder="Plain language summary of the project scope. Bold/italic/bullets supported."
                testIdPrefix="project-description"
                rows={4}
              />
            </div>
          </div>

          <div className="md:col-span-2 mt-2 border-t border-[#E5E7EB] pt-4">
            <Label className="font-mono-label">Default values (pre-fill new gigs)</Label>
            <p className="mt-1 text-[11px] text-[#4B5563]">
              When you add a gig under this project, these fields auto-fill.
              You can override per gig.
            </p>
          </div>

          <div>
            <Label className="font-mono-label">Default location</Label>
            <Input
              data-testid="project-default-location"
              value={form.defaults.location}
              onChange={(e) => setDefault("location", e.target.value)}
              placeholder="Baltimore · 21201"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Default date label</Label>
            <Input
              data-testid="project-default-date"
              value={form.defaults.scheduled_date}
              onChange={(e) => setDefault("scheduled_date", e.target.value)}
              placeholder="Sat Jun 15"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>

          <div className="md:col-span-2">
            <Label className="font-mono-label">Default payment timeline</Label>
            <Select
              value={form.defaults.payment_timeline || "_none"}
              onValueChange={(v) => setDefault("payment_timeline", v === "_none" ? "" : v)}
            >
              <SelectTrigger
                data-testid="project-default-pt"
                className="mt-2 h-11 rounded-none border-[#030712]"
              >
                <SelectValue placeholder="(none)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none">(none)</SelectItem>
                {PAYMENT_TIMELINE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="md:col-span-2 mt-2 flex justify-end gap-3 border-t border-[#E5E7EB] pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="h-11 rounded-none"
            >
              Cancel
            </Button>
            <Button
              data-testid="project-submit"
              type="submit"
              disabled={saving}
              className="h-11 rounded-none bg-[#0044FF] px-5 text-white hover:bg-[#0036cc]"
            >
              {saving ? "Creating…" : "Create project"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
