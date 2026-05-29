import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
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
} from "@phosphor-icons/react";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function WorkerGigDetail() {
  const { gigId } = useParams();
  const nav = useNavigate();
  const [gig, setGig] = useState(null);
  const [busy, setBusy] = useState(false);

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

  if (!gig) return <div className="p-10 font-mono-label">Loading…</div>;

  const Icon = CAT_ICON[gig.category];
  const accepted = !!gig.my_acceptance;
  const full = gig.slots_filled >= gig.slots && !accepted;

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
          {gig.contact_phone && (
            <Row icon={Phone} label="Contact">{gig.contact_phone}</Row>
          )}
        </div>
      </div>

      <div className="mt-6">
        {accepted ? (
          <>
            <div className="mb-3 flex items-center gap-2 rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4 text-sm">
              <CheckCircle size={20} weight="fill" className="text-[#10B981]" />
              <div>
                <div className="font-bold text-[#065F46]">You're on this gig.</div>
                <div className="text-xs text-[#065F46]/80">
                  Accepted {new Date(gig.my_acceptance.accepted_at).toLocaleString()}
                </div>
              </div>
            </div>
            <Button
              data-testid="withdraw-btn"
              onClick={withdraw}
              disabled={busy}
              variant="outline"
              className="h-14 w-full rounded-2xl border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
            >
              Withdraw
            </Button>
          </>
        ) : full ? (
          <Button disabled className="h-14 w-full rounded-2xl">All slots filled</Button>
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
