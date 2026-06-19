import React, { useEffect, useState } from "react";
import {
  Sparkle,
  X,
  Copy,
  CheckCircle,
  WarningCircle,
  Pen,
} from "@phosphor-icons/react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";

/**
 * AI Objection Coach popover — VA taps "Handle objection" on a lead card,
 * picks a common objection or types a custom one, and the LLM returns 3
 * on-brand response options the VA can copy.
 *
 * Props:
 *   - lead: { lead_id, prospect_name }
 *   - open: bool
 *   - onClose: () => void
 */
export default function ObjectionCoach({ lead, open, onClose }) {
  const [objections, setObjections] = useState(null);
  const [loadingList, setLoadingList] = useState(false);
  const [pickedKey, setPickedKey] = useState(null);
  const [customText, setCustomText] = useState("");
  const [loading, setLoading] = useState(false);
  const [responses, setResponses] = useState(null);
  const [usage, setUsage] = useState(null); // {calls_used_last_hour, rate_limit_per_hour}
  const [copiedIdx, setCopiedIdx] = useState(null);

  useEffect(() => {
    if (!open || objections !== null) return;
    setLoadingList(true);
    api
      .get("/va/objection-coach/objections")
      .then((r) => {
        setObjections(r.data.objections || []);
        setUsage({
          calls_used_last_hour: 0,
          rate_limit_per_hour: r.data.rate_limit_per_hour,
        });
      })
      .catch((e) => toast.error(getErr(e)))
      .finally(() => setLoadingList(false));
  }, [open, objections]);

  if (!open) return null;

  const reset = () => {
    setPickedKey(null);
    setCustomText("");
    setResponses(null);
    setCopiedIdx(null);
  };

  const submit = async () => {
    if (!pickedKey && !customText.trim()) {
      toast.error("Pick an objection or type one");
      return;
    }
    setLoading(true);
    setResponses(null);
    setCopiedIdx(null);
    try {
      const body = pickedKey
        ? { objection_key: pickedKey }
        : { custom_text: customText.trim() };
      const r = await api.post(`/va/leads/${lead.lead_id}/objection-coach`, body);
      setResponses(r.data.responses || []);
      setUsage({
        calls_used_last_hour: r.data.calls_used_last_hour,
        rate_limit_per_hour: r.data.rate_limit_per_hour,
      });
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  const copy = async (idx, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      toast.success("Copied — paste into SMS/email/DM");
      setTimeout(() => setCopiedIdx((c) => (c === idx ? null : c)), 2000);
    } catch {
      toast.error("Couldn't copy — long-press to select instead");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      data-testid="objection-coach-modal"
    >
      <div
        className="flex w-full max-w-2xl flex-col border border-[#030712] bg-white shadow-2xl sm:max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#030712] bg-[#0044FF] px-5 py-3 text-white">
          <div className="flex items-center gap-2">
            <Sparkle size={20} weight="fill" />
            <div>
              <div className="font-display text-lg font-bold leading-tight">
                Objection Coach
              </div>
              <div className="font-mono-label text-[10px] tracking-widest text-white/80">
                For {lead.prospect_name}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            data-testid="objection-coach-close"
            className="grid h-8 w-8 place-items-center text-white hover:bg-white/10"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {/* Step 1 — Pick or type the objection */}
          {!responses && (
            <>
              <div className="font-mono-label mb-2 text-[10px] tracking-widest text-[#4B5563]">
                What did the prospect say?
              </div>
              <div className="flex flex-wrap gap-2">
                {loadingList && (
                  <div className="text-xs text-[#9CA3AF]">Loading…</div>
                )}
                {(objections || []).map((o) => (
                  <button
                    key={o.key}
                    onClick={() => {
                      setPickedKey(o.key);
                      setCustomText("");
                    }}
                    data-testid={`objection-pick-${o.key}`}
                    className={`border px-3 py-2 text-left text-xs font-semibold transition-colors ${
                      pickedKey === o.key
                        ? "border-[#030712] bg-[#030712] text-white"
                        : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#030712]"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>

              <div className="mt-5 border-t border-[#E5E7EB] pt-5">
                <div className="font-mono-label mb-2 flex items-center gap-1.5 text-[10px] tracking-widest text-[#4B5563]">
                  <Pen size={11} /> Or type it in their own words
                </div>
                <textarea
                  data-testid="objection-custom-text"
                  value={customText}
                  onChange={(e) => {
                    setCustomText(e.target.value);
                    if (e.target.value.trim()) setPickedKey(null);
                  }}
                  rows={3}
                  maxLength={500}
                  placeholder={'e.g. "She said her husband cleans on Saturdays and she doesn\u2019t want to pay for something he does"'}
                  className="w-full resize-none border border-[#030712] bg-white p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#0044FF]"
                />
              </div>

              <div className="mt-5 flex items-center justify-between">
                <div className="font-mono-label text-[10px] text-[#9CA3AF]">
                  {usage
                    ? `${usage.calls_used_last_hour}/${usage.rate_limit_per_hour} coach calls used this hour`
                    : ""}
                </div>
                <button
                  data-testid="objection-coach-submit"
                  onClick={submit}
                  disabled={loading || (!pickedKey && !customText.trim())}
                  className="inline-flex items-center gap-2 bg-[#0044FF] px-5 py-2.5 text-sm font-bold uppercase tracking-widest text-white hover:bg-[#0036cc] disabled:bg-[#9CA3AF]"
                >
                  {loading ? (
                    <>
                      <Sparkle size={14} className="animate-spin" /> Generating…
                    </>
                  ) : (
                    <>
                      <Sparkle size={14} weight="fill" /> Get 3 responses
                    </>
                  )}
                </button>
              </div>
            </>
          )}

          {/* Step 2 — Responses */}
          {responses && responses.length > 0 && (
            <>
              <div className="mb-3 flex items-center justify-between">
                <div className="font-mono-label text-[10px] tracking-widest text-[#4B5563]">
                  3 options · tap Copy then paste into SMS/email/DM
                </div>
                <button
                  data-testid="objection-coach-reset"
                  onClick={reset}
                  className="font-mono-label text-[10px] tracking-widest text-[#0044FF] hover:underline"
                >
                  ← try a different objection
                </button>
              </div>
              <div className="space-y-3">
                {responses.map((r, i) => (
                  <div
                    key={i}
                    data-testid={`objection-response-${i}`}
                    className="border border-[#E5E7EB] bg-white p-4 hover:border-[#030712]"
                  >
                    <div className="font-mono-label mb-2 text-[10px] tracking-widest text-[#0044FF]">
                      Option {i + 1} · {r.angle}
                    </div>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-[#030712]">
                      {r.body}
                    </div>
                    <div className="mt-3 flex items-center justify-between">
                      <div className="font-mono-label text-[9px] text-[#9CA3AF]">
                        ~{r.body.length} chars · fits in a text message
                      </div>
                      <button
                        onClick={() => copy(i, r.body)}
                        data-testid={`objection-copy-${i}`}
                        className={`inline-flex items-center gap-1.5 border px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors ${
                          copiedIdx === i
                            ? "border-[#10B981] bg-[#10B981] text-white"
                            : "border-[#030712] bg-white text-[#030712] hover:bg-[#030712] hover:text-white"
                        }`}
                      >
                        {copiedIdx === i ? (
                          <>
                            <CheckCircle size={11} weight="fill" /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={11} /> Copy
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-5 flex items-start gap-2 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs text-[#4B5563]">
                <WarningCircle size={14} className="mt-0.5 shrink-0" />
                <span>
                  AI suggestions only. Always read once before sending — adjust
                  the tone for your specific prospect and never quote pricing
                  unless you&apos;ve already confirmed it with Ops.
                </span>
              </div>
            </>
          )}

          {responses && responses.length === 0 && (
            <div className="border border-[#EF4444] bg-[#FEE2E2] p-4 text-sm text-[#991B1B]">
              The AI didn&apos;t return any usable responses. Try a different
              objection wording.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
