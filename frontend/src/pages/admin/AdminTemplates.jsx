import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft,
  Plus,
  Pencil,
  Trash,
  Archive,
  ArrowCounterClockwise,
  Lightbulb,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const CHANNELS = [
  { v: "any", l: "Any" },
  { v: "dm", l: "DM" },
  { v: "email", l: "Email" },
  { v: "sms", l: "SMS" },
];

export default function AdminTemplates() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState(null); // null | template object | 'new'
  const [form, setForm] = useState({ title: "", body: "", category: "", channel: "any" });

  const load = async () => {
    try {
      const { data } = await api.get(
        `/pm/templates${showArchived ? "?include_archived=true" : ""}`
      );
      setItems(data.items || []);
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [showArchived]);

  const startNew = () => {
    setForm({ title: "", body: "", category: "", channel: "any" });
    setEditing("new");
  };
  const startEdit = (t) => {
    setForm({
      title: t.title,
      body: t.body,
      category: t.category || "",
      channel: t.channel || "any",
    });
    setEditing(t);
  };

  const save = async () => {
    try {
      if (!form.title.trim() || !form.body.trim()) {
        toast.error("Title and body are required");
        return;
      }
      const payload = {
        title: form.title.trim(),
        body: form.body.trim(),
        category: form.category.trim() || null,
        channel: form.channel,
      };
      if (editing === "new") {
        await api.post("/pm/templates", payload);
        toast.success("Template created");
      } else {
        await api.patch(`/pm/templates/${editing.template_id}`, payload);
        toast.success("Template updated");
      }
      setEditing(null);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const toggleArchive = async (t) => {
    try {
      await api.patch(`/pm/templates/${t.template_id}`, { active: !t.active });
      toast.success(t.active ? "Archived" : "Re-activated");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const remove = async (t) => {
    if (!window.confirm(`Delete "${t.title}" permanently? VAs will lose access.`)) return;
    try {
      await api.delete(`/pm/templates/${t.template_id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="admin-templates">
      <button
        onClick={() => nav("/ops/va-program")}
        className="font-mono-label flex items-center gap-1 hover:underline"
      >
        <ArrowLeft size={12} /> VA Program
      </button>

      <div className="mt-3 mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono-label">Admin · VA Program</div>
          <h1 className="font-display text-4xl font-black tracking-tight flex items-center gap-2">
            <Lightbulb size={32} weight="duotone" /> Pitch templates
          </h1>
          <p className="mt-1 text-sm text-[#4B5563]">
            Templates VAs see in their library at <code>/va/templates</code>. Use {`{prospect_name}`} or {`{service_type}`} for client-side fill-in.
          </p>
        </div>
        <Button
          data-testid="template-new-btn"
          onClick={startNew}
          className="h-10 rounded-none bg-[#030712] text-white"
        >
          <Plus size={14} className="mr-1" weight="bold" /> New template
        </Button>
      </div>

      <label className="mb-4 inline-flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          data-testid="show-archived"
          checked={showArchived}
          onChange={(e) => setShowArchived(e.target.checked)}
          className="h-3 w-3 accent-[#0044FF]"
        />
        Show archived
      </label>

      {err && <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>}

      {items.length === 0 ? (
        <div className="border border-[#E5E7EB] bg-white p-8 text-center">
          <div className="font-mono-label text-[#9CA3AF]">No templates yet</div>
          <Button onClick={startNew} className="mt-3 h-9 rounded-none bg-[#030712] text-white">
            Create your first template
          </Button>
        </div>
      ) : (
        <div className="overflow-x-auto border border-[#E5E7EB] bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-[#F9FAFB] font-mono-label">
              <tr className="text-left">
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => (
                <tr
                  key={t.template_id}
                  data-testid={`template-row-${t.template_id}`}
                  className={`border-t border-[#E5E7EB] ${t.active ? "" : "opacity-50"}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-bold">{t.title}</div>
                    <div className="mt-1 truncate text-xs text-[#4B5563]" title={t.body}>
                      {t.body.slice(0, 100)}
                      {t.body.length > 100 ? "…" : ""}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs">{t.category || "—"}</td>
                  <td className="px-4 py-3 text-xs uppercase">{t.channel}</td>
                  <td className="px-4 py-3 text-xs">
                    {t.active ? (
                      <span className="text-[#10B981] font-bold">Active</span>
                    ) : (
                      <span className="text-[#9CA3AF]">Archived</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        data-testid={`template-edit-${t.template_id}`}
                        onClick={() => startEdit(t)}
                        title="Edit"
                        className="inline-flex items-center gap-1 border border-[#E5E7EB] bg-white px-2 py-1 text-xs hover:border-[#030712]"
                      >
                        <Pencil size={10} /> Edit
                      </button>
                      <button
                        data-testid={`template-archive-${t.template_id}`}
                        onClick={() => toggleArchive(t)}
                        title={t.active ? "Archive" : "Re-activate"}
                        className="inline-flex items-center gap-1 border border-[#E5E7EB] bg-white px-2 py-1 text-xs hover:border-[#030712]"
                      >
                        {t.active ? <Archive size={10} /> : <ArrowCounterClockwise size={10} />}
                        {t.active ? "Archive" : "Restore"}
                      </button>
                      <button
                        data-testid={`template-delete-${t.template_id}`}
                        onClick={() => remove(t)}
                        title="Delete permanently"
                        className="inline-flex items-center gap-1 border border-[#FCA5A5] bg-white px-2 py-1 text-xs text-[#DC2626] hover:bg-[#DC2626] hover:text-white"
                      >
                        <Trash size={10} /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="rounded-none border-[#030712]" data-testid="template-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-black">
              {editing === "new" ? "New template" : "Edit template"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <div className="font-mono-label mb-1">Title</div>
              <Input
                data-testid="template-form-title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="h-9 rounded-none border-[#030712]"
                placeholder="e.g. Cold outreach — DM"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="font-mono-label mb-1">Category</div>
                <Input
                  data-testid="template-form-category"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="h-9 rounded-none border-[#030712]"
                  placeholder="intro, follow-up…"
                />
              </div>
              <div>
                <div className="font-mono-label mb-1">Channel</div>
                <select
                  data-testid="template-form-channel"
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value })}
                  className="h-9 w-full border border-[#030712] bg-white px-2 text-sm"
                >
                  {CHANNELS.map((c) => (
                    <option key={c.v} value={c.v}>
                      {c.l}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <div className="font-mono-label mb-1">Body</div>
              <Textarea
                data-testid="template-form-body"
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                rows={8}
                className="rounded-none border-[#030712] font-mono text-xs"
                placeholder={"Hi {prospect_name}, I saw your post about cleaning…"}
              />
              <div className="mt-1 text-[10px] text-[#9CA3AF]">
                Tip: use {`{prospect_name}`} and {`{service_type}`} as placeholders. VAs replace these when sending.
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => setEditing(null)}
                className="h-10 rounded-none"
              >
                Cancel
              </Button>
              <Button
                data-testid="template-form-save"
                onClick={save}
                className="h-10 rounded-none bg-[#030712] text-white"
              >
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
