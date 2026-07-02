import React, { useEffect, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  SealCheck,
  Plus,
  Sparkle,
  Trash,
  PencilSimple,
  CheckCircle,
  XCircle,
  ArrowCounterClockwise,
  LinkSimple,
  FileArrowDown,
} from "@phosphor-icons/react";

const COLORS = ["#0044FF", "#0EA5E9", "#F59E0B", "#3B82F6", "#10B981", "#8B5CF6", "#EF4444", "#030712"];
const STATUS_TABS = [
  { value: "pending_review", label: "Pending review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "test_failed", label: "Failed tests" },
  { value: "test_passed", label: "Awaiting proof" },
  { value: "all", label: "All" },
];
const STATUS_CHIP = {
  pending_review: "bg-[#F59E0B]",
  approved: "bg-[#10B981]",
  rejected: "bg-[#EF4444]",
  test_failed: "bg-[#EF4444]",
  test_passed: "bg-[#0044FF]",
};

export default function AdminBadges() {
  const [tab, setTab] = useState("queue");
  const [badges, setBadges] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const loadBadges = async () => {
    try {
      const { data } = await api.get("/admin/badges");
      setBadges(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  useEffect(() => {
    loadBadges();
  }, []);

  const pendingTotal = badges.reduce((s, b) => s + (b.pending_review || 0), 0);

  return (
    <div className="p-6 md:p-10" data-testid="admin-badges-page">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono-label">Specialty workforce</div>
          <h1 className="font-display flex items-center gap-2 text-4xl font-black tracking-tight">
            <SealCheck size={30} weight="fill" className="text-[#0044FF]" /> Certifications
          </h1>
          <p className="mt-2 max-w-xl text-sm text-[#4B5563]">
            Workers pass a test and upload credentials — you review and approve.
            Certified pros unlock specialty assignments gated by these badges.
          </p>
        </div>
        <Button
          data-testid="new-badge-btn"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
          className="h-11 rounded-none bg-[#030712] px-5 font-bold text-white hover:bg-[#1f2937]"
        >
          <Plus size={16} weight="bold" className="mr-2" /> New certification
        </Button>
      </div>

      <div className="mb-6 flex gap-0 border-b-2 border-[#030712]">
        <button
          data-testid="badges-tab-queue"
          onClick={() => setTab("queue")}
          className={`px-5 py-2.5 text-sm font-bold ${tab === "queue" ? "bg-[#030712] text-white" : "text-[#4B5563] hover:text-[#030712]"}`}
        >
          Review queue{pendingTotal > 0 ? ` (${pendingTotal})` : ""}
        </button>
        <button
          data-testid="badges-tab-badges"
          onClick={() => setTab("badges")}
          className={`px-5 py-2.5 text-sm font-bold ${tab === "badges" ? "bg-[#030712] text-white" : "text-[#4B5563] hover:text-[#030712]"}`}
        >
          Badges ({badges.length})
        </button>
      </div>

      {tab === "queue" ? (
        <ReviewQueue onChanged={loadBadges} />
      ) : (
        <BadgesPanel
          badges={badges}
          onEdit={(b) => {
            setEditing(b);
            setDialogOpen(true);
          }}
          onChanged={loadBadges}
        />
      )}

      <BadgeDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        badge={editing}
        onSaved={() => {
          setDialogOpen(false);
          loadBadges();
        }}
      />
    </div>
  );
}

function ReviewQueue({ onChanged }) {
  const [status, setStatus] = useState("pending_review");
  const [apps, setApps] = useState(null);

  const load = async (s = status) => {
    try {
      const { data } = await api.get("/admin/badge-applications", { params: { status: s } });
      setApps(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  useEffect(() => {
    load(status);
    // eslint-disable-next-line
  }, [status]);

  const refresh = () => {
    load();
    onChanged();
  };

  return (
    <div data-testid="badge-review-queue">
      <div className="mb-4 flex flex-wrap gap-1.5">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            data-testid={`queue-filter-${t.value}`}
            onClick={() => setStatus(t.value)}
            className={`border px-3 py-1.5 text-xs font-bold ${
              status === t.value
                ? "border-[#030712] bg-[#030712] text-white"
                : "border-[#E5E7EB] text-[#4B5563] hover:border-[#030712]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {apps === null ? (
        <div className="border border-dashed border-[#9CA3AF] bg-white p-10 text-center text-sm text-[#4B5563]">Loading…</div>
      ) : apps.length === 0 ? (
        <div className="border border-dashed border-[#9CA3AF] bg-white p-10 text-center text-sm text-[#4B5563]" data-testid="queue-empty">
          Nothing here.
        </div>
      ) : (
        <div className="space-y-3">
          {apps.map((a) => (
            <ApplicationCard key={a.application_id} app={a} onChanged={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function ApplicationCard({ app, onChanged }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async (action) => {
    if (action === "reset" && !window.confirm("Reset this application? The worker can retake the test (an approved badge would be revoked).")) return;
    setBusy(true);
    try {
      await api.post(`/admin/badge-applications/${app.application_id}/${action}`, { note: note.trim() || null });
      toast.success(action === "approve" ? "Certified ✓" : action === "reject" ? "Rejected" : "Reset — worker can retake");
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const passed = app.status !== "test_failed";
  return (
    <div className="border-2 border-[#030712] bg-white p-5" data-testid={`badge-app-${app.application_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display text-lg font-bold">{app.worker_name || "Worker"}</span>
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-black tracking-widest text-white"
              style={{ backgroundColor: app.badge_color || "#0044FF" }}
            >
              <SealCheck size={10} weight="fill" /> {app.badge_name}
            </span>
            <span className={`px-2 py-0.5 text-[10px] font-black tracking-widest text-white ${STATUS_CHIP[app.status] || "bg-[#4B5563]"}`}>
              {app.status.replace("_", " ").toUpperCase()}
            </span>
          </div>
          <div className="mt-1 text-xs text-[#4B5563]">
            {app.worker_email} {app.worker_phone ? `· ${app.worker_phone}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className={`font-display text-2xl font-black ${passed ? "text-[#10B981]" : "text-[#EF4444]"}`} data-testid={`app-score-${app.application_id}`}>
            {app.score_pct}%
          </div>
          <div className="text-[10px] text-[#4B5563]">test score · pass {app.pass_pct || 80}%</div>
        </div>
      </div>

      {(app.documents?.length > 0 || app.portfolio_links?.length > 0 || app.notes) && (
        <div className="mt-3 space-y-2 border-t border-[#E5E7EB] pt-3">
          {app.documents?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {app.documents.map((d) => (
                <a
                  key={d.path}
                  href={`${API}/files/${d.path}`}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="app-doc-link"
                  className="inline-flex items-center gap-1 border border-[#030712] px-2.5 py-1 text-xs font-semibold hover:bg-[#030712] hover:text-white"
                >
                  <FileArrowDown size={12} /> {d.filename}
                </a>
              ))}
            </div>
          )}
          {app.portfolio_links?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {app.portfolio_links.map((l, i) => (
                <a key={i} href={l} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-[#0044FF] underline">
                  <LinkSimple size={12} /> {l.length > 45 ? l.slice(0, 45) + "…" : l}
                </a>
              ))}
            </div>
          )}
          {app.notes && <div className="text-xs text-[#4B5563]">“{app.notes}”</div>}
        </div>
      )}

      {app.admin_note && app.status !== "pending_review" && (
        <div className="mt-2 text-xs text-[#4B5563]">Review note: {app.admin_note}</div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {app.status === "pending_review" ? (
          <>
            <Input
              data-testid={`app-note-${app.application_id}`}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note to the worker…"
              className="h-9 w-full max-w-xs rounded-none border-[#030712] text-xs"
            />
            <Button
              data-testid={`app-approve-${app.application_id}`}
              onClick={() => act("approve")}
              disabled={busy}
              className="h-9 rounded-none bg-[#10B981] px-4 text-xs font-bold text-white hover:bg-[#0e9971]"
            >
              <CheckCircle size={14} weight="fill" className="mr-1" /> Approve — certify
            </Button>
            <Button
              data-testid={`app-reject-${app.application_id}`}
              onClick={() => act("reject")}
              disabled={busy}
              variant="outline"
              className="h-9 rounded-none border-[#EF4444] px-4 text-xs font-bold text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
            >
              <XCircle size={14} weight="fill" className="mr-1" /> Reject
            </Button>
          </>
        ) : (
          <Button
            data-testid={`app-reset-${app.application_id}`}
            onClick={() => act("reset")}
            disabled={busy}
            variant="outline"
            className="h-9 rounded-none border-[#030712] px-4 text-xs font-bold"
          >
            <ArrowCounterClockwise size={14} className="mr-1" /> Reset — allow retake
          </Button>
        )}
      </div>
    </div>
  );
}

function BadgesPanel({ badges, onEdit, onChanged }) {
  const toggleActive = async (b) => {
    try {
      await api.put(`/admin/badges/${b.badge_id}`, { active: !b.active });
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  const remove = async (b) => {
    if (!window.confirm(`Delete "${b.name}"? This revokes it from ${b.holders} certified worker(s) and removes it from any gigs that require it.`)) return;
    try {
      await api.delete(`/admin/badges/${b.badge_id}`);
      toast.success("Badge deleted");
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="badges-panel">
      {badges.map((b) => (
        <div key={b.badge_id} className="border-2 border-[#030712] bg-white p-5" data-testid={`badge-row-${b.badge_id}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center text-white" style={{ backgroundColor: b.color }}>
                <SealCheck size={20} weight="fill" />
              </div>
              <div>
                <div className="font-display text-lg font-bold leading-tight">{b.name}</div>
                <div className="mt-0.5 text-xs text-[#4B5563]">
                  {(b.questions || []).length} questions · pass {b.pass_pct}% · {b.holders} certified
                  {b.pending_review > 0 && <span className="ml-1 font-bold text-[#F59E0B]">· {b.pending_review} pending</span>}
                </div>
              </div>
            </div>
            <button
              data-testid={`badge-active-toggle-${b.badge_id}`}
              onClick={() => toggleActive(b)}
              className={`px-2 py-0.5 text-[10px] font-black tracking-widest text-white ${b.active ? "bg-[#10B981]" : "bg-[#9CA3AF]"}`}
            >
              {b.active ? "ACTIVE" : "HIDDEN"}
            </button>
          </div>
          {b.description && <p className="mt-2 text-xs text-[#4B5563]">{b.description}</p>}
          <div className="mt-3 flex gap-2">
            <Button data-testid={`badge-edit-${b.badge_id}`} onClick={() => onEdit(b)} variant="outline" className="h-8 rounded-none border-[#030712] px-3 text-xs font-bold">
              <PencilSimple size={13} className="mr-1" /> Edit
            </Button>
            <Button data-testid={`badge-delete-${b.badge_id}`} onClick={() => remove(b)} variant="outline" className="h-8 rounded-none border-[#EF4444] px-3 text-xs font-bold text-[#EF4444] hover:bg-[#EF4444] hover:text-white">
              <Trash size={13} className="mr-1" /> Delete
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

const BLANK_Q = () => ({ q: "", options: ["", "", "", ""], correct_index: 0 });

function BadgeDialog({ open, onOpenChange, badge, onSaved }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [passPct, setPassPct] = useState(80);
  const [questions, setQuestions] = useState([]);
  const [aiTopic, setAiTopic] = useState("");
  const [aiCount, setAiCount] = useState(8);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(badge?.name || "");
    setDescription(badge?.description || "");
    setColor(badge?.color || COLORS[0]);
    setPassPct(badge?.pass_pct ?? 80);
    setQuestions(badge?.questions ? JSON.parse(JSON.stringify(badge.questions)) : []);
    setAiTopic(badge?.name || "");
  }, [open, badge]);

  const setQ = (i, patch) =>
    setQuestions((qs) => qs.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));

  const generate = async () => {
    const topic = aiTopic.trim() || name.trim();
    if (!topic) return toast.error("Give the AI a topic (e.g. 'HVAC repair')");
    setGenerating(true);
    try {
      const { data } = await api.post("/admin/badges/generate-quiz", {
        topic,
        description: description.trim() || null,
        num_questions: parseInt(aiCount) || 8,
      });
      setQuestions((qs) => [...qs, ...data.questions]);
      toast.success(`Added ${data.questions.length} AI questions — review them below`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setGenerating(false);
    }
  };

  const save = async () => {
    if (!name.trim()) return toast.error("Name is required");
    if (questions.length === 0) return toast.error("Add at least one test question");
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        color,
        pass_pct: parseInt(passPct) || 80,
        questions,
      };
      if (badge) await api.put(`/admin/badges/${badge.badge_id}`, payload);
      else await api.post("/admin/badges", payload);
      toast.success(badge ? "Badge updated" : "Badge created");
      onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-3xl overflow-y-auto rounded-none border-2 border-[#030712]" data-testid="badge-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black">
            {badge ? "Edit certification" : "New certification"}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label className="font-mono-label">Name *</Label>
            <Input data-testid="badge-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Certified HVAC Tech" className="mt-1 h-10 rounded-none border-[#030712]" />
          </div>
          <div>
            <Label className="font-mono-label">Pass mark (%)</Label>
            <Input data-testid="badge-pass-input" type="number" min="1" max="100" value={passPct} onChange={(e) => setPassPct(e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Description</Label>
            <Textarea data-testid="badge-desc-input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this certification covers…" className="mt-1 rounded-none border-[#030712]" />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Badge color</Label>
            <div className="mt-2 flex gap-2">
              {COLORS.map((c) => (
                <button
                  key={c}
                  data-testid={`badge-color-${c.replace("#", "")}`}
                  onClick={() => setColor(c)}
                  className={`h-8 w-8 ${color === c ? "ring-2 ring-[#030712] ring-offset-2" : ""}`}
                  style={{ backgroundColor: c }}
                  type="button"
                />
              ))}
            </div>
          </div>
        </div>

        {/* AI generator */}
        <div className="border border-[#0044FF]/30 bg-[#F0F4FF] p-4">
          <div className="font-mono-label flex items-center gap-1.5 text-[#0044FF]">
            <Sparkle size={13} weight="fill" /> AI test writer
          </div>
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <div className="flex-1 min-w-[180px]">
              <Label className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">Topic</Label>
              <Input data-testid="ai-quiz-topic" value={aiTopic} onChange={(e) => setAiTopic(e.target.value)} placeholder="e.g. commercial plumbing" className="mt-1 h-9 rounded-none border-[#030712] bg-white text-sm" />
            </div>
            <div className="w-20">
              <Label className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]"># Qs</Label>
              <Input data-testid="ai-quiz-count" type="number" min="3" max="20" value={aiCount} onChange={(e) => setAiCount(e.target.value)} className="mt-1 h-9 rounded-none border-[#030712] bg-white text-sm" />
            </div>
            <Button data-testid="ai-quiz-generate-btn" onClick={generate} disabled={generating} type="button" className="h-9 rounded-none bg-[#0044FF] px-4 text-xs font-bold text-white hover:bg-[#0033CC]">
              <Sparkle size={13} weight="fill" className="mr-1" /> {generating ? "Writing questions…" : "Generate questions"}
            </Button>
          </div>
        </div>

        {/* Questions editor */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <Label className="font-mono-label">Test questions ({questions.length})</Label>
            <Button data-testid="add-question-btn" type="button" variant="outline" onClick={() => setQuestions((qs) => [...qs, BLANK_Q()])} className="h-8 rounded-none border-[#030712] px-3 text-xs font-bold">
              <Plus size={13} className="mr-1" /> Add question
            </Button>
          </div>
          <div className="space-y-3">
            {questions.map((q, qi) => (
              <div key={qi} className="border border-[#030712] p-3" data-testid={`question-editor-${qi}`}>
                <div className="flex items-start gap-2">
                  <span className="mt-2 font-mono-label text-[#4B5563]">{qi + 1}.</span>
                  <Textarea rows={1} value={q.q} onChange={(e) => setQ(qi, { q: e.target.value })} placeholder="Question text…" className="min-h-[38px] flex-1 rounded-none border-[#E5E7EB] text-sm" data-testid={`question-text-${qi}`} />
                  <button type="button" data-testid={`question-remove-${qi}`} onClick={() => setQuestions((qs) => qs.filter((_, i) => i !== qi))} className="mt-2 text-[#4B5563] hover:text-red-600">
                    <Trash size={15} />
                  </button>
                </div>
                <div className="mt-2 space-y-1.5 pl-6">
                  {q.options.map((opt, oi) => (
                    <div key={oi} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`correct-${qi}`}
                        checked={q.correct_index === oi}
                        onChange={() => setQ(qi, { correct_index: oi })}
                        className="h-4 w-4 accent-[#10B981]"
                        title="Mark as correct answer"
                        data-testid={`question-${qi}-correct-${oi}`}
                      />
                      <Input
                        value={opt}
                        onChange={(e) =>
                          setQ(qi, { options: q.options.map((o, i) => (i === oi ? e.target.value : o)) })
                        }
                        placeholder={`Option ${oi + 1}`}
                        className={`h-8 flex-1 rounded-none text-sm ${q.correct_index === oi ? "border-[#10B981] bg-[#ECFDF5]" : "border-[#E5E7EB]"}`}
                        data-testid={`question-${qi}-option-${oi}`}
                      />
                    </div>
                  ))}
                  <div className="text-[10px] text-[#4B5563]">Green radio = correct answer</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-[#E5E7EB] pt-4">
          <Button variant="outline" type="button" onClick={() => onOpenChange(false)} className="h-10 rounded-none border-[#030712]">
            Cancel
          </Button>
          <Button data-testid="badge-save-btn" onClick={save} disabled={saving} className="h-10 rounded-none bg-[#030712] px-6 font-bold text-white hover:bg-[#1f2937]">
            {saving ? "Saving…" : badge ? "Save changes" : "Create certification"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
