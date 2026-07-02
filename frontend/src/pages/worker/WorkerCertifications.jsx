import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  SealCheck,
  ArrowLeft,
  UploadSimple,
  X,
  CheckCircle,
  XCircle,
  HourglassMedium,
  Exam,
} from "@phosphor-icons/react";

export default function WorkerCertifications() {
  const [badges, setBadges] = useState(null);
  const [testBadge, setTestBadge] = useState(null); // badge currently being tested

  const load = async () => {
    try {
      const { data } = await api.get("/worker/badges");
      setBadges(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };
  useEffect(() => {
    load();
  }, []);

  if (testBadge) {
    return (
      <TestScreen
        badge={testBadge}
        onExit={() => {
          setTestBadge(null);
          load();
        }}
      />
    );
  }

  return (
    <div className="px-5 py-6 pb-28" data-testid="worker-certifications">
      <div className="font-mono-label">Specialty access</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        Professional Certifications
      </h1>
      <p className="mt-2 text-sm text-[#4B5563]">
        Pass the test, upload proof of your skills (certifications, portfolio,
        photos of your work), and HCOB will review. Certified pros get first
        access to specialty assignments.
      </p>

      <div className="mt-5 space-y-4">
        {badges === null ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            Loading…
          </div>
        ) : badges.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            No certifications available yet — check back soon.
          </div>
        ) : (
          badges.map((b) => (
            <BadgeCard key={b.badge_id} badge={b} onTakeTest={() => setTestBadge(b)} onChanged={load} />
          ))
        )}
      </div>
    </div>
  );
}

function StatusChip({ badge }) {
  const app = badge.application;
  if (badge.certified)
    return (
      <span data-testid={`badge-status-${badge.badge_id}`} className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
        <CheckCircle size={10} weight="fill" /> CERTIFIED
      </span>
    );
  if (!app) return null;
  if (app.status === "pending_review")
    return (
      <span data-testid={`badge-status-${badge.badge_id}`} className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
        <HourglassMedium size={10} weight="fill" /> IN REVIEW
      </span>
    );
  if (app.status === "test_passed")
    return (
      <span data-testid={`badge-status-${badge.badge_id}`} className="inline-flex items-center gap-1 rounded-full bg-[#0044FF] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
        TEST PASSED · {app.score_pct}%
      </span>
    );
  if (app.status === "test_failed")
    return (
      <span data-testid={`badge-status-${badge.badge_id}`} className="inline-flex items-center gap-1 rounded-full bg-[#EF4444] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
        <XCircle size={10} weight="fill" /> FAILED · {app.score_pct}%
      </span>
    );
  if (app.status === "rejected")
    return (
      <span data-testid={`badge-status-${badge.badge_id}`} className="inline-flex items-center gap-1 rounded-full bg-[#EF4444] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
        <XCircle size={10} weight="fill" /> NOT APPROVED
      </span>
    );
  return null;
}

function BadgeCard({ badge, onTakeTest, onChanged }) {
  const app = badge.application;
  return (
    <div
      data-testid={`badge-card-${badge.badge_id}`}
      className="gb-tactile rounded-2xl border border-black/5 bg-white p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white"
            style={{ backgroundColor: badge.color }}
          >
            <SealCheck size={22} weight="fill" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold leading-snug">{badge.name}</h3>
            {badge.description && (
              <p className="mt-1 text-xs text-[#4B5563]">{badge.description}</p>
            )}
          </div>
        </div>
        <StatusChip badge={badge} />
      </div>

      {badge.certified ? (
        <div className="mt-4 rounded-xl border border-[#10B981]/30 bg-[#ECFDF5] p-3 text-xs text-[#065F46]">
          You're certified — you get first access to {badge.name} assignments.
        </div>
      ) : !app ? (
        <Button
          data-testid={`take-test-btn-${badge.badge_id}`}
          onClick={onTakeTest}
          className="mt-4 h-11 w-full rounded-2xl bg-[#030712] text-sm font-bold text-white"
        >
          <Exam size={16} weight="fill" className="mr-2" />
          Take the test · {badge.question_count} questions · pass at {badge.pass_pct}%
        </Button>
      ) : app.status === "test_failed" ? (
        <div className="mt-4 rounded-xl border border-[#EF4444]/30 bg-[#FEF2F2] p-3 text-xs text-[#991B1B]">
          You scored {app.score_pct}% — {badge.pass_pct}% needed. Retakes require
          HCOB approval; contact HCOB if you'd like another shot.
        </div>
      ) : app.status === "rejected" ? (
        <div className="mt-4 rounded-xl border border-[#EF4444]/30 bg-[#FEF2F2] p-3 text-xs text-[#991B1B]">
          {app.admin_note || "HCOB reviewed your application and it wasn't approved this time."}
        </div>
      ) : app.status === "pending_review" ? (
        <div className="mt-4 rounded-xl border border-[#F59E0B]/30 bg-[#FFFBEB] p-3 text-xs text-[#92400E]">
          Your test score ({app.score_pct}%) and credentials are with HCOB for
          internal review. You'll get a notification with the decision.
        </div>
      ) : app.status === "test_passed" ? (
        <ProofPanel badge={badge} app={app} onChanged={onChanged} />
      ) : null}
    </div>
  );
}

function ProofPanel({ badge, app, onChanged }) {
  const fileRef = React.useRef(null);
  const [docs, setDocs] = useState(app.documents || []);
  const [links, setLinks] = useState((app.portfolio_links || []).join("\n"));
  const [notes, setNotes] = useState(app.notes || "");
  const [busy, setBusy] = useState(false);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/worker/badges/${badge.badge_id}/documents`, fd);
      setDocs(data.documents);
      toast.success("Document added");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeDoc = async (path) => {
    try {
      await api.delete(`/worker/badges/${badge.badge_id}/documents`, { params: { path } });
      setDocs((d) => d.filter((x) => x.path !== path));
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/worker/badges/${badge.badge_id}/submit`, {
        portfolio_links: links.split("\n").map((l) => l.trim()).filter(Boolean),
        notes: notes.trim() || null,
      });
      toast.success("Submitted — HCOB will review and get back to you");
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 space-y-3 rounded-xl border border-[#0044FF]/20 bg-[#F0F4FF] p-4" data-testid={`proof-panel-${badge.badge_id}`}>
      <div className="text-xs font-bold text-[#1D4ED8]">
        Test passed ({app.score_pct}%) — now show HCOB your credentials.
      </div>

      <div>
        <div className="font-mono-label text-[10px]">Certifications / photos of your work</div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*,.pdf"
          className="hidden"
          data-testid={`proof-file-input-${badge.badge_id}`}
          onChange={(e) => upload(e.target.files?.[0])}
        />
        {docs.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {docs.map((d) => (
              <div key={d.path} className="flex items-center justify-between rounded-lg border border-[#BFDBFE] bg-white px-3 py-2 text-xs">
                <span className="truncate font-semibold">{d.filename}</span>
                <button data-testid={`proof-doc-remove-${badge.badge_id}`} onClick={() => removeDoc(d.path)} className="ml-2 text-[#4B5563] hover:text-red-600">
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          data-testid={`proof-add-doc-btn-${badge.badge_id}`}
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[#93C5FD] bg-white px-3 py-3 text-xs font-semibold text-[#1D4ED8]"
        >
          <UploadSimple size={14} /> {busy ? "Uploading…" : "Add image or PDF"}
        </button>
      </div>

      <div>
        <div className="font-mono-label text-[10px]">Portfolio links (one per line)</div>
        <Textarea
          data-testid={`proof-links-${badge.badge_id}`}
          rows={2}
          value={links}
          onChange={(e) => setLinks(e.target.value)}
          placeholder={"https://instagram.com/yourwork\nhttps://yoursite.com"}
          className="mt-1 rounded-lg border-[#BFDBFE] bg-white text-xs"
        />
      </div>

      <div>
        <div className="font-mono-label text-[10px]">Anything HCOB should know (optional)</div>
        <Input
          data-testid={`proof-notes-${badge.badge_id}`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. 6 years licensed in MD, license #12345"
          className="mt-1 h-9 rounded-lg border-[#BFDBFE] bg-white text-xs"
        />
      </div>

      <Button
        data-testid={`proof-submit-btn-${badge.badge_id}`}
        onClick={submit}
        disabled={busy}
        className="h-11 w-full rounded-xl bg-[#0044FF] text-sm font-bold text-white"
      >
        {busy ? "Submitting…" : "Submit for HCOB review"}
      </Button>
    </div>
  );
}

function TestScreen({ badge, onExit }) {
  const [test, setTest] = useState(null);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/worker/badges/${badge.badge_id}/test`);
        setTest(data);
      } catch (e) {
        toast.error(getErr(e));
        onExit();
      }
    })();
    // eslint-disable-next-line
  }, [badge.badge_id]);

  const submit = async () => {
    if (!test) return;
    if (Object.keys(answers).length !== test.questions.length)
      return toast.error("Answer every question before submitting");
    setBusy(true);
    try {
      const { data } = await api.post(`/worker/badges/${badge.badge_id}/test`, {
        answers: test.questions.map((_, i) => answers[i]),
      });
      setResult(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="px-5 py-6 pb-28" data-testid="test-result-screen">
        <div
          className={`rounded-2xl border p-8 text-center ${
            result.passed ? "border-[#10B981]/40 bg-[#ECFDF5]" : "border-[#EF4444]/40 bg-[#FEF2F2]"
          }`}
        >
          {result.passed ? (
            <CheckCircle size={44} weight="fill" className="mx-auto text-[#10B981]" />
          ) : (
            <XCircle size={44} weight="fill" className="mx-auto text-[#EF4444]" />
          )}
          <h2 className="mt-3 font-display text-2xl font-black" data-testid="test-result-headline">
            {result.passed ? "You passed!" : "Not this time"}
          </h2>
          <p className="mt-1 text-sm text-[#4B5563]" data-testid="test-result-score">
            You scored <strong>{result.score_pct}%</strong> — pass mark {result.pass_pct}%.
          </p>
          <p className="mt-2 text-xs text-[#4B5563]">
            {result.passed
              ? "Next step: upload your certifications or portfolio so HCOB can verify and approve you."
              : "Retakes require HCOB approval. Your result is on file — contact HCOB if you'd like another attempt."}
          </p>
          <Button data-testid="test-result-back-btn" onClick={onExit} className="mt-5 h-11 w-full rounded-2xl bg-[#030712] text-white">
            {result.passed ? "Upload my credentials →" : "Back to certifications"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-5 py-6 pb-28" data-testid="test-screen">
      <button onClick={onExit} className="font-mono-label mb-4 flex items-center gap-2 text-[#4B5563]">
        <ArrowLeft size={14} /> Certifications
      </button>
      <div className="flex items-center gap-2">
        <div className="grid h-9 w-9 place-items-center rounded-lg text-white" style={{ backgroundColor: badge.color }}>
          <SealCheck size={18} weight="fill" />
        </div>
        <div>
          <h1 className="font-display text-xl font-black leading-tight">{badge.name} test</h1>
          <div className="text-[11px] text-[#4B5563]">
            One attempt · pass at {badge.pass_pct}% · answers are final
          </div>
        </div>
      </div>

      {!test ? (
        <div className="mt-6 rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
          Loading questions…
        </div>
      ) : (
        <>
          <div className="mt-5 space-y-4">
            {test.questions.map((q, qi) => (
              <div key={qi} className="rounded-2xl border border-black/5 bg-white p-4" data-testid={`test-question-${qi}`}>
                <div className="text-sm font-bold">
                  {qi + 1}. {q.q}
                </div>
                <div className="mt-3 space-y-2">
                  {q.options.map((opt, oi) => (
                    <label
                      key={oi}
                      data-testid={`test-q${qi}-opt${oi}`}
                      className={`flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2.5 text-sm ${
                        answers[qi] === oi
                          ? "border-[#0044FF] bg-[#F0F4FF] font-semibold"
                          : "border-[#E5E7EB] hover:border-[#9CA3AF]"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`q-${qi}`}
                        checked={answers[qi] === oi}
                        onChange={() => setAnswers((a) => ({ ...a, [qi]: oi }))}
                        className="mt-0.5 h-4 w-4 accent-[#0044FF]"
                      />
                      {opt}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <Button
            data-testid="test-submit-btn"
            onClick={submit}
            disabled={busy}
            className="mt-6 h-13 h-14 w-full rounded-2xl bg-[#0044FF] text-base font-bold text-white"
          >
            {busy ? "Scoring…" : `Submit answers (${Object.keys(answers).length}/${test.questions.length})`}
          </Button>
        </>
      )}
    </div>
  );
}
