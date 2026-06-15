import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  CurrencyDollar,
  MapPin,
  Clock,
  CalendarBlank,
  Broom,
  Wrench,
  Car,
  CheckCircle,
  Sparkle,
  ArrowRight,
} from "@phosphor-icons/react";
import { getPaymentTimeline } from "@/lib/paymentTimeline";
import { formatGigLong } from "@/lib/gigDate";
import MarkdownView from "@/components/MarkdownView";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

/**
 * Public, no-auth gig page reached via /gigs/:gigId (the share link). Shows
 * the gig's public-safe info and bounces the visitor through register/login →
 * /app/gigs/:gigId where the authenticated worker flow takes over.
 */
export default function PublicGigPage() {
  const { gigId } = useParams();
  const [gig, setGig] = useState(null);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();
  const { user } = useAuth() || {};

  // Logged-in workers hitting a blast/share link skip the public landing and
  // land directly on the authenticated gig view.
  useEffect(() => {
    if (user && user.role === "worker") {
      nav(`/crew/gigs/${gigId}`, { replace: true });
    }
  }, [user, gigId, nav]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/public/gigs/${gigId}`);
        if (!res.ok) {
          setGig({ error: res.status });
        } else {
          setGig(await res.json());
        }
      } catch {
        setGig({ error: "network" });
      } finally {
        setLoading(false);
      }
    })();
  }, [gigId]);

  const continueToApp = () => {
    // Already-logged-in workers go straight to the gig detail; new visitors
    // are redirected to register with a `next` query so they land on the gig
    // after signup.
    nav(`/crew/gigs/${gigId}`);
  };

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#F9FAFB] text-sm text-[#4B5563]">
        Loading…
      </div>
    );
  }
  if (!gig || gig.error) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#F9FAFB] p-6">
        <div
          data-testid="public-gig-not-found"
          className="max-w-sm border border-[#E5E7EB] bg-white p-6 text-center"
        >
          <div className="font-display text-2xl font-black">Gig not found</div>
          <p className="mt-2 text-sm text-[#4B5563]">
            This gig is no longer available or the link is invalid.
          </p>
          <Link
            to="/"
            className="mt-4 inline-block text-[#0044FF] underline"
          >
            Back to HCOB Network →
          </Link>
        </div>
      </div>
    );
  }

  const Icon = CAT_ICON[gig.category] || Broom;
  const payDisplay = `$${Number(gig.pay_rate || 0).toFixed(2)}${
    gig.pay_type === "hourly" ? "/hr" : " flat"
  }`;
  const filled = (gig.slots_filled || 0) >= (gig.slots || 0);

  return (
    <div className="min-h-screen bg-[#F9FAFB] py-10 px-4">
      <div className="mx-auto max-w-md">
        <Link
          to="/"
          className="font-mono-label inline-flex items-center gap-1.5 text-[#0044FF]"
        >
          <Sparkle size={12} weight="fill" /> HCOB Network
        </Link>

        <div className="mt-4 overflow-hidden rounded-3xl border border-black/5 bg-white shadow-sm">
          {/* Hero */}
          <div className="bg-[#030712] p-6 text-white">
            <div className="font-mono-label text-white/70">
              {gig.category} · {gig.subcategory || "general"}
            </div>
            <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
              {gig.title}
            </h1>
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-[#10B981] px-3 py-1.5 text-sm font-bold">
              <CurrencyDollar size={14} weight="fill" /> {payDisplay}
            </div>
          </div>

          {/* Details */}
          <div className="space-y-3 p-6 text-sm">
            <Row icon={MapPin} label="Where" value={gig.location} />
            <Row
              icon={CalendarBlank}
              label="When"
              value={formatGigLong(gig)}
            />
            {gig.duration_hours && (
              <Row
                icon={Clock}
                label="Duration"
                value={`${gig.duration_hours} hrs`}
              />
            )}
            <Row
              icon={Icon}
              label="Slots"
              value={`${gig.slots_filled || 0} / ${gig.slots || 0} filled`}
            />
            {(() => {
              const pt = getPaymentTimeline(gig.payment_timeline);
              const PI = pt.icon;
              return (
                <Row icon={PI} label="Payment" value={pt.label} />
              );
            })()}
            {gig.payment_timeline === "custom" && gig.payment_timeline_note && (
              <div className="bg-[#FFFBEB] px-3 py-1.5 text-xs text-[#92400E]">
                <strong>Note:</strong> {gig.payment_timeline_note}
              </div>
            )}
            {gig.description && (
              <div className="border-t border-[#E5E7EB] pt-3">
                <div className="font-mono-label">Description</div>
                <div className="mt-1 text-[#4B5563]">
                  <MarkdownView text={gig.description} />
                </div>
              </div>
            )}
          </div>

          {/* CTA */}
          <div className="border-t border-[#E5E7EB] bg-[#F9FAFB] p-6">
            {filled ? (
              <div className="text-center text-sm font-bold text-[#92400E]">
                This gig is fully filled — but more gigs come in every day.
              </div>
            ) : (
              <>
                <Button
                  data-testid="public-claim-btn"
                  onClick={continueToApp}
                  className="h-12 w-full rounded-2xl bg-[#0044FF] text-white hover:bg-[#0036cc]"
                >
                  <CheckCircle size={16} weight="fill" className="mr-2" /> Claim
                  this gig
                  <ArrowRight size={14} className="ml-1.5" />
                </Button>
                <p className="mt-3 text-center text-[10px] text-[#4B5563]">
                  You'll need an HCOB Network account. New here?{" "}
                  <Link
                    to={`/register?next=/app/gigs/${gigId}`}
                    className="font-bold text-[#0044FF] underline"
                  >
                    Sign up free →
                  </Link>
                </p>
              </>
            )}
          </div>
        </div>

        <p className="mt-4 text-center text-[10px] text-[#4B5563]">
          hcobcleaners.com · A trusted local gig platform
        </p>
      </div>
    </div>
  );
}

function Row({ icon: I, label, value }) {
  return (
    <div className="flex items-start gap-3">
      <I size={16} weight="duotone" className="mt-0.5 shrink-0 text-[#0044FF]" />
      <div className="min-w-0 flex-1">
        <div className="font-mono-label">{label}</div>
        <div className="text-sm font-semibold text-[#030712]">{value || "—"}</div>
      </div>
    </div>
  );
}
