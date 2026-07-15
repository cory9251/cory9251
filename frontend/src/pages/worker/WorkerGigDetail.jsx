import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { getPaymentTimeline } from "@/lib/paymentTimeline";
import { formatGigLong, formatGigRelative, isGigToday } from "@/lib/gigDate";
import MarkdownView from "@/components/MarkdownView";
import CustomerChatPanel from "@/components/worker/CustomerChatPanel";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Broom,
  Wrench,
  Car,
  CurrencyDollar,
  MapPin,
  Clock,
  Users,
  Phone,
  CheckCircle,
  Play,
  Stop,
  Timer,
  IdentificationCard,
  ShieldCheck,
  EyeSlash,
  UsersThree,
  FolderSimple,
  SealCheck,
  HandWaving,
} from "@phosphor-icons/react";
import GigPhoto from "@/components/GigPhoto";
import {
  isSpecialist,
  takesInterestOnly,
  payLine,
  payReason,
  dateLine,
  scopeLine,
  windowDays,
  dayLabel,
} from "@/lib/specialist";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

function elapsedFrom(iso) {
  if (!iso) return "0:00:00";
  const start = new Date(iso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function WorkerGigDetail() {
  const { gigId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [gig, setGig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState("0:00:00");

  // Worker agreement modal — workers must check + sign each accept.
  const [agreementOpen, setAgreementOpen] = useState(false);
  const [agreementRules, setAgreementRules] = useState([]);
  const [agreementVersion, setAgreementVersion] = useState("v1");
  const [agreementChecked, setAgreementChecked] = useState(false);
  const [agreementTypedName, setAgreementTypedName] = useState("");
  // Window-dated gigs — worker picks their day at claim (FRD Addendum B).
  const [chosenDate, setChosenDate] = useState("");

  const load = async () => {
    try {
      const { data } = await api.get(`/gigs/${gigId}`);
      setGig(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // View tracking — deduped per worker per gig server-side (Addendum B).
    api.post(`/gigs/${gigId}/view`).catch(() => {});
    // eslint-disable-next-line
  }, [gigId]);

  // Live ticker while on the clock
  useEffect(() => {
    const cin = gig?.my_acceptance?.clock_in_at;
    const cout = gig?.my_acceptance?.clock_out_at;
    if (!cin || cout) return;
    setElapsed(elapsedFrom(cin));
    const t = setInterval(() => setElapsed(elapsedFrom(cin)), 1000);
    return () => clearInterval(t);
  }, [gig]);

  const accept = async () => {
    // First-time UX: fetch rules and open the agreement modal. The actual
    // POST happens in submitAgreement() after the worker checks the box and
    // types their full name to confirm.
    setBusy(true);
    try {
      const { data } = await api.get("/worker/agreement-rules");
      setAgreementRules(data.rules || []);
      setAgreementVersion(data.version || "v1");
      setAgreementTypedName("");
      setAgreementChecked(false);
      setAgreementOpen(true);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const submitAgreement = async () => {
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/accept`, {
        typed_name: agreementTypedName.trim(),
        agreed_rules: agreementRules,
        version: agreementVersion,
        chosen_date: gig?.date_mode === "window" ? chosenDate : null,
      });
      setAgreementOpen(false);
      toast.success("Request sent — waiting for HCOB approval");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelNote, setCancelNote] = useState("");

  const withdrawRequest = async () => {
    // Cancel an unapproved request — quick, no reason needed
    if (!window.confirm("Cancel your pending request for this gig?")) return;
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/cancel-shift`, { reason: "other", note: "Withdrew before approval" });
      toast.success("Request cancelled");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const submitCancel = async () => {
    if (!cancelReason) {
      toast.error("Please pick a reason");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(`/gigs/${gigId}/cancel-shift`, {
        reason: cancelReason,
        note: cancelNote || undefined,
      });
      if (data.is_late) {
        toast.warning("Shift cancelled — flagged as late (<24hr notice). HCOB has been notified.");
      } else {
        toast.success("Shift cancelled — HCOB notified");
      }
      if (data.backup_promoted) {
        toast.info("A backup worker has been auto-promoted.");
      }
      setCancelOpen(false);
      setCancelReason("");
      setCancelNote("");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const getPosition = () =>
    new Promise((resolve) => {
      if (!navigator.geolocation) {
        return resolve({ location_error: "Geolocation not supported on this device" });
      }
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
          }),
        (err) => resolve({ location_error: err?.message || "Location unavailable" }),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });

  const clockIn = async () => {
    setBusy(true);
    try {
      const loc = await getPosition();
      const { data } = await api.post(`/gigs/${gigId}/clock-in`, loc);
      if (data.location_verified) {
        toast.success("Clocked in — location verified on site");
      } else {
        toast.success("Clocked in — timer running (location not verified, flagged for review)");
      }
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const clockOut = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/gigs/${gigId}/clock-out`);
      toast.success(`Clocked out — ${data.hours_worked.toFixed(2)}h logged`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (!gig) return <div className="p-10 font-mono-label">Loading…</div>;

  const Icon = CAT_ICON[gig.category];
  const acc = gig.my_acceptance;
  const hasAcceptance = !!acc;
  const isRequested = acc?.status === "requested";
  const isBackup = acc?.status === "backup";
  const isApproved =
    acc?.status === "accepted" || acc?.status === "on_the_clock" || acc?.status === "completed";
  const onClock = !!acc?.clock_in_at && !acc?.clock_out_at;
  const completed = !!acc?.clock_out_at;
  const full = gig.slots_filled >= gig.slots && !isApproved;

  // Status & verification gates — only enforced before requesting
  const workerStatus = user?.worker_status || "approved";
  const isBlocked = workerStatus === "rejected" || workerStatus === "suspended";
  const hasId = !!user?.id_image_path;
  const verified = !!user?.id_verified;
  const profileMissing = user?.profile_missing_fields || [];
  const profileComplete = profileMissing.length === 0;
  const canRequest = !isBlocked && hasId && verified && profileComplete;
  const needsBadge = !!gig.required_badge && !gig.has_required_badge;

  return (
    <div className="px-5 py-6 pb-28" data-testid="worker-gig-detail">
      <button
        onClick={() => nav("/crew")}
        className="font-mono-label mb-4 flex items-center gap-2 text-[#4B5563]"
      >
        <ArrowLeft size={14} /> Feed
      </button>

      <div className="gb-tactile rounded-2xl border border-black/5 bg-white p-6">
        <div className="font-mono-label flex items-center gap-2">
          <Icon size={14} weight="duotone" /> {gig.category} · {gig.subcategory}
        </div>
        <h1 className="mt-2 font-display text-3xl font-black tracking-tight">
          {gig.title}
        </h1>
        {gig.required_badge && (
          <div
            data-testid="worker-required-badge-chip"
            className="mt-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[10px] font-black tracking-widest text-white"
            style={{ backgroundColor: gig.has_required_badge ? "#10B981" : (gig.required_badge.color || "#0044FF") }}
          >
            <SealCheck size={12} weight="fill" />
            {gig.has_required_badge ? "YOU'RE CERTIFIED" : "REQUIRES"} · {gig.required_badge.name.toUpperCase()}
          </div>
        )}
        {gig.project_lite && (
          <button
            data-testid="worker-project-lite-badge"
            onClick={() => nav(`/crew/projects/${gig.project_lite.project_id}`)}
            className="mt-3 inline-flex items-center gap-1.5 bg-[#030712] px-2.5 py-1 text-[10px] font-black tracking-[0.18em] text-white hover:bg-[#1f2937]"
            title={`Tap to view all gigs in: ${gig.project_lite.title}`}
          >
            <FolderSimple size={11} weight="fill" /> PART OF PROJECT ·{" "}
            <span className="font-bold normal-case tracking-normal">
              {gig.project_lite.title}
            </span>
            <span className="ml-1">→</span>
          </button>
        )}
        {(() => {
          const pt = getPaymentTimeline(gig.payment_timeline);
          const PI = pt.icon;
          return (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span
                data-testid="worker-payment-timeline-pill"
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] ${pt.pillClass}`}
                title={pt.description}
              >
                <PI
                  size={11}
                  weight="fill"
                  className={pt.pulse ? "animate-pulse" : ""}
                />
                {pt.label}
              </span>
            </div>
          );
        })()}
        {gig.payment_timeline === "custom" && gig.payment_timeline_note && (
          <p
            data-testid="worker-payment-timeline-note"
            className="mt-2 inline-block bg-[#FFFBEB] px-3 py-1.5 text-xs text-[#92400E]"
          >
            <strong>Payment note:</strong> {gig.payment_timeline_note}
          </p>
        )}
        <div className="mt-3 text-sm text-[#4B5563] leading-relaxed">
          <MarkdownView text={gig.description} />
        </div>

        {/* Specialist project — photos + structured scope (Addendum B) */}
        {isSpecialist(gig) && (
          <>
            {(gig.photos || []).length > 0 && (
              <div className="mt-4 flex gap-2 overflow-x-auto pb-1" data-testid="specialist-gallery">
                {gig.photos.map((p, i) => (
                  <GigPhoto
                    key={p}
                    path={p}
                    className={`h-36 ${i === 0 ? "w-56" : "w-36"} shrink-0 rounded-xl object-cover`}
                  />
                ))}
              </div>
            )}
            <div className="mt-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] p-4" data-testid="specialist-scope-card">
              <div className="font-mono-label">Scope</div>
              <div className="mt-1 font-display text-lg font-bold">{scopeLine(gig)}</div>
              {gig.condition_notes && (
                <div className="mt-2 text-xs leading-relaxed text-[#4B5563]">
                  <strong>Condition:</strong> {gig.condition_notes}
                </div>
              )}
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <div className="font-mono-label text-[#10B981]">We provide</div>
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {(gig.materials_provided || []).length ? (
                      gig.materials_provided.map((m) => <li key={m}>• {m}</li>)
                    ) : (
                      <li className="text-[#9CA3AF]">Nothing — bring your setup</li>
                    )}
                  </ul>
                </div>
                <div>
                  <div className="font-mono-label text-[#0044FF]">You bring</div>
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {(gig.materials_bring || []).length ? (
                      gig.materials_bring.map((m) => <li key={m}>• {m}</li>)
                    ) : (
                      <li className="text-[#9CA3AF]">Everything is on site</li>
                    )}
                  </ul>
                </div>
              </div>
              {gig.access_notes && (
                <div className="mt-3 text-xs text-[#4B5563]">
                  <strong>Access:</strong> {gig.access_notes}
                </div>
              )}
              {gig.target_trade && (
                <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#7C3AED] px-3 py-1 text-[10px] font-black tracking-widest text-white" data-testid="target-trade-chip">
                  <Wrench size={12} weight="fill" />
                  SENT TO VERIFIED {gig.target_trade.replace(/_/g, " ").toUpperCase()} PROS
                </div>
              )}
            </div>
          </>
        )}

        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-[#E5E7EB] pt-4 text-sm">
          <Row icon={CurrencyDollar} label="Pay">
            {payLine(gig) || (
              <>
                ${Number(gig.pay_rate || 0).toFixed(2)}{" "}
                {gig.pay_type === "hourly" ? "/hr" : "flat"}
              </>
            )}
            {payReason(gig) && (
              <div className="mt-1 text-[11px] font-normal text-[#92400E]" data-testid="pay-range-reason">
                Depends on: {payReason(gig)}
              </div>
            )}
          </Row>
          <Row icon={MapPin} label="Location">{gig.location}</Row>
          <Row icon={Clock} label="When" data-testid="gig-when">
            <span
              data-testid="gig-when-value"
              className={isGigToday(gig) ? "font-bold text-[#0044FF]" : ""}
            >
              {dateLine(gig) || formatGigLong(gig)}
            </span>
            {!dateLine(gig) && (
              <span
                data-testid="gig-when-relative"
                className="ml-2 text-[10px] font-mono-label text-[#4B5563]"
              >
                {formatGigRelative(gig)}
              </span>
            )}
          </Row>
          <Row icon={Users} label="Slots">
            {gig.slots_filled}/{gig.slots}
          </Row>
          {gig.duration_hours && (
            <Row icon={Clock} label="Duration">{gig.duration_hours} hrs</Row>
          )}
          {gig.contact_phone && isApproved && (
            <Row icon={Phone} label="Contact">{gig.contact_phone}</Row>
          )}
        </div>

        {/* Worker's own role on this gig — shows above the address card when
            they have anything other than "worker" (e.g., manager / lead). */}
        {isApproved && acc?.gig_role && acc.gig_role !== "worker" && (
          <div
            data-testid="my-gig-role"
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-[#F59E0B] px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-white"
          >
            You're the {acc.gig_role}
          </div>
        )}

        {/* Full address — only shown to workers whose request is approved */}
        {isApproved && gig.address_line && (
          <div
            data-testid="full-address-card"
            className="mt-4 rounded-xl border border-[#0044FF]/30 bg-[#F0F4FF] p-3"
          >
            <div className="font-mono-label flex items-center gap-1.5 text-[#0044FF]">
              <MapPin size={12} weight="duotone" /> Full address
            </div>
            <div className="mt-1 font-display text-base font-bold">
              {gig.address_line}
            </div>
          </div>
        )}
        {!isApproved && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs text-[#4B5563]">
            <EyeSlash size={14} weight="duotone" className="mt-0.5 shrink-0" />
            <div>
              Full address is revealed after HCOB approves your request.
            </div>
          </div>
        )}
      </div>

      {/* Messaging — message HCOB admin or open the gig group chat */}
      {isApproved && (
        <div
          data-testid="worker-gig-messaging"
          className="mx-0 mt-5 grid grid-cols-2 gap-3"
        >
          <button
            type="button"
            data-testid="message-admin-btn"
            onClick={async () => {
              try {
                const { data: admins } = await api.get(
                  "/messages/eligible-users?q=admin"
                );
                const target = admins.find((u) => u.role === "admin");
                if (!target) {
                  toast.error("No admin available to message");
                  return;
                }
                const { data } = await api.post("/messages/threads/dm", {
                  user_id: target.user_id,
                });
                nav(`/crew/messages?thread=${data.thread_id}`);
              } catch (e) {
                toast.error(getErr(e));
              }
            }}
            className="flex items-center justify-center gap-2 border border-[#030712] bg-white px-3 py-3 text-xs font-bold uppercase tracking-widest hover:bg-[#030712] hover:text-white"
          >
            Message HCOB admin
          </button>
          <button
            type="button"
            data-testid="open-gig-chat-btn"
            onClick={async () => {
              try {
                const { data } = await api.get(
                  `/messages/threads/gig/${gigId}`
                );
                nav(`/crew/messages?thread=${data.thread_id}`);
              } catch (e) {
                toast.error(getErr(e));
              }
            }}
            className="flex items-center justify-center gap-2 bg-[#030712] px-3 py-3 text-xs font-bold uppercase tracking-widest text-white hover:bg-[#0044FF]"
          >
            Group chat
          </button>
        </div>
      )}

      {/* Customer chats (if any) — inline panel; PII-stripped */}
      {isApproved && <CustomerChatPanel gigId={gigId} />}

      {/* Crew — other approved workers on the same gig. First name + role
          only, surfaced only after this worker is approved. */}
      {isApproved && Array.isArray(gig.crew) && gig.crew.length > 0 && (
        <div
          data-testid="worker-crew-card"
          className="mt-5 rounded-2xl border border-black/5 bg-white p-5 gb-tactile"
        >
          <div className="font-mono-label flex items-center gap-1.5">
            <UsersThree size={12} weight="duotone" /> Your crew on this gig
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {gig.crew.map((c, i) => (
              <div
                key={i}
                data-testid={`crew-chip-${i}`}
                className="inline-flex items-center gap-2 rounded-full border border-[#E5E7EB] bg-[#F9FAFB] px-3 py-1.5"
              >
                <div className="grid h-6 w-6 place-items-center rounded-full bg-[#0044FF] text-[10px] font-black text-white">
                  {(c.first_name || "?")[0].toUpperCase()}
                </div>
                <span className="text-sm font-semibold">{c.first_name}</span>
                {c.gig_role && c.gig_role !== "worker" && (
                  <span className="ml-1 rounded bg-[#F59E0B] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">
                    {c.gig_role}
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-[#4B5563]">
            First names only. Contact your HCOB admin if you need to coordinate.
          </div>
        </div>
      )}

      {/* Project context — sibling gigs + their crew. Workers only see this
          after their request is approved. */}
      {isApproved && gig.project && (
        <div
          data-testid="worker-project-card"
          className="mt-5 rounded-2xl border border-[#030712]/10 bg-[#F9FAFB] p-5 gb-tactile"
        >
          <div className="font-mono-label flex items-center gap-1.5">
            <FolderSimple size={12} weight="duotone" /> You're part of a project
          </div>
          <div className="mt-1 font-display text-lg font-black tracking-tight">
            {gig.project.title}
          </div>
          {gig.project.client_name && (
            <div className="text-[11px] text-[#4B5563]">
              Client · {gig.project.client_name}
            </div>
          )}
          <button
            data-testid="worker-project-card-open"
            onClick={() => nav(`/crew/projects/${gig.project.project_id}`)}
            className="mt-3 inline-flex items-center gap-1 border border-[#030712] bg-[#030712] px-3 py-1.5 text-[11px] font-bold text-white hover:bg-[#1f2937]"
          >
            <FolderSimple size={12} weight="fill" /> View all project gigs →
          </button>

          {(gig.project.sibling_gigs || []).length > 0 && (
            <div className="mt-3">
              <div className="font-mono-label mb-2 text-[10px] text-[#4B5563]">
                Other gigs in this project
              </div>
              <ul className="space-y-1.5">
                {gig.project.sibling_gigs.map((s) => (
                  <li
                    key={s.gig_id}
                    data-testid={`project-sibling-${s.gig_id}`}
                    className="flex items-center justify-between border border-[#E5E7EB] bg-white px-3 py-2 text-xs"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-display text-sm font-bold">
                        {s.title}
                      </div>
                      <div className="text-[10px] text-[#4B5563]">
                        {s.category} · {s.scheduled_date || "Flexible"}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(gig.project.crew || []).length > 0 && (
            <div className="mt-4">
              <div className="font-mono-label mb-2 text-[10px] text-[#4B5563]">
                Crew you're working alongside
              </div>
              <div className="flex flex-wrap gap-2">
                {gig.project.crew.map((c, i) => (
                  <div
                    key={`${c.gig_id}-${i}`}
                    data-testid={`project-crew-chip-${i}`}
                    title={c.gig_title || ""}
                    className="inline-flex items-center gap-2 rounded-full border border-[#E5E7EB] bg-white px-3 py-1.5"
                  >
                    <div className="grid h-6 w-6 place-items-center rounded-full bg-[#030712] text-[10px] font-black text-white">
                      {(c.first_name || "?")[0].toUpperCase()}
                    </div>
                    <span className="text-sm font-semibold">{c.first_name}</span>
                    {c.gig_role && c.gig_role !== "worker" && (
                      <span className="rounded bg-[#F59E0B] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">
                        {c.gig_role}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-[10px] text-[#4B5563]">
                First names only. Contact HCOB if you need to coordinate.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Clock card — appears once admin has approved the request */}
      {isApproved && (
        <div
          data-testid="worker-clock-card"
          className={`mt-5 rounded-2xl border p-5 ${
            completed
              ? "border-[#10B981]/40 bg-[#ECFDF5]"
              : onClock
              ? "border-[#F59E0B]/50 bg-[#FFFBEB]"
              : "border-black/5 bg-white gb-tactile"
          }`}
        >
          <div className="flex items-center gap-2">
            <Timer
              size={18}
              weight={onClock ? "fill" : "duotone"}
              className={onClock ? "text-[#F59E0B]" : "text-[#030712]"}
            />
            <div className="font-mono-label">Time tracking</div>
          </div>

          {completed ? (
            <div className="mt-3">
              <div className="font-display text-3xl font-black text-[#065F46]">
                {acc.paid_hours != null
                  ? acc.paid_hours.toFixed(2)
                  : acc.hours_worked != null
                  ? acc.hours_worked.toFixed(2)
                  : "—"}{" "}
                hours paid
              </div>
              <div className="mt-1 text-xs text-[#065F46]/80">
                Logged · {new Date(acc.clock_in_at).toLocaleTimeString()} →{" "}
                {new Date(acc.clock_out_at).toLocaleTimeString()}
              </div>
              {(acc.break_minutes_applied || acc.break_minutes_effective) ? (
                <div
                  data-testid="worker-break-line"
                  className="mt-2 rounded-lg bg-white/60 px-2 py-1.5 text-[11px] text-[#065F46]"
                >
                  {`${Number(acc.hours_worked || 0).toFixed(2)}h worked – `}
                  {`${(Number(acc.break_minutes_applied ?? acc.break_minutes_effective ?? 0) / 60).toFixed(2)}h break = `}
                  <strong>
                    {`${Number(acc.paid_hours ?? Math.max(0, (acc.hours_worked || 0) - (acc.break_minutes_applied ?? acc.break_minutes_effective ?? 0) / 60)).toFixed(2)}h paid`}
                  </strong>
                </div>
              ) : null}
            </div>
          ) : onClock ? (
            <>
              <div
                data-testid="elapsed-timer"
                className="mt-3 font-display text-5xl font-black tabular-nums tracking-tight text-[#92400E]"
              >
                {elapsed}
              </div>
              <div className="mt-1 text-xs text-[#92400E]/80">
                Started at {new Date(acc.clock_in_at).toLocaleTimeString()}
              </div>
              <Button
                data-testid="clock-out-btn"
                onClick={clockOut}
                disabled={busy}
                className="mt-4 h-14 w-full rounded-2xl bg-[#EF4444] text-base font-bold tracking-wide text-white hover:bg-[#dc2626]"
              >
                <Stop size={20} weight="fill" className="mr-2" />
                {busy ? "Clocking out…" : "Clock out"}
              </Button>
            </>
          ) : (
            <>
              <div className="mt-2 text-sm text-[#4B5563]">
                Clock-in is location-verified — you must be at the job address,
                at or after the scheduled start time. We'll track your time
                automatically.
              </div>
              <Button
                data-testid="clock-in-btn"
                onClick={clockIn}
                disabled={busy}
                className="mt-4 h-14 w-full rounded-2xl bg-[#10B981] text-base font-bold tracking-wide text-white hover:bg-[#0e9971]"
              >
                <Play size={20} weight="fill" className="mr-2" />
                {busy ? "Verifying location…" : "Clock in"}
              </Button>
            </>
          )}
        </div>
      )}

      {/* Bottom actions */}
      <div className="mt-6">
        {hasAcceptance ? (
          completed ? (
            <div className="flex items-center gap-2 rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4 text-sm">
              <CheckCircle size={20} weight="fill" className="text-[#10B981]" />
              <div>
                <div className="font-bold text-[#065F46]">Assignment complete.</div>
                <div className="text-xs text-[#065F46]/80">Thanks for the work.</div>
              </div>
            </div>
          ) : isRequested ? (
            <div
              data-testid="request-pending-card"
              className="rounded-2xl border border-[#F59E0B]/40 bg-[#FFFBEB] p-5"
            >
              <div className="flex items-center gap-2 text-[#92400E]">
                <ShieldCheck size={20} weight="fill" />
                <div className="font-display text-base font-bold">
                  Request pending HCOB approval
                </div>
              </div>
              <p className="mt-2 text-xs text-[#92400E]/90">
                We've sent your request to HCOB. You'll see the full address and
                be able to clock in once they approve you for this gig.
              </p>
              <Button
                data-testid="withdraw-btn"
                onClick={withdrawRequest}
                disabled={busy}
                variant="outline"
                className="mt-4 h-11 w-full rounded-2xl border-[#92400E]/50 text-[#92400E] hover:bg-[#92400E] hover:text-white"
              >
                Cancel my request
              </Button>
            </div>
          ) : onClock ? null : (
            <Button
              data-testid="cancel-shift-btn"
              onClick={() => setCancelOpen(true)}
              disabled={busy}
              variant="outline"
              className="h-12 w-full rounded-2xl border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
            >
              Cancel my shift
            </Button>
          )
        ) : full ? (
          <Button disabled className="h-14 w-full rounded-2xl">All slots filled</Button>
        ) : !canRequest ? (
          <div
            data-testid="verification-required-card"
            className={`rounded-2xl border p-5 ${
              isBlocked
                ? "border-[#EF4444]/40 bg-[#FEF2F2]"
                : "border-[#F59E0B]/40 bg-[#FFFBEB]"
            }`}
          >
            <div
              className={`flex items-center gap-2 ${
                isBlocked ? "text-[#991B1B]" : "text-[#92400E]"
              }`}
            >
              {hasId ? (
                <ShieldCheck size={20} weight="fill" />
              ) : (
                <IdentificationCard size={20} weight="duotone" />
              )}
              <div className="font-display text-base font-bold">
                {workerStatus === "rejected"
                  ? "Account not authorized"
                  : workerStatus === "suspended"
                  ? "Account suspended"
                  : !profileComplete
                  ? "Complete your profile to request gigs"
                  : !hasId
                  ? "Upload your ID to request gigs"
                  : "Awaiting HCOB ID verification"}
              </div>
            </div>
            <p
              className={`mt-2 text-xs ${
                isBlocked ? "text-[#991B1B]/90" : "text-[#92400E]/90"
              }`}
            >
              {workerStatus === "rejected"
                ? "Your account is not authorized to request gigs. Contact HCOB if you believe this is a mistake."
                : workerStatus === "suspended"
                ? "Your account has been suspended. Contact HCOB to reinstate."
                : !profileComplete
                ? `HCOB needs ${profileMissing.length} more item${profileMissing.length === 1 ? "" : "s"} on your profile before you can request gigs.`
                : !hasId
                ? "Workers must upload a photo of a government ID and be verified by HCOB before requesting gigs."
                : "Your ID is in. An HCOB admin needs to verify it before you can request any gigs."}
            </p>
            {!isBlocked && (!profileComplete || !hasId) && (
              <Button
                data-testid="go-to-profile-btn"
                onClick={() => nav("/crew/me")}
                className="mt-4 h-12 w-full rounded-2xl bg-[#030712] text-white"
              >
                {!profileComplete ? "Complete my profile →" : "Upload my ID →"}
              </Button>
            )}
          </div>
        ) : needsBadge ? (
          <div
            data-testid="cert-required-card"
            className="rounded-2xl border border-[#0044FF]/30 bg-[#F0F4FF] p-5"
          >
            <div className="flex items-center gap-2 text-[#1D4ED8]">
              <SealCheck size={20} weight="fill" />
              <div className="font-display text-base font-bold">
                {gig.required_badge.name} certification required
              </div>
            </div>
            <p className="mt-2 text-xs text-[#1D4ED8]/90">
              This is a specialty assignment — only workers certified by HCOB
              can request it. Pass the test and upload your credentials to get
              first access to jobs like this.
            </p>
            <Button
              data-testid="get-certified-btn"
              onClick={() => nav("/crew/certifications")}
              className="mt-4 h-12 w-full rounded-2xl bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              Get certified →
            </Button>
          </div>
        ) : takesInterestOnly(gig) ? (
          <InterestPanel gig={gig} onChanged={load} />
        ) : (
          <Button
            data-testid="accept-gig-btn"
            onClick={accept}
            disabled={busy}
            className="h-14 w-full rounded-2xl bg-[#0044FF] text-base font-bold tracking-wide text-white hover:bg-[#0036cc]"
          >
            {busy ? "Sending request…" : "Request this gig"}
          </Button>
        )}
      </div>

      {/* Cancel-shift modal */}
      {cancelOpen && (
        <div
          data-testid="cancel-shift-modal"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          onClick={() => !busy && setCancelOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-3xl bg-white p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-mono-label text-[#EF4444]">Cancel shift</div>
            <h3 className="mt-1 font-display text-2xl font-black">
              Why are you cancelling?
            </h3>
            <p className="mt-2 text-xs text-[#4B5563]">
              Cancellations less than 24 hours before the gig are flagged for HCOB. If
              there&apos;s a backup worker, they&apos;ll be auto-promoted.
            </p>
            <div className="mt-4 space-y-2">
              {[
                { v: "sick", l: "Sick / not feeling well" },
                { v: "conflict", l: "Schedule conflict" },
                { v: "transportation", l: "Transportation issue" },
                { v: "other", l: "Other reason" },
              ].map((opt) => (
                <button
                  key={opt.v}
                  data-testid={`cancel-reason-${opt.v}`}
                  type="button"
                  onClick={() => setCancelReason(opt.v)}
                  className={`flex w-full items-center justify-between rounded-2xl border-2 px-4 py-3 text-left ${
                    cancelReason === opt.v
                      ? "border-[#0044FF] bg-[#F0F4FF]"
                      : "border-[#E5E7EB] hover:border-[#030712]"
                  }`}
                >
                  <span className="font-semibold">{opt.l}</span>
                  {cancelReason === opt.v && (
                    <span className="font-mono text-xs text-[#0044FF]">✓</span>
                  )}
                </button>
              ))}
            </div>
            <div className="mt-4">
              <Label className="font-mono-label">
                Anything else? <span className="text-[#9CA3AF]">(optional)</span>
              </Label>
              <textarea
                data-testid="cancel-note"
                value={cancelNote}
                onChange={(e) => setCancelNote(e.target.value)}
                rows={3}
                className="mt-2 w-full rounded-2xl border border-[#030712] bg-white p-3 text-sm"
                placeholder="e.g. Family emergency, will reach out…"
              />
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button
                onClick={() => setCancelOpen(false)}
                variant="outline"
                disabled={busy}
                className="h-12 flex-1 rounded-2xl border-[#030712]"
              >
                Never mind
              </Button>
              <Button
                data-testid="cancel-shift-confirm"
                onClick={submitCancel}
                disabled={busy || !cancelReason}
                className="h-12 flex-1 rounded-2xl bg-[#EF4444] text-white hover:bg-[#dc2626]"
              >
                {busy ? "Cancelling…" : "Cancel my shift"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Worker Agreement modal — required before requesting a gig */}
      {agreementOpen && (
        <div
          data-testid="worker-agreement-modal"
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
          onClick={() => !busy && setAgreementOpen(false)}
        >
          <div
            className="w-full max-w-lg overflow-hidden rounded-3xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b border-[#E5E7EB] bg-[#FFFBEB] px-6 py-5">
              <div className="font-mono-label text-[10px] uppercase tracking-widest text-amber-900">
                Worker Agreement · {agreementVersion}
              </div>
              <h2 className="mt-1 font-display text-2xl font-black tracking-tight text-[#030712]">
                Before you request this gig
              </h2>
              <p className="mt-2 text-sm text-[#4B5563]">
                Read each rule, then sign your name to confirm you agree. We log this with a timestamp every time you request a shift.
              </p>
            </div>
            <div className="px-6 py-5">
              <ol
                data-testid="worker-agreement-rules"
                className="space-y-3"
              >
                {agreementRules.map((r, i) => (
                  <li
                    key={i}
                    data-testid={`worker-agreement-rule-${i}`}
                    className="flex gap-3 border border-[#030712]/10 bg-[#F9FAFB] px-3 py-2.5"
                  >
                    <span className="font-mono-label flex h-6 min-w-[24px] items-center justify-center bg-[#030712] text-[10px] font-bold text-white">
                      {i + 1}
                    </span>
                    <span className="text-sm leading-relaxed text-[#030712]">{r}</span>
                  </li>
                ))}
              </ol>

              <label className="mt-5 flex items-start gap-3 cursor-pointer select-none">
                <input
                  data-testid="worker-agreement-checkbox"
                  type="checkbox"
                  checked={agreementChecked}
                  onChange={(e) => setAgreementChecked(e.target.checked)}
                  className="mt-1 h-5 w-5 accent-[#0044FF]"
                />
                <span className="text-sm leading-snug text-[#030712]">
                  I have read and agree to <strong>all {agreementRules.length} rules</strong> above. I understand that violations may result in immediate removal from the platform.
                </span>
              </label>

              <div className="mt-5">
                <Label className="font-mono-label text-[10px] uppercase tracking-widest text-[#4B5563]">
                  Sign by typing your full name
                </Label>
                <input
                  data-testid="worker-agreement-typed-name"
                  type="text"
                  value={agreementTypedName}
                  onChange={(e) => setAgreementTypedName(e.target.value)}
                  placeholder={user?.name || "Your full name"}
                  className="mt-2 h-12 w-full rounded-2xl border border-[#030712] bg-white px-4 font-display text-base text-[#030712]"
                />
                <div className="mt-1.5 text-[11px] text-[#4B5563]">
                  Must match the name on your profile: <strong>{user?.name}</strong>
                </div>
              </div>

              {/* Window gigs — pick your work day (Addendum B) */}
              {gig.date_mode === "window" && (
                <div className="mt-5">
                  <Label className="font-mono-label text-[10px] uppercase tracking-widest text-[#4B5563]">
                    Pick your work day
                  </Label>
                  <select
                    data-testid="agreement-chosen-date"
                    value={chosenDate}
                    onChange={(e) => setChosenDate(e.target.value)}
                    className="mt-2 h-12 w-full rounded-2xl border border-[#030712] bg-white px-4 text-sm"
                  >
                    <option value="">Select a day…</option>
                    {windowDays(gig).map((d) => (
                      <option key={d} value={d}>{dayLabel(d)}</option>
                    ))}
                  </select>
                  <div className="mt-1.5 text-[11px] text-[#4B5563]">
                    Arrival {gig.window_arrival_time || "09:00"} — your day locks in when HCOB approves.
                  </div>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2 border-t border-[#E5E7EB] bg-[#F9FAFB] px-6 py-4">
              <Button
                onClick={() => setAgreementOpen(false)}
                variant="outline"
                disabled={busy}
                data-testid="worker-agreement-cancel"
                className="h-12 flex-1 rounded-2xl border-[#030712]"
              >
                Never mind
              </Button>
              <Button
                data-testid="worker-agreement-submit"
                onClick={submitAgreement}
                disabled={
                  busy ||
                  !agreementChecked ||
                  (gig.date_mode === "window" && !chosenDate) ||
                  agreementTypedName.trim().toLowerCase() !==
                    (user?.name || "").trim().toLowerCase()
                }
                className="h-12 flex-1 rounded-2xl bg-[#0044FF] text-white hover:bg-[#0036cc] disabled:opacity-50"
              >
                {busy ? "Submitting…" : "I agree — request this gig"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const Row = ({ icon: I, label, children }) => (
  <div>
    <div className="font-mono-label flex items-center gap-1.5">
      <I size={13} weight="duotone" /> {label}
    </div>
    <div className="mt-1 font-semibold">{children}</div>
  </div>
);

// FRD Addendum B — "I'm Interested" flow for open-variable specialist gigs.
function InterestPanel({ gig, onChanged }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [availability, setAvailability] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/gigs/${gig.gig_id}/interest`, { note, availability });
      toast.success("Hand raised — HCOB will follow up with final details");
      setOpen(false);
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setBusy(true);
    try {
      await api.delete(`/gigs/${gig.gig_id}/interest`);
      toast.success("Interest withdrawn");
      onChanged();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (gig.my_interest) {
    return (
      <div data-testid="interest-confirmation" className="rounded-2xl border border-[#7C3AED]/30 bg-[#F5F3FF] p-5">
        <div className="flex items-center gap-2 text-[#6D28D9]">
          <HandWaving size={20} weight="fill" />
          <div className="font-display text-base font-bold">You raised your hand</div>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-[#6D28D9]/90">
          HCOB reviews interested pros and sends a direct offer with the locked
          price and confirmed date. Accepting that offer books the job.
        </p>
        {gig.my_interest.note && (
          <p className="mt-2 text-xs text-[#4B5563]">Your note: "{gig.my_interest.note}"</p>
        )}
        <Button
          data-testid="withdraw-interest-btn"
          variant="outline"
          disabled={busy}
          onClick={withdraw}
          className="mt-4 h-11 w-full rounded-2xl border-[#6D28D9] text-[#6D28D9]"
        >
          {busy ? "…" : "Withdraw interest"}
        </Button>
      </div>
    );
  }

  if (!open) {
    return (
      <div>
        <Button
          data-testid="interested-btn"
          onClick={() => setOpen(true)}
          className="h-14 w-full rounded-2xl bg-[#7C3AED] text-base font-bold tracking-wide text-white hover:bg-[#6D28D9]"
        >
          <HandWaving size={18} weight="fill" className="mr-2" /> I'm Interested
        </Button>
        <p className="mt-2 text-center text-[11px] text-[#4B5563]">
          {gig.pay_mode === "range"
            ? "Price locks when HCOB sends you a direct offer."
            : "Scheduling is flexible — HCOB confirms the date with you."}{" "}
          No commitment yet.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="interest-form" className="rounded-2xl border border-[#7C3AED]/40 bg-white p-5">
      <div className="font-display text-base font-bold">Raise your hand</div>
      <div className="mt-3">
        <Label className="font-mono-label text-[10px] uppercase tracking-widest">
          Note to HCOB (optional)
        </Label>
        <textarea
          data-testid="interest-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          maxLength={300}
          placeholder='e.g. "Done 20+ of these — have all the tools"'
          className="mt-2 w-full rounded-xl border border-[#E5E7EB] p-3 text-sm"
        />
      </div>
      <div className="mt-3">
        <Label className="font-mono-label text-[10px] uppercase tracking-widest">
          Your availability (optional)
        </Label>
        <input
          data-testid="interest-availability"
          value={availability}
          onChange={(e) => setAvailability(e.target.value)}
          maxLength={200}
          placeholder='e.g. "Weekdays after 3pm"'
          className="mt-2 h-11 w-full rounded-xl border border-[#E5E7EB] px-3 text-sm"
        />
      </div>
      <div className="mt-4 flex gap-2">
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => setOpen(false)}
          className="h-11 flex-1 rounded-2xl border-[#E5E7EB]"
        >
          Back
        </Button>
        <Button
          data-testid="interest-submit"
          disabled={busy}
          onClick={submit}
          className="h-11 flex-1 rounded-2xl bg-[#7C3AED] text-white hover:bg-[#6D28D9]"
        >
          {busy ? "Sending…" : "Send interest"}
        </Button>
      </div>
    </div>
  );
}
