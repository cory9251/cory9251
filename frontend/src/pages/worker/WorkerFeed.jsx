import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
} from "@phosphor-icons/react";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function WorkerFeed() {
  const [gigs, setGigs] = useState([]);
  const [category, setCategory] = useState("all");
  const nav = useNavigate();
  const { user } = useAuth();
  const needsId = !user?.id_image_path;
  const awaitingVerification = !!user?.id_image_path && !user?.id_verified;

  const load = async () => {
    try {
      const params = {};
      if (category !== "all") params.category = category;
      const { data } = await api.get("/gigs", { params });
      setGigs(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [category]);

  return (
    <div className="px-5 py-6" data-testid="worker-feed">
      <div className="font-mono-label">Available now</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        Open gigs
      </h1>

      {(needsId || awaitingVerification) && (
        <button
          data-testid="verification-banner"
          onClick={() => nav("/app/profile")}
          className="mt-4 flex w-full items-start gap-3 rounded-2xl border border-[#F59E0B]/40 bg-[#FFFBEB] p-4 text-left hover:bg-[#FEF3C7]"
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#F59E0B] text-white">
            {needsId ? (
              <IdentificationCard size={20} weight="duotone" />
            ) : (
              <ShieldCheck size={20} weight="fill" />
            )}
          </div>
          <div className="flex-1">
            <div className="font-display text-sm font-bold text-[#92400E]">
              {needsId ? "Upload your ID to claim gigs" : "Awaiting HCOB verification"}
            </div>
            <div className="mt-0.5 text-xs text-[#92400E]/80">
              {needsId
                ? "You can browse, but you need a verified ID before accepting."
                : "Your ID is in review. You'll be able to accept gigs as soon as HCOB verifies you."}
            </div>
          </div>
          <CaretRight size={18} className="mt-1 shrink-0 text-[#92400E]" />
        </button>
      )}

      <div className="mt-4">
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger
            data-testid="worker-category-filter"
            className="h-11 w-full rounded-xl border-[#E5E7EB] bg-white"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            <SelectItem value="cleaning">Cleaning</SelectItem>
            <SelectItem value="labor">Labor</SelectItem>
            <SelectItem value="driver">Driver / Ride</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="mt-5 space-y-4">
        {gigs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E7EB] bg-white p-10 text-center text-sm text-[#4B5563]">
            No open gigs right now. Check back soon.
          </div>
        ) : (
          gigs.map((g) => {
            const Icon = CAT_ICON[g.category];
            const accepted = !!g.my_acceptance;
            return (
              <button
                key={g.gig_id}
                data-testid={`feed-gig-${g.gig_id}`}
                onClick={() => nav(`/app/gigs/${g.gig_id}`)}
                className="gb-tactile w-full rounded-2xl border border-black/5 bg-white p-5 text-left transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 font-mono-label">
                      <Icon size={14} weight="duotone" />
                      {g.category} · {g.subcategory || "general"}
                    </div>
                    <h3 className="mt-2 font-display text-xl font-bold leading-snug">
                      {g.title}
                    </h3>
                  </div>
                  {accepted ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      <CheckCircle size={10} weight="fill" /> ACCEPTED
                    </span>
                  ) : (
                    <span className="rounded-full bg-[#0044FF] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      OPEN
                    </span>
                  )}
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3 border-t border-[#E5E7EB] pt-3 text-xs">
                  <Bit
                    icon={CurrencyDollar}
                    value={`$${Number(g.pay_rate).toFixed(0)}${
                      g.pay_type === "hourly" ? "/hr" : ""
                    }`}
                  />
                  <Bit icon={MapPin} value={g.location} />
                  <Bit icon={Clock} value={g.scheduled_date} />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

const Bit = ({ icon: I, value }) => (
  <div className="flex items-start gap-1.5 text-[#4B5563]">
    <I size={14} weight="duotone" className="mt-px shrink-0" />
    <span className="truncate font-semibold text-[#030712]">{value}</span>
  </div>
);
