import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Star, CheckCircle, Sparkle } from "@phosphor-icons/react";

/**
 * Public, no-auth rating page reached via /rate/:token. The client picks
 * 1-5 stars + optional note + name, then submits. The token is burned on
 * submission. No HCOB branding leaks beyond the worker name + gig title.
 */
export default function RatePage() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stars, setStars] = useState(0);
  const [hover, setHover] = useState(0);
  const [note, setNote] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/public/rating/${token}`);
        if (!res.ok) {
          setInfo({ error: res.status });
        } else {
          setInfo(await res.json());
        }
      } catch {
        setInfo({ error: "network" });
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (!stars) {
      toast.error("Pick a star rating first");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/public/rating/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stars, note: note || null, client_name: name || null }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setSubmitted(true);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#F9FAFB] text-sm text-[#4B5563]">
        Loading…
      </div>
    );
  }
  if (!info || info.error) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#F9FAFB] p-6">
        <div
          data-testid="rating-not-found"
          className="max-w-sm border border-[#E5E7EB] bg-white p-6 text-center"
        >
          <div className="font-display text-2xl font-black">Link not found</div>
          <p className="mt-2 text-sm text-[#4B5563]">
            This rating link has already been used or is no longer valid. If
            you'd like to leave feedback, contact HCOB for a fresh link.
          </p>
        </div>
      </div>
    );
  }
  if (submitted) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#F9FAFB] p-6">
        <div
          data-testid="rating-thanks"
          className="max-w-md border border-[#10B981]/30 bg-[#ECFDF5] p-8 text-center"
        >
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-[#10B981] text-white">
            <CheckCircle size={32} weight="fill" />
          </div>
          <div className="mt-4 font-display text-2xl font-black text-[#065F46]">
            Thanks for the feedback!
          </div>
          <p className="mt-2 text-sm text-[#065F46]/80">
            HCOB and {info.worker_name} appreciate you taking the time. You can
            close this page now.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] py-10 px-4">
      <div className="mx-auto max-w-md">
        <div className="font-mono-label inline-flex items-center gap-1.5 text-[#0044FF]">
          <Sparkle size={12} weight="fill" /> HCOB Network
        </div>
        <h1 className="mt-2 font-display text-3xl font-black tracking-tight">
          How did {info.worker_name} do?
        </h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          {info.gig_title}
          {info.gig_scheduled_date && (
            <span> · {info.gig_scheduled_date}</span>
          )}
          {info.gig_location && <span> · {info.gig_location}</span>}
        </p>

        <form
          onSubmit={submit}
          data-testid="public-rating-form"
          className="mt-6 space-y-4 rounded-2xl border border-black/5 bg-white p-6 shadow-sm"
        >
          <div>
            <Label className="font-mono-label">Your rating</Label>
            <div className="mt-2 flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  data-testid={`public-star-${n}`}
                  onClick={() => setStars(n)}
                  onMouseEnter={() => setHover(n)}
                  onMouseLeave={() => setHover(0)}
                  className={`transition-transform hover:scale-110 ${
                    n <= (hover || stars) ? "text-[#F59E0B]" : "text-[#D1D5DB]"
                  }`}
                >
                  <Star size={36} weight={n <= (hover || stars) ? "fill" : "regular"} />
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label className="font-mono-label">Anything to share? (optional)</Label>
            <Textarea
              data-testid="public-rating-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="What did they do well? Anything we should fix?"
              className="mt-2 rounded-xl border-[#E5E7EB]"
            />
          </div>

          <div>
            <Label className="font-mono-label">Your name (optional)</Label>
            <Input
              data-testid="public-rating-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Client"
              className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
            />
          </div>

          <Button
            data-testid="public-rating-submit"
            type="submit"
            disabled={submitting || !stars}
            className="h-12 w-full rounded-2xl bg-[#030712] text-white"
          >
            {submitting ? "Submitting…" : "Submit feedback"}
          </Button>
        </form>

        <p className="mt-4 text-center text-[10px] text-[#4B5563]">
          Powered by HCOB Network · hcobcleaners.com
        </p>
      </div>
    </div>
  );
}
