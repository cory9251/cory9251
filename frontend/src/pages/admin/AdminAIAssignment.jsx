import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Sparkle, UploadSimple, X, ArrowLeft, PaperPlaneTilt, CheckCircle, WarningCircle, Megaphone } from "@phosphor-icons/react";

const MODELS = [
  { value: "gpt-5.5", label: "GPT-5.5" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
];
const CHANNELS = ["in_app", "email", "sms", "push"];

const buildFromLocal = (local) => {
  if (!local) return { iso: null, display: null };
  const d = new Date(local);
  if (isNaN(d)) return { iso: null, display: null };
  const display =
    d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) +
    " · " +
    d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return { iso: d.toISOString(), display };
};

export default function AdminAIAssignment() {
  const nav = useNavigate();
  const fileRef = useRef(null);
  const [step, setStep] = useState("input"); // input | review | done
  const [text, setText] = useState("");
  const [model, setModel] = useState("gpt-5.5");
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createdGig, setCreatedGig] = useState(null);
  const [blastOpen, setBlastOpen] = useState(false);
  const [blastChannels, setBlastChannels] = useState(["in_app", "push"]);
  const [blasting, setBlasting] = useState(false);

  const generate = async () => {
    if (!text.trim() && !file) return toast.error("Type some details or upload a document");
    setParsing(true);
    try {
      const fd = new FormData();
      if (text.trim()) fd.append("text", text.trim());
      fd.append("model", model);
      if (file) fd.append("file", file);
      const { data } = await api.post("/admin/ai-assignments/parse", fd);
      setDraft(data.draft);
      setStep("review");
      toast.success("Draft ready — review and tweak before creating");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setParsing(false);
    }
  };

  const setD = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const createGig = async () => {
    if (!draft.title?.trim()) return toast.error("Title is required");
    if (!draft.description?.trim()) return toast.error("Description is required");
    if (!draft.location?.trim()) return toast.error("Public location is required");
    if (!draft.scheduled_local) return toast.error("Pick the date & time");
    if (!draft.pay_rate) return toast.error("Set the pay rate");
    const { iso, display } = buildFromLocal(draft.scheduled_local);
    if (!iso) return toast.error("Invalid date/time");
    setCreating(true);
    try {
      const { data } = await api.post("/gigs", {
        title: draft.title.trim(),
        description: draft.description.trim(),
        category: draft.category,
        location: draft.location.trim(),
        address_line: draft.address_line?.trim() || null,
        scheduled_date: display,
        scheduled_at: iso,
        scheduled_local: draft.scheduled_local,
        pay_rate: parseFloat(draft.pay_rate),
        pay_type: draft.pay_type,
        slots: parseInt(draft.slots || 1),
        duration_hours: draft.duration_hours ? parseFloat(draft.duration_hours) : null,
        contact_phone: draft.contact_phone?.trim() || null,
        recurrence: "none",
        repeat_count: 1,
      });
      setCreatedGig(data);
      setStep("done");
      setBlastOpen(true);
      toast.success("Assignment created");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setCreating(false);
    }
  };

  const blast = async () => {
    setBlasting(true);
    try {
      await api.post(`/gigs/${createdGig.gig_id}/blast`, { channels: blastChannels });
      toast.success("Blasted to workers 🚀");
      setBlastOpen(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBlasting(false);
    }
  };

  const reset = () => {
    setStep("input");
    setText("");
    setFile(null);
    setDraft(null);
    setCreatedGig(null);
  };

  return (
    <div className="p-6 md:p-10 max-w-3xl" data-testid="admin-ai-assignment">
      <div className="mb-6">
        <div className="font-mono-label">AI powered</div>
        <h1 className="font-display flex items-center gap-2 text-4xl font-black tracking-tight">
          <Sparkle size={30} weight="fill" className="text-[#0044FF]" /> AI Assignment Maker
        </h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Describe the job or drop in a work order (PDF, Word, photo) — the AI drafts the assignment,
          you review, create, and blast it out.
        </p>
      </div>

      {step === "input" && (
        <section className="space-y-4 border-2 border-[#030712] bg-white p-6" data-testid="ai-input-step">
          <div>
            <Label className="font-mono-label">Tell it the details</Label>
            <Textarea
              data-testid="ai-text-input"
              rows={5}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="mt-2 rounded-none border-[#030712]"
              placeholder={'e.g. "Deep clean for a dental office at 450 Light St, Baltimore this Friday 9am. Need 3 cleaners, $22/hr, roughly 5 hours. Bring PPE."'}
            />
          </div>

          <div>
            <Label className="font-mono-label">…and/or upload a document</Label>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,image/*"
              className="hidden"
              data-testid="ai-file-input"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file ? (
              <div className="mt-2 flex items-center justify-between border border-[#0044FF] bg-[#F0F4FF] px-3 py-2 text-sm" data-testid="ai-file-chip">
                <span className="truncate font-semibold">{file.name}</span>
                <button data-testid="ai-file-remove" onClick={() => setFile(null)} className="ml-2 text-[#4B5563] hover:text-red-600">
                  <X size={14} />
                </button>
              </div>
            ) : (
              <button
                data-testid="ai-file-browse"
                type="button"
                onClick={() => fileRef.current?.click()}
                className="mt-2 flex w-full items-center justify-center gap-2 border border-dashed border-[#9CA3AF] bg-[#F9FAFB] px-4 py-6 text-sm text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
              >
                <UploadSimple size={18} /> PDF · Word (.docx) · photo/screenshot of a work order
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Label className="font-mono-label">AI model</Label>
              <select
                data-testid="ai-model-select"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="mt-2 h-10 border border-[#030712] bg-white px-2 text-sm"
              >
                {MODELS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
            <Button
              data-testid="ai-generate-btn"
              onClick={generate}
              disabled={parsing}
              className="h-11 rounded-none bg-[#0044FF] px-6 font-bold text-white hover:bg-[#0033CC]"
            >
              <Sparkle size={16} weight="fill" className="mr-2" />
              {parsing ? "Reading your details…" : "Generate draft"}
            </Button>
          </div>
        </section>
      )}

      {step === "review" && draft && (
        <section className="space-y-4 border-2 border-[#030712] bg-white p-6" data-testid="ai-review-step">
          <div className="flex items-center justify-between">
            <div className="font-mono-label flex items-center gap-2">
              <CheckCircle size={14} weight="fill" className="text-emerald-600" /> AI draft — review &amp; tweak
            </div>
            <button data-testid="ai-back-btn" onClick={() => setStep("input")} className="inline-flex items-center gap-1 text-xs font-semibold text-[#4B5563] hover:text-[#030712]">
              <ArrowLeft size={12} /> Back
            </button>
          </div>

          {draft.ai_notes && (
            <div className="border border-[#BFDBFE] bg-[#EFF6FF] p-3 text-xs text-[#1D4ED8]" data-testid="ai-notes">
              <strong>AI:</strong> {draft.ai_notes}
            </div>
          )}
          {draft.missing_fields?.length > 0 && (
            <div className="flex items-start gap-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900" data-testid="ai-missing-fields">
              <WarningCircle size={16} className="mt-0.5 shrink-0" />
              <span>Couldn't find: <strong>{draft.missing_fields.join(", ").replace(/_/g, " ")}</strong> — fill these in below.</span>
            </div>
          )}

          <div>
            <Label className="font-mono-label">Title *</Label>
            <Input data-testid="ai-draft-title" value={draft.title || ""} onChange={(e) => setD("title", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
          </div>
          <div>
            <Label className="font-mono-label">Description *</Label>
            <Textarea data-testid="ai-draft-description" rows={5} value={draft.description || ""} onChange={(e) => setD("description", e.target.value)} className="mt-1 rounded-none border-[#030712]" />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <div>
              <Label className="font-mono-label">Category *</Label>
              <select data-testid="ai-draft-category" value={draft.category} onChange={(e) => setD("category", e.target.value)} className="mt-1 h-10 w-full border border-[#030712] bg-white px-2 text-sm">
                <option value="cleaning">Cleaning</option>
                <option value="labor">Labor</option>
                <option value="driver">Driver</option>
              </select>
            </div>
            <div>
              <Label className="font-mono-label">Public location *</Label>
              <Input data-testid="ai-draft-location" value={draft.location || ""} onChange={(e) => setD("location", e.target.value)} placeholder="Downtown · 21201" className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Full address</Label>
              <Input data-testid="ai-draft-address" value={draft.address_line || ""} onChange={(e) => setD("address_line", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Date &amp; time *</Label>
              <Input data-testid="ai-draft-datetime" type="datetime-local" value={draft.scheduled_local || ""} onChange={(e) => setD("scheduled_local", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Pay rate ($) *</Label>
              <Input data-testid="ai-draft-pay-rate" type="number" min="0" step="0.5" value={draft.pay_rate ?? ""} onChange={(e) => setD("pay_rate", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Pay type</Label>
              <select data-testid="ai-draft-pay-type" value={draft.pay_type} onChange={(e) => setD("pay_type", e.target.value)} className="mt-1 h-10 w-full border border-[#030712] bg-white px-2 text-sm">
                <option value="hourly">Hourly</option>
                <option value="flat">Flat</option>
              </select>
            </div>
            <div>
              <Label className="font-mono-label">Workers needed</Label>
              <Input data-testid="ai-draft-slots" type="number" min="1" value={draft.slots || 1} onChange={(e) => setD("slots", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Duration (hrs)</Label>
              <Input data-testid="ai-draft-duration" type="number" min="0" step="0.5" value={draft.duration_hours ?? ""} onChange={(e) => setD("duration_hours", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
            <div>
              <Label className="font-mono-label">Contact phone</Label>
              <Input data-testid="ai-draft-phone" value={draft.contact_phone || ""} onChange={(e) => setD("contact_phone", e.target.value)} className="mt-1 h-10 rounded-none border-[#030712]" />
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <Button
              data-testid="ai-create-btn"
              onClick={createGig}
              disabled={creating}
              className="h-11 rounded-none bg-[#030712] px-6 font-bold text-white hover:bg-[#1f2937]"
            >
              <PaperPlaneTilt size={16} weight="bold" className="mr-2" />
              {creating ? "Creating…" : "Create assignment"}
            </Button>
          </div>
        </section>
      )}

      {step === "done" && createdGig && (
        <section className="border-2 border-emerald-600 bg-white p-8 text-center" data-testid="ai-done-step">
          <CheckCircle size={40} weight="fill" className="mx-auto text-emerald-600" />
          <h2 className="font-display mt-3 text-2xl font-black">Assignment created</h2>
          <p className="mt-1 text-sm text-[#4B5563]">&ldquo;{createdGig.title}&rdquo; is live.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Button data-testid="ai-view-gig-btn" onClick={() => nav(`/ops/assignments/${createdGig.gig_id}`)} className="h-10 rounded-none bg-[#030712] text-white">
              View assignment
            </Button>
            <Button data-testid="ai-blast-again-btn" variant="outline" onClick={() => setBlastOpen(true)} className="h-10 rounded-none border-[#030712]">
              <Megaphone size={14} className="mr-1" /> Blast it
            </Button>
            <Button data-testid="ai-create-another-btn" variant="outline" onClick={reset} className="h-10 rounded-none border-[#030712]">
              <Sparkle size={14} className="mr-1" /> Create another
            </Button>
          </div>
        </section>
      )}

      {/* Blast prompt */}
      <Dialog open={blastOpen} onOpenChange={setBlastOpen}>
        <DialogContent className="max-w-sm rounded-none border-2 border-[#030712]" data-testid="ai-blast-dialog">
          <DialogHeader>
            <DialogTitle className="font-display font-black">Blast it to workers now?</DialogTitle>
            <DialogDescription className="text-xs text-[#4B5563]">
              Notify available workers about this new assignment right away.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-1.5">
            {CHANNELS.map((c) => (
              <label key={c} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  data-testid={`ai-blast-channel-${c}`}
                  checked={blastChannels.includes(c)}
                  onChange={() =>
                    setBlastChannels((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]))
                  }
                  className="h-4 w-4 accent-[#030712]"
                />
                {c === "in_app" ? "In-app" : c.toUpperCase() === "SMS" ? "SMS" : c.charAt(0).toUpperCase() + c.slice(1)}
              </label>
            ))}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button data-testid="ai-blast-skip" variant="outline" onClick={() => setBlastOpen(false)} className="h-10 rounded-none border-[#030712]">
              Not now
            </Button>
            <Button data-testid="ai-blast-send" onClick={blast} disabled={blasting || blastChannels.length === 0} className="h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0033CC]">
              <Megaphone size={14} className="mr-1" /> {blasting ? "Blasting…" : "Blast now"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
