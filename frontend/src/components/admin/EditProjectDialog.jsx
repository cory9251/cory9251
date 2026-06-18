import React, { useEffect, useState } from "react";
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

export default function EditProjectDialog({ open, onOpenChange, project, onSaved }) {
  const [form, setForm] = useState({
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
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && project) {
      setForm({
        title: project.title || "",
        description: project.description || "",
        client_name: project.client_name || "",
        defaults: {
          location: project.defaults?.location || "",
          scheduled_date: project.defaults?.scheduled_date || "",
          scheduled_at: project.defaults?.scheduled_at || "",
          payment_timeline: project.defaults?.payment_timeline || "",
          contact_phone: project.defaults?.contact_phone || "",
        },
      });
    }
  }, [open, project]);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setDefault = (k, v) =>
    setForm((f) => ({ ...f, defaults: { ...f.defaults, [k]: v } }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const cleanDefaults = Object.fromEntries(
        Object.entries(form.defaults).filter(([, v]) => v !== "" && v !== null)
      );
      await api.put(`/projects/${project.project_id}`, {
        title: form.title.trim(),
        description: form.description,
        client_name: form.client_name.trim() || null,
        defaults: cleanDefaults,
      });
      toast.success("Project updated");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="edit-project-dialog"
        className="max-h-[92vh] max-w-2xl overflow-hidden rounded-none border-[#030712] p-0"
      >
        <DialogHeader className="border-b border-[#E5E7EB] px-6 py-4">
          <DialogTitle className="font-display text-xl font-black">
            Edit project
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="grid max-h-[78vh] grid-cols-1 gap-4 overflow-y-auto p-6 md:grid-cols-2"
        >
          <div className="md:col-span-2">
            <Label className="font-mono-label">Project title</Label>
            <Input
              data-testid="edit-project-title"
              value={form.title}
              onChange={(e) => setField("title", e.target.value)}
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label className="font-mono-label">Client name</Label>
            <Input
              value={form.client_name}
              onChange={(e) => setField("client_name", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Description</Label>
            <div className="mt-2">
              <MarkdownEditor
                value={form.description}
                onChange={(v) => setField("description", v)}
                placeholder="Project scope, client notes, etc."
                testIdPrefix="edit-project-description"
                rows={4}
              />
            </div>
          </div>
          <div className="md:col-span-2 mt-2 border-t border-[#E5E7EB] pt-4">
            <Label className="font-mono-label">Defaults (pre-fill new assignments)</Label>
          </div>
          <div>
            <Label className="font-mono-label">Default location</Label>
            <Input
              value={form.defaults.location}
              onChange={(e) => setDefault("location", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label className="font-mono-label">Default date label</Label>
            <Input
              value={form.defaults.scheduled_date}
              onChange={(e) => setDefault("scheduled_date", e.target.value)}
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Default payment timeline</Label>
            <Select
              value={form.defaults.payment_timeline || "_none"}
              onValueChange={(v) =>
                setDefault("payment_timeline", v === "_none" ? "" : v)
              }
            >
              <SelectTrigger className="mt-2 h-11 rounded-none border-[#030712]">
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
              type="submit"
              disabled={saving}
              className="h-11 rounded-none bg-[#0044FF] px-5 text-white hover:bg-[#0036cc]"
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
