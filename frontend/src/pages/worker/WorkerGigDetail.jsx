import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
} from "@phosphor-icons/react";

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
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/accept`);
      toast.success("Gig accepted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/withdraw`);
      toast.success("Withdrew from gig");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const clockIn = async () => {
    setBusy(true);
    try {
      await api.post(`/gigs/${gigId}/clock-in`);
      toast.success("Clocked in — timer running");
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
  const accepted = !!acc;
  const onClock = !!acc?.clock_in_at && !acc?.clock_out_at;
  const completed = !!acc?.clock_out_at;
  const full = gig.slots_filled >= gig.slots && !accepted;

  // Status & verification gates — only enforced for unaccepted workers
  const workerStatus = user?.worker_status || "approved";
  const isPending = workerStatus === "pending";
  const isBlocked = workerStatus === "rejected" || workerStatus === "suspended";
  const hasId = !!user?.id_image_path;
  const verified = !!user?.id_verified;
  const canAccept = !isPending && !isBlocked && hasId && verified;

  return (
    <div className="px-5 py-6" data-testid="worker-gig-detail">
      <button
        onClick={() => nav("/app")}
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
        <p className="mt-3 text-sm text-[#4B5563] leading-relaxed">
          {gig.description}
        </p>

        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-[#E5E7EB] pt-4 text-sm">
          <Row icon={CurrencyDollar} label="Pay">
            ${Number(gig.pay_rate).toFixed(2)}{" "}
            {gig.pay_type === "hourly" ? "/hr" : "flat"}
          </Row>
          <Row icon={MapPin} label="Location">{gig.location}</Row>
          <Row icon={Clock} label="When">{gig.scheduled_date}</Row>
          <Row icon={Users} label="Slots">
            {gig.slots_filled}/{gig.slots}
          </Row>
          {gig.duration_hours && (
            <Row icon={Clock} label="Duration">{gig.duration_hours} hrs</Row>
          )}
          {gig.contact_phone && accepted && (
            <Row icon={Phone} label="Contact">{gig.contact_phone}</Row>
          )}
        </div>

        {/* Full address — only shown to workers who have accepted */}
        {accepted && gig.address_line && (
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
        {!accepted && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs text-[#4B5563]">
            <EyeSlash size={14} weight="duotone" className="mt-0.5 shrink-0" />
            <div>
              Full address is revealed after you accept this gig.
            </div>
          </div>
        )}
      </div>

      {/* Clock card — appears once accepted */}
      {accepted && (
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
                {acc.hours_worked != null ? acc.hours_worked.toFixed(2) : "—"} hours
              </div>
              <div className="mt-1 text-xs text-[#065F46]/80">
                Logged · {new Date(acc.clock_in_at).toLocaleTimeString()} →{" "}
                {new Date(acc.clock_out_at).toLocaleTimeString()}
              </div>
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
                Tap clock-in when you arrive on site. We'll track your time
                automatically.
              </div>
              <Button
                data-testid="clock-in-btn"
                onClick={clockIn}
                disabled={busy}
                className="mt-4 h-14 w-full rounded-2xl bg-[#10B981] text-base font-bold tracking-wide text-white hover:bg-[#0e9971]"
              >
                <Play size={20} weight="fill" className="mr-2" />
                {busy ? "Clocking in…" : "Clock in"}
              </Button>
            </>
          )}
        </div>
      )}

      {/* Bottom actions */}
      <div className="mt-6">
        {accepted ? (
          completed ? (
            <div className="flex items-center gap-2 rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4 text-sm">
              <CheckCircle size={20} weight="fill" className="text-[#10B981]" />
              <div>
                <div className="font-bold text-[#065F46]">Gig complete.</div>
                <div className="text-xs text-[#065F46]/80">Thanks for the work.</div>
              </div>
            </div>
          ) : onClock ? null : (
            <Button
              data-testid="withdraw-btn"
              onClick={withdraw}
              disabled={busy}
              variant="outline"
              className="h-12 w-full rounded-2xl border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
            >
              Withdraw from gig
            </Button>
          )
        ) : full ? (
          <Button disabled className="h-14 w-full rounded-2xl">All slots filled</Button>
        ) : !canAccept ? (
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
              {isBlocked ? (
                <ShieldCheck size={20} weight="fill" />
              ) : isPending ? (
                <ShieldCheck size={20} weight="fill" />
              ) : hasId ? (
                <ShieldCheck size={20} weight="fill" />
              ) : (
                <IdentificationCard size={20} weight="duotone" />
              )}
              <div className="font-display text-base font-bold">
                {workerStatus === "rejected"
                  ? "Application not approved"
                  : workerStatus === "suspended"
                  ? "Account suspended"
                  : isPending
                  ? "Application under review"
                  : hasId
                  ? "Awaiting HCOB verification"
                  : "Upload your ID to claim gigs"}
              </div>
            </div>
            <p
              className={`mt-2 text-xs ${
                isBlocked ? "text-[#991B1B]/90" : "text-[#92400E]/90"
              }`}
            >
              {workerStatus === "rejected"
                ? "HCOB did not approve your application. Contact HCOB if you believe this is a mistake."
                : workerStatus === "suspended"
                ? "Your account has been suspended. Contact HCOB to reinstate."
                : isPending
                ? "An HCOB admin must approve your account before you can claim gigs. You'll be able to claim this gig as soon as you're approved."
                : hasId
                ? "Your ID is in. An HCOB admin needs to verify your ID before you can accept any gigs."
                : "Workers must upload a photo of a government ID and be verified by HCOB before claiming gigs."}
            </p>
            {!isBlocked && !isPending && !hasId && (
              <Button
                data-testid="go-to-profile-btn"
                onClick={() => nav("/app/profile")}
                className="mt-4 h-12 w-full rounded-2xl bg-[#030712] text-white"
              >
                Upload my ID →
              </Button>
            )}
          </div>
        ) : (
          <Button
            data-testid="accept-gig-btn"
            onClick={accept}
            disabled={busy}
            className="h-14 w-full rounded-2xl bg-[#0044FF] text-base font-bold tracking-wide text-white hover:bg-[#0036cc]"
          >
            {busy ? "Accepting…" : "Accept this gig"}
          </Button>
        )}
      </div>
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
