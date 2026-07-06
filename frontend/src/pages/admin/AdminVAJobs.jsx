import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Briefcase, Plus, PencilSimple } from "@phosphor-icons/react";

const STATUS_META = {
  open: { label: "Open", cls: "bg-[#0044FF] text-white" },
  assigned: { label: "Assigned", cls: "bg-amber-500 text-white" },
  in_progress: { label: "In progress", cls: "bg-indigo-600 text-white" },
  submitted: { label: "Needs review", cls: "bg-violet-600 text-white" },
  approved: { label: "Approved ✓", cls: "bg-emerald-700 text-white" },
  cancelled: { label: "Cancelled", cls: "bg-[#9CA3AF] text-white" },
};
const FILTERS = ["", "open", "assigned", "in_progress", "submitted", "approved", "cancelled"];

function payLabel(job) {
  return job.pay_type === "fixed"
    ? `$${Number(job.pay_amount).toFixed(2)} fixed`
    : `$${Number(job.pay_amount).toFixed(2)} / hr`;
}

const EMPTY_FORM = {
  title: "",
  description: "",
  pay_type: "fixed",
  pay_amount: "",
  due_date: "",
  assigned_va_id: "",
};

function JobDialog({ open, onClose, initial, vas, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const editing = Boolean(initial?.job_id);

  useEffect(() => {
    if (open)
      setForm(
        initial
          ? {
              title: initial.title,
              description: initial.description || "",
              pay_type: initial.pay_type,
              pay_amount: String(initial.pay_amount),
              due_date: initial.due_date || "",
              assigned_va_id: "",
            }
          : EMPTY_FORM
      );
  }, [open, initial]);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.title.trim() || !(Number(form.pay_amount) > 0)) {
      toast.error("Title and a pay amount are required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description || "",
        pay_type: form.pay_type,
        pay_amount: Number(form.pay_amount),
        due_date: form.due_date || null,
        assigned_va_id: editing ? null : form.assigned_va_id || null,
      };
      if (editing) {
        await api.put(`/admin/va-jobs/${initial.job_id}`, payload);
      } else {
        await api.post("/admin/va-jobs", payload);
      }
      toast.success(editing ? "Job updated" : form.assigned_va_id ? "Job assigned" : "Job posted to the board");
      onSaved();
      onClose();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="job-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black">
            {editing ? "Edit job" : "Post a digital job"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Title</Label>
            <Input
              data-testid="job-form-title"
              value={form.title}
              onChange={(e) => upd("title", e.target.value)}
              placeholder="e.g. Build a landing page for Smith Roofing"
            />
          </div>
          <div>
            <Label>Description / scope</Label>
            <Textarea
              data-testid="job-form-description"
              value={form.description}
              onChange={(e) => upd("description", e.target.value)}
              rows={3}
              placeholder="Deliverables, links, expectations…"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>Pay type</Label>
              <select
                data-testid="job-form-pay-type"
                value={form.pay_type}
                onChange={(e) => upd("pay_type", e.target.value)}
                className="h-10 w-full border border-input bg-white px-3 text-sm"
              >
                <option value="fixed">Fixed price</option>
                <option value="hourly">Hourly</option>
              </select>
            </div>
            <div>
              <Label>{form.pay_type === "fixed" ? "Price ($)" : "Rate ($/hr)"}</Label>
              <Input
                data-testid="job-form-pay-amount"
                type="number"
                min="1"
                value={form.pay_amount}
                onChange={(e) => upd("pay_amount", e.target.value)}
                placeholder="150"
              />
            </div>
            <div>
              <Label>Due date</Label>
              <Input
                data-testid="job-form-due-date"
                type="date"
                value={form.due_date}
                onChange={(e) => upd("due_date", e.target.value)}
              />
            </div>
          </div>
          {!editing && (
            <div>
              <Label>Assign to a VA (or leave open on the board)</Label>
              <select
                data-testid="job-form-assign-va"
                value={form.assigned_va_id}
                onChange={(e) => upd("assigned_va_id", e.target.value)}
                className="h-10 w-full border border-input bg-white px-3 text-sm"
              >
                <option value="">Open — any approved VA can claim</option>
                {vas.map((v) => (
                  <option key={v.user_id} value={v.user_id}>
                    {v.name || v.email}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-testid="job-form-save"
            onClick={save}
            disabled={saving}
            className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
          >
            {saving ? "Saving…" : editing ? "Save changes" : "Create job"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function JobRow({ job, vas, onChanged, onEdit }) {
  const meta = STATUS_META[job.status] || STATUS_META.open;
  const [assigning, setAssigning] = useState(false);
  const [reviewNote, setReviewNote] = useState("");

  const doAction = async (path, body = {}) => {
    try {
      await api.post(`/admin/va-jobs/${job.job_id}/${path}`, body);
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const approve = async () => {
    const payout =
      job.pay_type === "fixed"
        ? Number(job.pay_amount)
        : Number(job.pay_amount) * Number(job.hours_logged || 0);
    if (
      !window.confirm(
        `Approve "${job.title}"?\nPayout of $${payout.toFixed(2)} for ${job.assigned_va_name} will enter the commission queue.`
      )
    )
      return;
    await doAction("approve", { note: reviewNote || null });
    toast.success("Approved — payout is in the commission queue");
  };

  const sendBack = async () => {
    const note = window.prompt("What needs fixing? (sent to the VA)");
    if (!note || !note.trim()) return;
    await doAction("reject", { note: note.trim() });
    toast.success("Sent back to the VA");
  };

  return (
    <div
      data-testid={`admin-job-row-${job.job_id}`}
      className="border border-[#E5E7EB] bg-white p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display text-sm font-black">{job.title}</span>
            <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${meta.cls}`}>
              {meta.label}
            </span>
            <span className="border border-[#0044FF] bg-[#F0F4FF] px-1.5 py-0.5 text-[10px] font-bold text-[#0044FF]">
              {payLabel(job)}
            </span>
          </div>
          <div className="mt-1 text-xs text-[#6B7280]">
            {job.assigned_va_name ? `VA: ${job.assigned_va_name}` : "Unassigned — on the board"}
            {job.due_date ? ` · Due ${job.due_date}` : ""}
            {job.pay_type === "hourly" && job.hours_logged ? ` · ${job.hours_logged} hrs logged` : ""}
            {job.status === "approved" && job.payout_amount != null
              ? ` · Payout $${Number(job.payout_amount).toFixed(2)}`
              : ""}
          </div>
          {job.status === "submitted" && job.deliverable_note && (
            <div className="mt-2 border border-violet-300 bg-violet-50 p-3 text-sm text-violet-900">
              <span className="font-bold">Delivery note:</span>{" "}
              <span className="whitespace-pre-wrap">{job.deliverable_note}</span>
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {job.status === "submitted" && (
            <>
              <Button
                data-testid={`approve-job-${job.job_id}`}
                onClick={approve}
                size="sm"
                className="bg-emerald-700 text-white hover:bg-emerald-800"
              >
                Approve &amp; queue payout
              </Button>
              <Button
                data-testid={`reject-job-${job.job_id}`}
                onClick={sendBack}
                size="sm"
                variant="outline"
              >
                Send back
              </Button>
            </>
          )}
          {["open", "assigned", "in_progress"].includes(job.status) && (
            <>
              {assigning ? (
                <select
                  data-testid={`assign-select-${job.job_id}`}
                  className="h-9 border border-input bg-white px-2 text-sm"
                  defaultValue=""
                  onChange={async (e) => {
                    await doAction("assign", { va_user_id: e.target.value || null });
                    setAssigning(false);
                  }}
                >
                  <option value="" disabled>
                    Pick a VA…
                  </option>
                  <option value="">← Back to open board</option>
                  {vas.map((v) => (
                    <option key={v.user_id} value={v.user_id}>
                      {v.name || v.email}
                    </option>
                  ))}
                </select>
              ) : (
                <Button
                  data-testid={`assign-job-${job.job_id}`}
                  onClick={() => setAssigning(true)}
                  size="sm"
                  variant="outline"
                >
                  {job.assigned_va_id ? "Reassign" : "Assign"}
                </Button>
              )}
              <Button
                data-testid={`edit-job-${job.job_id}`}
                onClick={() => onEdit(job)}
                size="sm"
                variant="outline"
              >
                <PencilSimple size={14} />
              </Button>
              <Button
                data-testid={`cancel-job-${job.job_id}`}
                onClick={async () => {
                  if (window.confirm(`Cancel "${job.title}"?`)) await doAction("cancel");
                }}
                size="sm"
                variant="outline"
                className="text-red-600"
              >
                Cancel
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AdminVAJobs() {
  const [items, setItems] = useState(null);
  const [counts, setCounts] = useState({});
  const [filter, setFilter] = useState("");
  const [vas, setVas] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get(`/admin/va-jobs${filter ? `?status=${filter}` : ""}`);
      setItems(data.items || []);
      setCounts(data.counts || {});
    } catch (e) {
      toast.error(getErr(e));
      setItems([]);
    }
  };

  useEffect(() => {
    load(); // eslint-disable-line
  }, [filter]);

  useEffect(() => {
    api
      .get("/pm/vas")
      .then((r) =>
        setVas((r.data.items || []).filter((v) => (v.va_status || "pending") === "approved"))
      )
      .catch(() => setVas([]));
  }, []);

  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="mx-auto max-w-5xl" data-testid="admin-va-jobs-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
            <Briefcase size={14} weight="fill" /> VA PROGRAM · DIGITAL JOBS
          </div>
          <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
            Digital jobs
          </h1>
          <p className="mt-2 max-w-xl text-sm text-[#4B5563]">
            Post paid digital work to the VA board or assign it directly. Approve
            submitted work and the payout drops into the commission queue.
          </p>
        </div>
        <Button
          data-testid="post-job-btn"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
          className="bg-[#030712] text-white hover:bg-[#1f2937]"
        >
          <Plus size={16} className="mr-1" /> Post job
        </Button>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f || "all"}
            type="button"
            data-testid={`job-filter-${f || "all"}`}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 text-xs font-bold uppercase tracking-widest ${
              filter === f ? "bg-[#030712] text-white" : "border border-[#E5E7EB] bg-white"
            }`}
          >
            {f ? `${STATUS_META[f].label} (${counts[f] || 0})` : `All (${total})`}
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-2">
        {items === null ? (
          <div className="text-sm text-[#4B5563]">Loading…</div>
        ) : items.length === 0 ? (
          <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
            No jobs here yet. Post one to the board or assign a VA directly.
          </div>
        ) : (
          items.map((j) => (
            <JobRow
              key={j.job_id}
              job={j}
              vas={vas}
              onChanged={load}
              onEdit={(job) => {
                setEditing(job);
                setDialogOpen(true);
              }}
            />
          ))
        )}
      </div>

      <JobDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        initial={editing}
        vas={vas}
        onSaved={load}
      />
    </div>
  );
}
