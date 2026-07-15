import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { AnnouncementsBoard } from "@/components/announcements/AnnouncementsBoard";
import {
  Broom,
  Wrench,
  Car,
  CurrencyDollar,
  MapPin,
  Clock,
  CheckCircle,
  IdentificationCard,
  ShieldCheck,
  CaretRight,
  FolderSimple,
  SealCheck,
  X,
  HandWaving,
  Toolbox,
} from "@phosphor-icons/react";
import GigPhoto from "@/components/GigPhoto";
import { isSpecialist, payLine, dateLine, scopeLine } from "@/lib/specialist";
import { TAG_CONFIG, getTagBorderClass, getOrderedTags } from "@/lib/gigTags";
import { getPaymentTimeline } from "@/lib/paymentTimeline";
import { formatGigFull, isGigToday } from "@/lib/gigDate";
import AvailableNowToggle from "@/components/worker/AvailableNowToggle";
import WorkerCustomerChatsInbox from "@/components/worker/WorkerCustomerChatsInbox";
import FeedFilters, { DEFAULT_FILTERS, applyFeedFilters } from "@/components/worker/FeedFilters";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function WorkerFeed() {
  const [gigs, setGigs] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [hideCertsCta, setHideCertsCta] = useState(
    () => localStorage.getItem("hcob_certs_cta_hidden") === "1"
  );
  const nav = useNavigate();
  const { user } = useAuth();
  const status = user?.worker_status || "approved";
  const isPending = status === "pending";
  const isBlocked = status === "rejected" || status === "suspended";
  const needsId = status === "approved" && !user?.id_image_path;
  const awaitingVerification =
    status === "approved" && !!user?.id_image_path && !user?.id_verified;
  const incompleteProfile =
    status === "approved" && (user?.profile_missing_fields?.length || 0) > 0;
  const showBanner =
    isPending || isBlocked || needsId || awaitingVerification || incompleteProfile;

  const bannerCopy = isBlocked
    ? {
        title: status === "rejected" ? "Application not approved" : "Account suspended",
        sub:
          status === "rejected"
            ? "HCOB did not approve your application. Contact HCOB if you think this is a mistake."
            : "Your account has been suspended. Contact HCOB to reinstate.",
      }
    : isPending
    ? {
        title: "Application under review",
        sub: "An HCOB admin needs to approve you before you can claim gigs.",
      }
    : incompleteProfile
    ? {
        title: "Finish your profile to claim gigs",
        sub: `${user.profile_missing_fields.length} item${user.profile_missing_fields.length === 1 ? "" : "s"} left — tap to complete.`,
      }
    : needsId
    ? {
        title: "Upload your ID to claim gigs",
        sub: "You can browse, but you need a verified ID before accepting.",
      }
    : {
        title: "Awaiting HCOB verification",
        sub: "Your ID is in review. You'll be able to accept assignments as soon as HCOB verifies you.",
      };

  const load = async () => {
    try {
      // Always fetch the full open + coming_soon feed; client-side filters
      // narrow it down. Keeps the network round trip simple.
      const { data } = await api.get("/gigs");
      setGigs(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, []);

  // Apply filters/sort client-side — the feed is bounded at 500 gigs so this
  // is cheap and avoids round-trip latency every time a worker tweaks a
  // dropdown.
  const visibleGigs = useMemo(
    () => applyFeedFilters(gigs, filters, (user?.zip_code || "").trim()),
    [gigs, filters, user?.zip_code],
  );

  return (
    <div className="px-5 py-6" data-testid="worker-feed">
      <div className="font-mono-label">Available now</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        Open assignments
      </h1>

      {/* "I'm available now" toggle — hidden for pending/blocked workers
          (the component handles that). Sits above the verification banner so
          even fully-onboarded crews get the prompt first. */}
      <AvailableNowToggle />

      {/* Company announcements — popup handles urgent ones; this board lets
          workers revisit anything they dismissed (auto-hides when empty). */}
      <AnnouncementsBoard />

      {/* Customer chats inbox — surfaces any project/gig chats the worker
          is in (auto-hides when empty). Closes the "I have no idea where to
          find my chats" gap workers were running into. */}
      <WorkerCustomerChatsInbox />

      {/* Certifications entry point — specialty jobs are gated behind badges.
          Closable (X) — also reachable from Profile and gig detail pages. */}
      {!hideCertsCta && (
        <div className="relative mt-4">
          <button
            data-testid="feed-certifications-cta"
            onClick={() => nav("/crew/certifications")}
            className="flex w-full items-center gap-3 rounded-2xl border border-[#0044FF]/20 bg-[#F0F4FF] p-4 pr-10 text-left hover:bg-[#E0E9FF]"
          >
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#0044FF] text-white">
              <SealCheck size={20} weight="fill" />
            </div>
            <div className="flex-1">
              <div className="font-display text-sm font-bold text-[#1D4ED8]">Get certified — unlock specialty jobs</div>
              <div className="mt-0.5 text-xs text-[#1D4ED8]/80">
                Electrician, plumber, box truck & more. Pass the test, upload proof, get first access.
              </div>
            </div>
            <CaretRight size={18} className="shrink-0 text-[#1D4ED8]" />
          </button>
          <button
            type="button"
            aria-label="Dismiss certifications banner"
            data-testid="certs-cta-close"
            onClick={() => {
              localStorage.setItem("hcob_certs_cta_hidden", "1");
              setHideCertsCta(true);
            }}
            className="absolute right-2 top-2 grid h-6 w-6 place-items-center text-[#1D4ED8]/50 hover:text-[#1D4ED8]"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {showBanner && (
        <button
          data-testid="verification-banner"
          onClick={() => !isBlocked && nav("/crew/me")}
          disabled={isBlocked}
          className={`mt-4 flex w-full items-start gap-3 rounded-2xl border p-4 text-left ${
            isBlocked
              ? "cursor-default border-[#EF4444]/30 bg-[#FEF2F2]"
              : "border-[#F59E0B]/40 bg-[#FFFBEB] hover:bg-[#FEF3C7]"
          }`}
        >
          <div
            className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl text-white ${
              isBlocked ? "bg-[#EF4444]" : "bg-[#F59E0B]"
            }`}
          >
            {isPending ? (
              <ShieldCheck size={20} weight="fill" />
            ) : needsId ? (
              <IdentificationCard size={20} weight="duotone" />
            ) : (
              <ShieldCheck size={20} weight="fill" />
            )}
          </div>
          <div className="flex-1">
            <div
              className={`font-display text-sm font-bold ${
                isBlocked ? "text-[#991B1B]" : "text-[#92400E]"
              }`}
            >
              {bannerCopy.title}
            </div>
            <div
              className={`mt-0.5 text-xs ${
                isBlocked ? "text-[#991B1B]/80" : "text-[#92400E]/80"
              }`}
            >
              {bannerCopy.sub}
            </div>
          </div>
          {!isBlocked && (
            <CaretRight size={18} className="mt-1 shrink-0 text-[#92400E]" />
          )}
        </button>
      )}

      <div className="mt-4">
        <FeedFilters
          value={filters}
          onChange={setFilters}
          resultCount={visibleGigs.length}
          totalCount={gigs.length}
          testIdPrefix="worker-feed-filters"
        />
      </div>

      <div className="mt-5 space-y-4">
        {visibleGigs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            {gigs.length === 0
              ? "No open gigs right now. Check back soon."
              : "No gigs match your filters. Try clearing some."}
          </div>
        ) : (
          visibleGigs.map((g) => {
            const Icon = CAT_ICON[g.category];
            const acc = g.my_acceptance;
            const isRequested = acc?.status === "requested";
            const isApproved =
              acc?.status === "accepted" ||
              acc?.status === "on_the_clock" ||
              acc?.status === "completed";
            const activeTags = getOrderedTags(g.tags);
            const tagBorder = getTagBorderClass(g.tags);
            const isPinned = activeTags.length > 0 || g.is_rush;
            const pt = getPaymentTimeline(g.payment_timeline);
            // Only highlight same-day or custom on the card (default 2-3 day
            // pay is implicit and doesn't need a pill).
            const showPayPill = g.payment_timeline === "same_day" || g.payment_timeline === "custom";
            const PI = pt.icon;
            return (
              <div
                key={g.gig_id}
                role="button"
                tabIndex={0}
                data-testid={`feed-gig-${g.gig_id}`}
                onClick={() => nav(`/crew/assignments/${g.gig_id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    nav(`/crew/assignments/${g.gig_id}`);
                  }
                }}
                className={`gb-tactile relative w-full cursor-pointer rounded-2xl bg-white p-5 text-left transition-all focus:outline-none focus:ring-2 focus:ring-[#0044FF] ${
                  tagBorder || "border border-black/5"
                }`}
              >
                {(activeTags.length > 0 || showPayPill || g.project || g.required_badge || isSpecialist(g)) && (
                  <div
                    data-testid={`tag-stack-${g.gig_id}`}
                    className="-mt-1 mb-3 flex flex-wrap gap-1.5"
                  >
                    {activeTags.map((t) => {
                      const cfg = TAG_CONFIG[t];
                      const I = cfg.icon;
                      return (
                        <span
                          key={t}
                          data-testid={`tag-${t}-${g.gig_id}`}
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] ${cfg.pillClass}`}
                        >
                          <I
                            size={11}
                            weight="fill"
                            className={cfg.pulse ? "animate-pulse" : ""}
                          />
                          {cfg.label}
                        </span>
                      );
                    })}
                    {showPayPill && (
                      <span
                        data-testid={`pay-pill-${g.gig_id}`}
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] ${pt.pillClass}`}
                      >
                        <PI
                          size={11}
                          weight="fill"
                          className={pt.pulse ? "animate-pulse" : ""}
                        />
                        {pt.short}
                      </span>
                    )}
                    {isSpecialist(g) && (
                      <span
                        data-testid={`specialist-pill-${g.gig_id}`}
                        className="inline-flex items-center gap-1 rounded-full bg-[#7C3AED] px-2.5 py-1 text-[10px] font-black tracking-[0.18em] text-white"
                      >
                        <Toolbox size={11} weight="fill" /> SPECIALIST
                      </span>
                    )}
                    {g.required_badge && (
                      <span
                        data-testid={`badge-pill-${g.gig_id}`}
                        className="inline-flex max-w-[220px] items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] text-white"
                        style={{ backgroundColor: g.has_required_badge ? "#10B981" : (g.required_badge.color || "#0044FF") }}
                      >
                        <SealCheck size={11} weight="fill" />
                        <span className="truncate">
                          {g.has_required_badge ? "CERTIFIED" : "CERT REQUIRED"} · {g.required_badge.name.toUpperCase()}
                        </span>
                      </span>
                    )}
                    {g.project && (
                      <button
                        type="button"
                        data-testid={`project-pill-${g.gig_id}`}
                        title={`Tap to view all gigs in: ${g.project.title}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          nav(`/crew/projects/${g.project.project_id}`);
                        }}
                        className="inline-flex max-w-[180px] items-center gap-1 rounded-full bg-[#030712] px-2.5 py-1 text-[10px] font-black tracking-[0.18em] text-white hover:bg-[#1f2937]"
                      >
                        <FolderSimple size={11} weight="fill" />
                        <span className="truncate">PROJECT</span>
                      </button>
                    )}
                  </div>
                )}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 font-mono-label">
                      <Icon size={14} weight="duotone" />
                      {g.category} · {g.subcategory || "general"}
                    </div>
                    <h3 className="mt-2 font-display text-xl font-bold leading-snug">
                      {g.title}
                    </h3>
                    {scopeLine(g) && (
                      <div
                        data-testid={`scope-line-${g.gig_id}`}
                        className="mt-1 text-xs font-semibold text-[#4B5563]"
                      >
                        {scopeLine(g)}
                      </div>
                    )}
                  </div>
                  {isApproved ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      <CheckCircle size={10} weight="fill" /> APPROVED
                    </span>
                  ) : isRequested ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                      REQUESTED
                    </span>
                  ) : g.my_interest ? (
                    <span
                      data-testid={`interested-pill-${g.gig_id}`}
                      className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#7C3AED] px-3 py-1 text-[10px] font-bold tracking-widest text-white"
                    >
                      <HandWaving size={10} weight="fill" /> INTERESTED
                    </span>
                  ) : !isPinned ? (
                    <span className="shrink-0 rounded-full bg-[#0044FF] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      OPEN
                    </span>
                  ) : null}
                </div>

                <div className="mt-4 grid grid-cols-1 gap-2 border-t border-[#E5E7EB] pt-3 text-xs sm:grid-cols-2">
                  <Bit
                    icon={CurrencyDollar}
                    value={
                      payLine(g) ||
                      `$${Number(g.pay_rate || 0).toFixed(0)}${
                        g.pay_type === "hourly" ? "/hr" : ""
                      }`
                    }
                  />
                  <Bit icon={MapPin} value={g.location} />
                  <Bit
                    icon={Clock}
                    value={dateLine(g) || formatGigFull(g)}
                    highlight={!dateLine(g) && isGigToday(g)}
                    testId={`feed-when-${g.gig_id}`}
                    className="sm:col-span-2"
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

const Bit = ({ icon: I, value, highlight, testId, className }) => (
  <div
    data-testid={testId}
    className={`flex items-start gap-1.5 ${
      highlight ? "text-[#0044FF]" : "text-[#4B5563]"
    } ${className || ""}`}
  >
    <I size={14} weight={highlight ? "fill" : "duotone"} className="mt-px shrink-0" />
    <span
      className={`font-semibold ${
        highlight ? "text-[#0044FF]" : "text-[#030712]"
      }`}
    >
      {value}
    </span>
  </div>
);
