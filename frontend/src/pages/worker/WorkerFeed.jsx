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
  const status = user?.worker_status || "approved";
  const isPending = status === "pending";
  const isBlocked = status === "rejected" || status === "suspended";
  const needsId = status === "approved" && !user?.id_image_path;
  const awaitingVerification =
    status === "approved" && !!user?.id_image_path && !user?.id_verified;
  const showBanner = isPending || isBlocked || needsId || awaitingVerification;

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
    : needsId
    ? {
        title: "Upload your ID to claim gigs",
        sub: "You can browse, but you need a verified ID before accepting.",
      }
    : {
        title: "Awaiting HCOB verification",
        sub: "Your ID is in review. You'll be able to accept gigs as soon as HCOB verifies you.",
      };

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

      {showBanner && (
        <button
          data-testid="verification-banner"
          onClick={() => !isBlocked && nav("/app/profile")}
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
            const acc = g.my_acceptance;
            const isRequested = acc?.status === "requested";
            const isApproved =
              acc?.status === "accepted" ||
              acc?.status === "on_the_clock" ||
              acc?.status === "completed";
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
                  {isApproved ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      <CheckCircle size={10} weight="fill" /> APPROVED
                    </span>
                  ) : isRequested ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#F59E0B] px-3 py-1 text-[10px] font-bold tracking-widest text-white">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                      REQUESTED
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
