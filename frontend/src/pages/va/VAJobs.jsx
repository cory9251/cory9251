import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
import {
  Briefcase,
  Clock,
  CalendarBlank,
  ChatCircleDots,
  CheckCircle,
} from "@phosphor-icons/react";

const STATUS_META = {
  open: { label: "Open", cls: "bg-[#0044FF] text-white" },
  assigned: { label: "Assigned", cls: "bg-amber-500 text-white" },
  in_progress: { label: "In progress", cls: "bg-indigo-600 text-white" },
  submitted: { label: "In review", cls: "bg-violet-600 text-white" },
  approved: { label: "Approved ✓", cls: "bg-emerald-700 text-white" },
  cancelled: { label: "Cancelled", cls: "bg-[#9CA3AF] text-white" },
};

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.open;
  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${m.cls}`}>
      {m.label}
    </span>
  );
}

function payLabel(job) {
  return job.pay_type === "fixed"
    ? `$${Number(job.pay_amount).toFixed(2)} fixed`
    : `$${Number(job.pay_amount).toFixed(2)} / hr`;
}

function SubmitDialog({ job, open, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [hours, setHours] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setNote("");
      setHours("");
    }
  }, [open]);

  const payoutPreview =
    job?.pay_type === "hourly" && Number(hours) > 0
      ? (Number(job.pay_amount) * Number(hours)).toFixed(2)
      : job?.pay_type === "fixed"
        ? Number(job.pay_amount).toFixed(2)
        : null;

  const submit = async () => {
    if (!note.trim()) {
      toast.error("Add a delivery note (links, summary of the work)");
      return;
    }
    if (job.pay_type === "hourly" && !(Number(hours) > 0)) {
      toast.error("Log your hours");
      return;
    }
    setSaving(true);
    try {
      const payload = { note: note.trim() };
      if (job.pay_type === "hourly") payload.hours_logged = Number(hours);
      await api.post(`/va/jobs/${job.job_id}/submit`, payload);
      toast.success("Submitted for review");
      onDone();
      onClose();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  if (!job) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="submit-job-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black">
            Submit: {job.title}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Delivery note — links, files, what you did</Label>
            <Textarea
              data-testid="submit-job-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder="e.g. Landing page live at https://… — logo files in the shared drive."
            />
          </div>
          {job.pay_type === "hourly" && (
            <div>
              <Label>Hours worked</Label>
              <Input
                data-testid="submit-job-hours"
                type="number"
                min="0.5"
                step="0.5"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                placeholder="e.g. 4.5"
              />
            </div>
          )}
          {payoutPreview && (
            <div className="border border-emerald-300 bg-emerald-50 p-3 text-sm font-bold text-emerald-800">
              Payout on approval: ${payoutPreview}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-testid="submit-job-confirm"
            onClick={submit}
            disabled={saving}
            className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
          >
            {saving ? "Submitting…" : "Submit for review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function JobCard({ job, mine, onClaim, onStart, onSubmit }) {
  return (
    <div
      data-testid={`va-job-card-${job.job_id}`}
      className="border border-[#E5E7EB] bg-white p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="font-display text-base font-black">{job.title}</div>
        <div className="flex items-center gap-2">
          <span className="border border-[#0044FF] bg-[#F0F4FF] px-2 py-0.5 text-[11px] font-bold text-[#0044FF]">
            {payLabel(job)}
          </span>
          {mine && <StatusBadge status={job.status} />}
        </div>
      </div>
      {job.description && (
        <p className="mt-2 whitespace-pre-wrap text-sm text-[#4B5563]">{job.description}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-[#6B7280]">
        {job.due_date && (
          <span className="inline-flex items-center gap-1">
            <CalendarBlank size={13} /> Due {job.due_date}
          </span>
        )}
        {job.pay_type === "hourly" && job.hours_logged ? (
          <span className="inline-flex items-center gap-1">
            <Clock size={13} /> {job.hours_logged} hrs logged
          </span>
        ) : null}
      </div>

      {mine && job.status === "in_progress" && job.review_note && (
        <div className="mt-3 border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <span className="font-bold">Changes requested:</span> {job.review_note}
        </div>
      )}
      {mine && job.status === "approved" && (
        <div className="mt-3 flex items-center gap-2 border border-emerald-300 bg-emerald-50 p-3 text-sm font-bold text-emerald-800">
          <CheckCircle size={16} weight="fill" />
          ${Number(job.payout_amount).toFixed(2)} payout in the commission queue — track it in Earnings
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!mine && (
          <Button
            data-testid={`claim-job-${job.job_id}`}
            onClick={() => onClaim(job)}
            className="bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            Claim this job
          </Button>
        )}
        {mine && job.status === "assigned" && (
          <Button
            data-testid={`start-job-${job.job_id}`}
            onClick={() => onStart(job)}
            className="bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            Start working
          </Button>
        )}
        {mine && (job.status === "assigned" || job.status === "in_progress") && (
          <Button
            data-testid={`open-submit-${job.job_id}`}
            onClick={() => onSubmit(job)}
            className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
          >
            Submit work
          </Button>
        )}
        {mine && job.status === "submitted" && (
          <span className="text-sm font-semibold text-violet-700">
            Waiting for review — we'll notify you.
          </span>
        )}
        {mine && job.status !== "approved" && job.status !== "cancelled" && (
          <Link
            to="/va/messages"
            data-testid={`message-admin-${job.job_id}`}
            className="inline-flex items-center gap-1 text-sm font-semibold text-[#0044FF] underline"
          >
            <ChatCircleDots size={15} /> Message the team
          </Link>
        )}
      </div>
    </div>
  );
}

export default function VAJobs() {
  const [tab, setTab] = useState("board");
  const [board, setBoard] = useState(null);
  const [mine, setMine] = useState(null);
  const [submitJob, setSubmitJob] = useState(null);

  const load = async () => {
    try {
      const [b, m] = await Promise.all([
        api.get("/va/jobs/board"),
        api.get("/va/jobs/mine"),
      ]);
      setBoard(b.data.items || []);
      setMine(m.data.items || []);
    } catch (e) {
      toast.error(getErr(e));
      setBoard([]);
      setMine([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const claim = async (job) => {
    try {
      await api.post(`/va/jobs/${job.job_id}/claim`);
      toast.success("Job is yours — find it under My jobs");
      setTab("mine");
      load();
    } catch (e) {
      toast.error(getErr(e));
      load();
    }
  };

  const start = async (job) => {
    try {
      await api.post(`/va/jobs/${job.job_id}/start`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const activeMine = (mine || []).filter((j) => j.status !== "cancelled");

  return (
    <div className="p-6 md:p-10" data-testid="va-jobs-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <Briefcase size={14} weight="fill" /> DIGITAL JOBS
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        Jobs
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Paid digital work — claim a job from the board or get assigned directly.
        Approved payouts land in your Earnings alongside lead commissions.
      </p>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          data-testid="jobs-tab-board"
          onClick={() => setTab("board")}
          className={`px-4 py-2 text-sm font-bold ${
            tab === "board" ? "bg-[#030712] text-white" : "border border-[#E5E7EB] bg-white"
          }`}
        >
          Job board ({board?.length ?? "…"})
        </button>
        <button
          type="button"
          data-testid="jobs-tab-mine"
          onClick={() => setTab("mine")}
          className={`px-4 py-2 text-sm font-bold ${
            tab === "mine" ? "bg-[#030712] text-white" : "border border-[#E5E7EB] bg-white"
          }`}
        >
          My jobs ({activeMine.length})
        </button>
      </div>

      <div className="mt-6 space-y-3">
        {tab === "board" &&
          (board === null ? (
            <div className="text-sm text-[#4B5563]">Loading…</div>
          ) : board.length === 0 ? (
            <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
              No open jobs right now — check back soon or watch for a direct assignment.
            </div>
          ) : (
            board.map((j) => <JobCard key={j.job_id} job={j} mine={false} onClaim={claim} />)
          ))}
        {tab === "mine" &&
          (mine === null ? (
            <div className="text-sm text-[#4B5563]">Loading…</div>
          ) : activeMine.length === 0 ? (
            <div className="border border-dashed border-[#D1D5DB] p-10 text-center text-sm text-[#6B7280]">
              Nothing yet — claim a job from the board to get started.
            </div>
          ) : (
            activeMine.map((j) => (
              <JobCard
                key={j.job_id}
                job={j}
                mine
                onStart={start}
                onSubmit={(job) => setSubmitJob(job)}
              />
            ))
          ))}
      </div>

      <SubmitDialog
        job={submitJob}
        open={Boolean(submitJob)}
        onClose={() => setSubmitJob(null)}
        onDone={load}
      />
    </div>
  );
}
