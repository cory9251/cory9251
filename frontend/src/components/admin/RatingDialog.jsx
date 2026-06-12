import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import WorkerLink from "@/components/admin/WorkerLink";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Star,
  StarHalf,
  Trash,
  Copy,
  LinkSimple,
  ArrowsClockwise,
  PaperPlaneTilt,
  Note,
  ChatTeardropDots,
} from "@phosphor-icons/react";

/**
 * Star picker (1-5). Renders 5 buttons. Hover preview is intentionally subtle
 * — clicking commits the value.
 */
function StarPicker({ value, onChange, size = 24, testIdPrefix = "" }) {
  const [hover, setHover] = useState(0);
  const display = hover || value || 0;
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          data-testid={`${testIdPrefix}star-${n}`}
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          className={`transition-transform hover:scale-110 ${
            n <= display ? "text-[#F59E0B]" : "text-[#D1D5DB]"
          }`}
        >
          <Star size={size} weight={n <= display ? "fill" : "regular"} />
        </button>
      ))}
      <span className="ml-2 text-xs font-bold text-[#4B5563]">
        {value ? `${value}/5` : "Not rated"}
      </span>
    </div>
  );
}

/**
 * Read-only stars display — small inline component for cards/tables.
 */
export function StarsDisplay({ value, count, size = 12 }) {
  if (value == null) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
        <Star size={size} /> No ratings
      </span>
    );
  }
  const full = Math.floor(value);
  const half = value - full >= 0.5;
  return (
    <span className="inline-flex items-center gap-0.5 text-[#F59E0B]" title={`${value} from ${count} rating(s)`}>
      {[1, 2, 3, 4, 5].map((n) => {
        if (n <= full) return <Star key={n} size={size} weight="fill" />;
        if (n === full + 1 && half) return <StarHalf key={n} size={size} weight="fill" />;
        return <Star key={n} size={size} weight="regular" className="text-[#D1D5DB]" />;
      })}
      <span className="ml-1 text-[10px] font-bold text-[#030712]">
        {value.toFixed(1)}
      </span>
      {count != null && (
        <span className="ml-0.5 text-[10px] font-normal text-[#4B5563]">
          ({count})
        </span>
      )}
    </span>
  );
}

/**
 * Admin rating dialog. Captures admin's stars + private note for a worker on
 * one gig, AND lets admin generate/copy/regenerate a public client-feedback
 * link to share with the client.
 */
export default function RatingDialog({
  open,
  onOpenChange,
  gigId,
  acceptance,
  onSaved,
}) {
  const [stars, setStars] = useState(0);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [linkInfo, setLinkInfo] = useState(null);
  const [clientEmail, setClientEmail] = useState("");
  const [generatingLink, setGeneratingLink] = useState(false);
  // Per-gig admin note (separate from rating note)
  const [gigNote, setGigNote] = useState("");
  const [savingGigNote, setSavingGigNote] = useState(false);
  // Worker-visible message
  const [msgBody, setMsgBody] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);

  useEffect(() => {
    if (open && acceptance) {
      setStars(acceptance.admin_rating || 0);
      setNote(acceptance.admin_rating_note || "");
      setClientEmail(acceptance.client_email || "");
      setGigNote(acceptance.admin_gig_note || "");
      setMsgBody("");
      setLinkInfo(
        acceptance.client_rating_token
          ? { token: acceptance.client_rating_token, url: `${window.location.origin}/rate/${acceptance.client_rating_token}` }
          : null
      );
    }
  }, [open, acceptance]);

  if (!acceptance) return null;

  const saveGigNote = async () => {
    setSavingGigNote(true);
    try {
      await api.put(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/admin-note`,
        { note: gigNote }
      );
      toast.success(gigNote.trim() ? "Gig note saved" : "Gig note cleared");
      onSaved && onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingGigNote(false);
    }
  };

  const sendWorkerMessage = async () => {
    if (!msgBody.trim()) {
      toast.error("Type a message first");
      return;
    }
    setSendingMsg(true);
    try {
      await api.post(
        `/admin/workers/${acceptance.worker_id}/message`,
        { body: msgBody, gig_id: gigId }
      );
      toast.success("Message sent to worker");
      setMsgBody("");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSendingMsg(false);
    }
  };

  const saveAdminRating = async () => {
    if (!stars) {
      toast.error("Pick a star rating first");
      return;
    }
    setSaving(true);
    try {
      await api.put(`/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/rating`, {
        stars,
        note: note || null,
      });
      toast.success("Rating saved");
      onSaved && onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const clearRating = async () => {
    setSaving(true);
    try {
      await api.put(`/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/rating`, {
        clear: true,
      });
      toast.success("Rating cleared");
      onSaved && onSaved();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const generateLink = async (regenerate = false) => {
    setGeneratingLink(true);
    try {
      const { data } = await api.post(
        `/gigs/${gigId}/acceptances/${acceptance.acceptance_id}/rating-link`,
        { client_email: clientEmail || null, regenerate }
      );
      // Build absolute URL on the frontend (backend may return relative)
      const url = data.url.startsWith("http")
        ? data.url
        : `${window.location.origin}/rate/${data.token}`;
      setLinkInfo({ token: data.token, url });
      toast.success(regenerate ? "New link generated" : "Link ready");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setGeneratingLink(false);
    }
  };

  const copyLink = async () => {
    if (!linkInfo) return;
    try {
      await navigator.clipboard.writeText(linkInfo.url);
      toast.success("Link copied");
    } catch {
      toast.error("Could not copy — select & copy manually");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg max-h-[90vh] overflow-y-auto rounded-none border-[#030712]"
        data-testid="rating-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-black">
            Rate worker
          </DialogTitle>
          <DialogDescription>
            <span className="font-semibold">
              <WorkerLink workerId={acceptance.worker_id} name={acceptance.worker_name} />
            </span> for
            this gig. The admin rating is private. The client link is shareable.
          </DialogDescription>
        </DialogHeader>

        {/* Admin rating */}
        <div className="space-y-3">
          <div className="font-mono-label">Admin rating</div>
          <StarPicker value={stars} onChange={setStars} testIdPrefix="admin-" />
          <Textarea
            data-testid="admin-rating-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Private note (admins only)…"
            rows={2}
            className="rounded-none border-[#030712] text-sm"
          />
          <div className="flex flex-wrap justify-between gap-2">
            {acceptance.admin_rating != null && (
              <Button
                type="button"
                variant="outline"
                onClick={clearRating}
                disabled={saving}
                data-testid="clear-admin-rating"
                className="rounded-none border-[#4B5563] text-xs"
              >
                <Trash size={12} className="mr-1.5" /> Clear
              </Button>
            )}
            <Button
              type="button"
              onClick={saveAdminRating}
              disabled={saving}
              data-testid="save-admin-rating"
              className="ml-auto rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {saving ? "Saving…" : "Save rating"}
            </Button>
          </div>
        </div>

        {/* Client feedback link */}
        <div className="space-y-3 border-t border-[#E5E7EB] pt-4">
          <div className="font-mono-label">Client feedback link</div>
          <p className="text-xs text-[#4B5563]">
            Share this link with the client. They get a simple star + note form
            — no login needed. The link works once.
          </p>
          {acceptance.client_rating != null ? (
            <div
              data-testid="client-rating-display"
              className="border border-[#10B981]/30 bg-[#ECFDF5] p-3 text-xs"
            >
              <div className="font-mono-label text-[#065F46]">Client submitted</div>
              <div className="mt-1 flex items-center gap-3">
                <StarsDisplay value={acceptance.client_rating} count={null} size={14} />
              </div>
              {acceptance.client_rating_note && (
                <div className="mt-2 italic text-[#065F46]">
                  "{acceptance.client_rating_note}"
                </div>
              )}
              {acceptance.client_rating_submitted_name && (
                <div className="mt-1 text-[10px] text-[#065F46]/80">
                  — {acceptance.client_rating_submitted_name}
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                onClick={() => generateLink(true)}
                disabled={generatingLink}
                data-testid="regenerate-rating-link"
                className="mt-3 rounded-none border-[#10B981] text-xs text-[#065F46]"
              >
                <ArrowsClockwise size={12} className="mr-1.5" /> Generate new link
              </Button>
            </div>
          ) : (
            <>
              <Input
                data-testid="client-rating-email"
                type="email"
                value={clientEmail}
                onChange={(e) => setClientEmail(e.target.value)}
                placeholder="Client email (optional, for your records)"
                className="h-10 rounded-none border-[#030712]"
              />
              {linkInfo ? (
                <div className="space-y-2">
                  <div
                    data-testid="rating-link-display"
                    className="flex items-center gap-2 break-all border border-[#0044FF]/30 bg-[#F0F4FF] p-2 text-[10px] font-mono"
                  >
                    <LinkSimple size={12} className="shrink-0 text-[#0044FF]" />
                    {linkInfo.url}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      onClick={copyLink}
                      data-testid="copy-rating-link"
                      className="rounded-none bg-[#030712] text-white"
                    >
                      <Copy size={12} className="mr-1.5" /> Copy link
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => generateLink(true)}
                      disabled={generatingLink}
                      data-testid="regen-rating-link"
                      className="rounded-none border-[#4B5563] text-xs"
                    >
                      <ArrowsClockwise size={12} className="mr-1.5" /> Regenerate
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  type="button"
                  onClick={() => generateLink(false)}
                  disabled={generatingLink}
                  data-testid="generate-rating-link"
                  className="w-full rounded-none bg-[#10B981] text-white hover:bg-[#0e9971]"
                >
                  <PaperPlaneTilt size={12} className="mr-1.5" />
                  {generatingLink ? "Generating…" : "Generate client link"}
                </Button>
              )}
            </>
          )}
        </div>

        {/* Per-gig admin note (separate from rating note) */}
        <div className="space-y-2 border-t border-[#E5E7EB] pt-4">
          <div className="font-mono-label flex items-center gap-1.5">
            <Note size={11} weight="duotone" /> Per-gig admin note
          </div>
          <p className="text-[10px] text-[#4B5563]">
            Private ops note about this worker on this gig (e.g. "arrived 15
            min late", "client asked for them again"). Workers never see this.
          </p>
          <Textarea
            data-testid="admin-gig-note"
            value={gigNote}
            onChange={(e) => setGigNote(e.target.value)}
            placeholder="Quick note…"
            rows={2}
            className="rounded-none border-[#030712] text-sm"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              data-testid="save-admin-gig-note"
              onClick={saveGigNote}
              disabled={savingGigNote}
              className="rounded-none bg-[#030712] text-xs text-white"
            >
              {savingGigNote ? "Saving…" : (gigNote.trim() ? "Save note" : "Clear note")}
            </Button>
          </div>
        </div>

        {/* Send a worker-visible message */}
        <div className="space-y-2 border-t border-[#E5E7EB] pt-4">
          <div className="font-mono-label flex items-center gap-1.5">
            <ChatTeardropDots size={11} weight="duotone" /> Message the worker
          </div>
          <p className="text-[10px] text-[#4B5563]">
            One-way message to{" "}
            <WorkerLink workerId={acceptance.worker_id} name={acceptance.worker_name} />.
            Lands in their app notifications — they CAN see this one.
          </p>
          <Textarea
            data-testid="worker-message-body"
            value={msgBody}
            onChange={(e) => setMsgBody(e.target.value)}
            placeholder="e.g. Bring extra towels — client has 2 dogs."
            rows={2}
            className="rounded-none border-[#030712] text-sm"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              data-testid="send-worker-message"
              onClick={sendWorkerMessage}
              disabled={sendingMsg || !msgBody.trim()}
              className="rounded-none bg-[#0044FF] text-xs text-white hover:bg-[#0036cc]"
            >
              <PaperPlaneTilt size={12} className="mr-1.5" />
              {sendingMsg ? "Sending…" : "Send message"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
