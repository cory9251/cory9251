import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Megaphone, PaperPlaneTilt, Trash, Eye, EyeSlash } from "@phosphor-icons/react";

const AUDIENCES = [
  { value: "worker", label: "Workers" },
  { value: "va", label: "VAs" },
];
const CHANNELS = [
  { value: "in_app", label: "In-app" },
  { value: "email", label: "Email" },
  { value: "sms", label: "SMS" },
  { value: "push", label: "Push" },
];

const EMPTY = { title: "", body: "", audience: ["worker", "va"], popup: true, channels: ["in_app"] };

export default function AdminAnnouncements() {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [posting, setPosting] = useState(false);

  const load = () => {
    api.get("/admin/announcements").then((r) => setItems(r.data.items)).catch((e) => toast.error(getErr(e)));
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, []);

  const toggleIn = (key, value) =>
    setForm((f) => ({
      ...f,
      [key]: f[key].includes(value) ? f[key].filter((v) => v !== value) : [...f[key], value],
    }));

  const post = async (e) => {
    e.preventDefault();
    if (form.audience.length === 0) return toast.error("Pick at least one audience");
    if (form.channels.length === 0) return toast.error("Pick at least one channel");
    setPosting(true);
    try {
      const { data } = await api.post("/admin/announcements", form);
      toast.success(`Announcement posted to ${data.recipients} people (${data.in_app} in-app${data.blast_id ? " · email/SMS/push sending in background" : ""})`);
      setForm(EMPTY);
      load();
    } catch (er) {
      toast.error(getErr(er));
    } finally {
      setPosting(false);
    }
  };

  const toggleActive = async (a) => {
    try {
      await api.put(`/admin/announcements/${a.announcement_id}`, { active: !a.active });
      toast.success(a.active ? "Hidden from portals" : "Visible again");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const remove = async (a) => {
    if (!window.confirm(`Delete announcement "${a.title}"?`)) return;
    try {
      await api.delete(`/admin/announcements/${a.announcement_id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="p-6 md:p-10" data-testid="admin-announcements">
      <div className="mb-6">
        <div className="font-mono-label">Communication</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Announcements</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Post one centralized update — payment notices, schedule changes, cancellations — and every targeted
          worker/VA sees it on login (popup + board) and gets it via the channels you pick.
        </p>
      </div>

      {/* Compose */}
      <form onSubmit={post} className="mb-8 space-y-4 border-2 border-[#030712] bg-white p-6" data-testid="announcement-compose">
        <div className="font-mono-label flex items-center gap-2">
          <Megaphone size={14} weight="fill" /> New announcement
        </div>
        <div>
          <Label className="font-mono-label">Title *</Label>
          <Input
            data-testid="announcement-title-input"
            required
            maxLength={140}
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="mt-1 h-11 rounded-none border-[#030712]"
            placeholder="e.g. Payments go out Friday"
          />
        </div>
        <div>
          <Label className="font-mono-label">Message *</Label>
          <Textarea
            data-testid="announcement-body-input"
            required
            rows={4}
            maxLength={4000}
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            className="mt-1 rounded-none border-[#030712]"
            placeholder="Write the update once — everyone selected gets it."
          />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <Label className="font-mono-label">Audience *</Label>
            <div className="mt-2 space-y-1.5">
              {AUDIENCES.map((a) => (
                <label key={a.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    data-testid={`announcement-audience-${a.value}`}
                    checked={form.audience.includes(a.value)}
                    onChange={() => toggleIn("audience", a.value)}
                    className="h-4 w-4 accent-[#030712]"
                  />
                  {a.label}
                </label>
              ))}
            </div>
          </div>
          <div>
            <Label className="font-mono-label">Delivery channels *</Label>
            <div className="mt-2 grid grid-cols-2 gap-1.5">
              {CHANNELS.map((c) => (
                <label key={c.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    data-testid={`announcement-channel-${c.value}`}
                    checked={form.channels.includes(c.value)}
                    onChange={() => toggleIn("channels", c.value)}
                    className="h-4 w-4 accent-[#030712]"
                  />
                  {c.label}
                </label>
              ))}
            </div>
          </div>
          <div>
            <Label className="font-mono-label">Login popup</Label>
            <label className="mt-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                data-testid="announcement-popup-toggle"
                checked={form.popup}
                onChange={(e) => setForm({ ...form, popup: e.target.checked })}
                className="h-4 w-4 accent-[#030712]"
              />
              Show as popup when they log in
            </label>
            <p className="mt-1 text-[11px] text-[#9CA3AF]">Off = board-only (less intrusive)</p>
          </div>
        </div>
        <div className="flex justify-end">
          <Button
            data-testid="announcement-post-btn"
            type="submit"
            disabled={posting}
            className="h-11 rounded-none bg-[#030712] px-6 font-bold text-white hover:bg-[#1f2937]"
          >
            <PaperPlaneTilt size={16} weight="bold" className="mr-2" />
            {posting ? "Posting…" : "Post announcement"}
          </Button>
        </div>
      </form>

      {/* List */}
      {items === null ? (
        <div className="font-mono-label">Loading…</div>
      ) : items.length === 0 ? (
        <div className="border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]" data-testid="announcements-empty">
          No announcements yet. Post your first update above.
        </div>
      ) : (
        <div className="space-y-3" data-testid="announcements-admin-list">
          {items.map((a) => (
            <div
              key={a.announcement_id}
              data-testid={`announcement-admin-${a.announcement_id}`}
              className={`border bg-white p-4 ${a.active ? "border-[#E5E7EB]" : "border-dashed border-[#D1D5DB] opacity-60"}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-black">{a.title}</span>
                    {a.popup && (
                      <span className="bg-[#0044FF] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">popup</span>
                    )}
                    {!a.active && (
                      <span className="bg-[#9CA3AF] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">hidden</span>
                    )}
                    {(a.audience || []).map((aud) => (
                      <span key={aud} className="border border-[#030712] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest">
                        {aud === "va" ? "VAs" : "Workers"}
                      </span>
                    ))}
                  </div>
                  <p className="mt-1 line-clamp-2 whitespace-pre-line text-sm text-[#4B5563]">{a.body}</p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#9CA3AF]">
                    <span>{new Date(a.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    <span>by {a.created_by_name || "—"}</span>
                    <span data-testid={`announcement-read-count-${a.announcement_id}`} className="font-semibold text-[#4B5563]">
                      {a.read_count}/{a.recipients} read
                    </span>
                    <span>
                      Delivery: {a.delivery?.in_app || 0} in-app
                      {a.channels?.includes("email") ? ` · ${a.delivery?.email || 0} email` : ""}
                      {a.channels?.includes("sms") ? ` · ${a.delivery?.sms || 0} SMS` : ""}
                      {a.channels?.includes("push") ? ` · ${a.delivery?.push || 0} push` : ""}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    data-testid={`announcement-toggle-active-${a.announcement_id}`}
                    onClick={() => toggleActive(a)}
                    title={a.active ? "Hide from portals" : "Show again"}
                    className="grid h-8 w-8 place-items-center border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
                  >
                    {a.active ? <EyeSlash size={14} /> : <Eye size={14} />}
                  </button>
                  <button
                    data-testid={`announcement-delete-${a.announcement_id}`}
                    onClick={() => remove(a)}
                    className="grid h-8 w-8 place-items-center border border-[#E5E7EB] text-[#4B5563] hover:border-red-600 hover:text-red-600"
                  >
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
