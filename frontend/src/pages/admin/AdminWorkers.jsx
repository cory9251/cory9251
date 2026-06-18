import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { StarsDisplay } from "@/components/admin/RatingDialog";
import MessageUserButton from "@/components/messages/MessageUserButton";
import {
  CheckCircle,
  IdentificationCard,
  UserCircle,
  ClockCounterClockwise,
  Prohibit,
  PauseCircle,
  Funnel,
  X,
  MagnifyingGlass,
  MapPin,
  Star,
  Lightning,
  Warning,
  CurrencyDollar,
} from "@phosphor-icons/react";

const TABS = [
  { key: "all", label: "All" },
  { key: "approved", label: "Approved" },
  { key: "pending", label: "Pending" },
  { key: "rejected", label: "Rejected" },
  { key: "suspended", label: "Suspended" },
];

const SKILL_OPTIONS = [
  { value: "deep_cleaning", label: "Deep cleaning" },
  { value: "routine_cleaning", label: "Routine cleaning" },
  { value: "moveouts", label: "Move-outs" },
  { value: "detailing", label: "Detailing" },
  { value: "window_cleaning", label: "Window cleaning" },
  { value: "carpet_cleaning", label: "Carpet cleaning" },
  { value: "post_construction", label: "Post-construction" },
  { value: "hourly_labor", label: "Hourly labor" },
  { value: "heavy_lifting", label: "Heavy lifting" },
  { value: "forklift", label: "Forklift" },
  { value: "moving", label: "Moving" },
  { value: "warehouse", label: "Warehouse" },
  { value: "landscaping", label: "Landscaping" },
  { value: "painting", label: "Painting" },
  { value: "driving", label: "Driving" },
  { value: "delivery", label: "Delivery" },
  { value: "cdl", label: "CDL" },
  { value: "fast_learner", label: "Fast learner" },
  { value: "bilingual", label: "Bilingual" },
  { value: "team_lead", label: "Team lead" },
];

const AVAIL_OPTIONS = [
  { value: "weekdays", label: "Weekdays" },
  { value: "weekends", label: "Weekends" },
  { value: "mornings", label: "Mornings" },
  { value: "evenings", label: "Evenings" },
  { value: "overnight", label: "Overnight" },
  { value: "full_time", label: "Full-time" },
];

/**
 * Truthful status badge. Renders:
 *   • ACTIVE (green)   — admin-approved AND id-verified AND profile-complete.
 *                        These are the only workers who can actually book a gig.
 *   • SETUP NEEDED     — admin-approved but blocked by missing ID / profile.
 *                        Visually distinct from PENDING so admins know it's a
 *                        worker-side gap, not awaiting their review.
 *   • PENDING / REJECTED / SUSPENDED — unchanged.
 */
function StatusBadge({ worker }) {
  const status = worker?.worker_status || "approved";
  const fullyActive = !!worker?.fully_active;
  const blockers = worker?.approval_blockers || [];
  // If the backend hasn't surfaced approval_blockers yet, fall back to the
  // raw status so we don't paint everyone red on stale clients.
  const inferredFullyActive =
    worker?.fully_active === undefined
      ? status === "approved"
      : fullyActive;

  if (status === "approved" && !inferredFullyActive) {
    return (
      <span
        title={blockers.join(" · ") || "Profile or ID not complete"}
        className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-1 text-[10px] font-bold tracking-widest text-white"
      >
        <Warning size={10} weight="fill" /> SETUP NEEDED
      </span>
    );
  }

  const m = {
    pending: { bg: "bg-[#F59E0B]", icon: ClockCounterClockwise, label: "PENDING" },
    approved: { bg: "bg-[#10B981]", icon: CheckCircle, label: "ACTIVE" },
    rejected: { bg: "bg-[#EF4444]", icon: Prohibit, label: "REJECTED" },
    suspended: { bg: "bg-[#4B5563]", icon: PauseCircle, label: "SUSPENDED" },
  }[status] || { bg: "bg-[#4B5563]", icon: UserCircle, label: status.toUpperCase() };
  const Icon = m.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-bold tracking-widest text-white ${m.bg}`}
    >
      <Icon size={10} weight="fill" /> {m.label}
    </span>
  );
}

const SKILL_LABEL = Object.fromEntries(SKILL_OPTIONS.map((s) => [s.value, s.label]));

export default function AdminWorkers() {
  const [workers, setWorkers] = useState([]);
  const [params, setParams] = useSearchParams();
  const tab = params.get("status") || "all";
  const [skills, setSkills] = useState([]);
  const [availability, setAvailability] = useState([]);
  const [zipCode, setZipCode] = useState("");
  const [zipPrefix, setZipPrefix] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [profileComplete, setProfileComplete] = useState("");
  const [minRating, setMinRating] = useState("");
  const [search, setSearch] = useState("");
  const [availableNow, setAvailableNow] = useState(false);
  const [payoutMissing, setPayoutMissing] = useState(
    () => params.get("payout_status") === "missing"
  );
  const [showFilters, setShowFilters] = useState(false);
  const nav = useNavigate();

  const load = async () => {
    try {
      const q = {};
      if (tab !== "all") q.status = tab;
      if (skills.length) q.skills = skills.join(",");
      if (availability.length) q.availability = availability.join(",");
      if (zipCode.trim()) q.zip_code = zipCode.trim();
      else if (zipPrefix.trim()) q.zip_prefix = zipPrefix.trim();
      if (vehicle) q.vehicle = vehicle;
      if (profileComplete === "complete") q.profile_complete = true;
      else if (profileComplete === "incomplete") q.profile_complete = false;
      if (minRating) q.min_rating = minRating;
      if (availableNow) q.available_now = true;
      if (payoutMissing) q.payout_status = "missing";
      if (search.trim()) q.search = search.trim();
      const { data } = await api.get("/admin/workers", { params: q });
      setWorkers(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [tab, skills, availability, zipCode, zipPrefix, vehicle, profileComplete, minRating, availableNow, payoutMissing, search]);

  const toggleArr = (arr, setter, v) =>
    setter(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  const clearFilters = () => {
    setSkills([]);
    setAvailability([]);
    setZipCode("");
    setZipPrefix("");
    setVehicle("");
    setProfileComplete("");
    setMinRating("");
    setAvailableNow(false);
    setPayoutMissing(false);
    setSearch("");
  };

  const activeFilterCount =
    skills.length +
    availability.length +
    (zipCode ? 1 : 0) +
    (zipPrefix ? 1 : 0) +
    (vehicle ? 1 : 0) +
    (profileComplete ? 1 : 0) +
    (minRating ? 1 : 0) +
    (availableNow ? 1 : 0) +
    (payoutMissing ? 1 : 0) +
    (search ? 1 : 0);

  return (
    <div data-testid="admin-workers">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">Roster</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          Workers
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`workers-tab-${t.key}`}
            onClick={() => setParams(t.key === "all" ? {} : { status: t.key })}
            className={`px-3 py-1.5 text-xs font-bold tracking-widest uppercase ${
              tab === t.key
                ? "bg-[#030712] text-white"
                : "border border-[#E5E7EB] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
            }`}
          >
            {t.label}
          </button>
        ))}
        <span className="ml-auto font-mono-label">{workers.length} shown</span>
      </div>

      {/* Filters strip */}
      <div className="border-b border-[#E5E7EB] px-6 py-3 md:px-10">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <MagnifyingGlass
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4B5563]"
            />
            <Input
              data-testid="workers-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, email, phone"
              className="h-10 rounded-none border-[#030712] pl-9"
            />
          </div>
          <Button
            data-testid="toggle-filters-btn"
            variant="outline"
            onClick={() => setShowFilters((s) => !s)}
            className="h-10 rounded-none border-[#030712]"
          >
            <Funnel size={14} className="mr-2" weight="duotone" />
            Filters
            {activeFilterCount > 0 && (
              <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[#0044FF] px-1.5 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
          </Button>
          <button
            type="button"
            data-testid="filter-available-now"
            onClick={() => setAvailableNow((v) => !v)}
            className={`inline-flex h-10 items-center gap-1.5 border px-3 text-[10px] font-bold uppercase tracking-widest transition-colors ${
              availableNow
                ? "border-[#10B981] bg-[#10B981] text-white"
                : "border-[#10B981] bg-white text-[#065F46] hover:bg-[#ECFDF5]"
            }`}
            title="Show only workers who flipped 'I'm available now'"
          >
            <Lightning
              size={12}
              weight="fill"
              className={availableNow ? "animate-pulse" : ""}
            />
            Available now
          </button>
          <button
            type="button"
            data-testid="filter-payout-missing"
            onClick={() => setPayoutMissing((v) => !v)}
            className={`inline-flex h-10 items-center gap-1.5 border px-3 text-[10px] font-bold uppercase tracking-widest transition-colors ${
              payoutMissing
                ? "border-[#F59E0B] bg-[#F59E0B] text-white"
                : "border-[#F59E0B] bg-white text-[#92400E] hover:bg-[#FFFBEB]"
            }`}
            title="Show only workers without a payout method on file"
          >
            <CurrencyDollar size={12} weight="fill" />
            Missing payout
          </button>
          {activeFilterCount > 0 && (
            <button
              data-testid="clear-filters-btn"
              onClick={clearFilters}
              className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-widest text-[#EF4444]"
            >
              <X size={12} /> Clear
            </button>
          )}
        </div>

        {showFilters && (
          <div
            data-testid="filters-panel"
            className="mt-4 grid grid-cols-1 gap-4 border border-[#E5E7EB] bg-[#F9FAFB] p-4 md:grid-cols-2 lg:grid-cols-3"
          >
            <div>
              <div className="font-mono-label mb-2">Skills</div>
              <div className="flex flex-wrap gap-1.5">
                {SKILL_OPTIONS.map((s) => (
                  <FilterChip
                    key={s.value}
                    testId={`filter-skill-${s.value}`}
                    active={skills.includes(s.value)}
                    onClick={() => toggleArr(skills, setSkills, s.value)}
                  >
                    {s.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div>
              <div className="font-mono-label mb-2">Availability</div>
              <div className="flex flex-wrap gap-1.5">
                {AVAIL_OPTIONS.map((a) => (
                  <FilterChip
                    key={a.value}
                    testId={`filter-avail-${a.value}`}
                    active={availability.includes(a.value)}
                    onClick={() => toggleArr(availability, setAvailability, a.value)}
                  >
                    {a.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div>
              <div className="font-mono-label mb-2">Vehicle</div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { value: "any", label: "Any vehicle" },
                  { value: "car", label: "Car" },
                  { value: "truck", label: "Truck" },
                  { value: "cdl", label: "CDL" },
                ].map((v) => (
                  <FilterChip
                    key={v.value}
                    testId={`filter-vehicle-${v.value}`}
                    active={vehicle === v.value}
                    onClick={() => setVehicle(vehicle === v.value ? "" : v.value)}
                  >
                    {v.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div>
              <div className="font-mono-label mb-2">ZIP code (exact)</div>
              <Input
                data-testid="filter-zip-code"
                value={zipCode}
                onChange={(e) => {
                  setZipCode(e.target.value.replace(/\D/g, "").slice(0, 5));
                  if (e.target.value) setZipPrefix("");
                }}
                inputMode="numeric"
                maxLength={5}
                placeholder="94110"
                className="h-10 rounded-none border-[#030712]"
              />
            </div>

            <div>
              <div className="font-mono-label mb-2">ZIP starts with (nearby)</div>
              <Input
                data-testid="filter-zip-prefix"
                value={zipPrefix}
                onChange={(e) => {
                  setZipPrefix(e.target.value.replace(/\D/g, "").slice(0, 3));
                  if (e.target.value) setZipCode("");
                }}
                inputMode="numeric"
                maxLength={3}
                placeholder="941 (~SF area)"
                className="h-10 rounded-none border-[#030712]"
              />
            </div>

            <div>
              <div className="font-mono-label mb-2">Profile</div>
              <div className="flex flex-wrap gap-1.5">
                <FilterChip
                  testId="filter-profile-complete"
                  active={profileComplete === "complete"}
                  onClick={() =>
                    setProfileComplete(
                      profileComplete === "complete" ? "" : "complete"
                    )
                  }
                >
                  Complete
                </FilterChip>
                <FilterChip
                  testId="filter-profile-incomplete"
                  active={profileComplete === "incomplete"}
                  onClick={() =>
                    setProfileComplete(
                      profileComplete === "incomplete" ? "" : "incomplete"
                    )
                  }
                >
                  Incomplete
                </FilterChip>
              </div>
            </div>

            <div>
              <div className="font-mono-label mb-2">Min rating</div>
              <div className="flex flex-wrap gap-1.5">
                {[3, 4, 4.5, 5].map((r) => (
                  <FilterChip
                    key={r}
                    testId={`filter-min-rating-${r}`}
                    active={minRating === String(r)}
                    onClick={() =>
                      setMinRating(minRating === String(r) ? "" : String(r))
                    }
                  >
                    <Star size={9} weight="fill" className="mr-0.5 inline" />
                    {r}+
                  </FilterChip>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* List */}
      <div className="px-6 py-6 md:px-10">
        {workers.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No workers match these filters.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {workers.map((w) => (
              <div
                key={w.user_id}
                data-testid={`worker-card-${w.user_id}`}
                role="button"
                tabIndex={0}
                onClick={() => nav(`/ops/workers/${w.user_id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    nav(`/ops/workers/${w.user_id}`);
                  }
                }}
                className="relative cursor-pointer border border-[#E5E7EB] bg-white p-5 text-left hover:border-[#030712] focus:border-[#030712] focus:outline-none"
              >
                <div className="absolute right-3 top-3">
                  <MessageUserButton
                    userId={w.user_id}
                    name={w.name}
                    variant="icon"
                    testId={`message-worker-${w.user_id}`}
                  />
                </div>
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center bg-[#F0F4FF] text-[#0044FF]">
                    <UserCircle size={28} weight="duotone" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-display text-lg font-bold">
                      {w.name}
                    </div>
                    <div className="truncate text-xs text-[#4B5563]">{w.email}</div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <StatusBadge worker={w} />
                  {w.available_now && (
                    <span
                      data-testid={`available-badge-${w.user_id}`}
                      className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-1 text-[10px] font-bold tracking-widest text-white"
                    >
                      <Lightning size={10} weight="fill" className="animate-pulse" />
                      AVAILABLE NOW
                    </span>
                  )}
                  {w.id_image_path ? (
                    w.id_verified ? (
                      <span className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#065F46]">
                        <CheckCircle size={10} weight="fill" /> ID OK
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#92400E]">
                        <IdentificationCard size={10} /> ID PENDING
                      </span>
                    )
                  ) : (
                    <span className="bg-[#E5E7EB] px-2 py-1 text-[10px] font-bold tracking-widest text-[#4B5563]">
                      NO ID
                    </span>
                  )}
                  {!w.payout_method && (
                    <span
                      data-testid={`payout-missing-badge-${w.user_id}`}
                      className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#92400E]"
                      title="No payout method on file — admin can't send pay yet"
                    >
                      <CurrencyDollar size={10} weight="fill" /> NO PAYOUT
                    </span>
                  )}
                  {w.payout_method && (
                    <span
                      data-testid={`payout-set-badge-${w.user_id}`}
                      className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-1 text-[10px] font-bold tracking-widest text-[#065F46]"
                      title={`${w.payout_method.toUpperCase()} · ${w.payout_handle || ""}`}
                    >
                      <CurrencyDollar size={10} weight="fill" />{" "}
                      {w.payout_method === "zelle"
                        ? "ZELLE"
                        : w.payout_method === "apple_cash"
                        ? "APPLE CASH"
                        : "CHIME"}
                    </span>
                  )}
                </div>

                {/* Profile completion */}
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px]">
                  {w.profile_complete ? (
                    <span className="inline-flex items-center gap-1 bg-[#10B981]/15 px-2 py-1 font-bold tracking-widest text-[#065F46]">
                      <CheckCircle size={9} weight="fill" /> PROFILE OK
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 bg-[#F59E0B]/15 px-2 py-1 font-bold tracking-widest text-[#92400E]">
                      PROFILE{" "}
                      {(w.profile_missing_fields?.length || 0)} LEFT
                    </span>
                  )}
                  {w.zip_code && (
                    <span className="inline-flex items-center gap-1 text-[#4B5563]">
                      <MapPin size={10} weight="duotone" />
                      {w.zip_code}
                    </span>
                  )}
                </div>

                {/* Rating stars */}
                <div className="mt-2">
                  <StarsDisplay
                    value={w.rating_avg}
                    count={w.rating_count}
                    size={11}
                  />
                </div>

                {/* Skills */}
                {Array.isArray(w.skills) && w.skills.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {w.skills.slice(0, 3).map((s) => (
                      <span
                        key={s}
                        className="bg-[#F0F4FF] px-2 py-0.5 text-[10px] font-semibold text-[#0044FF]"
                      >
                        {SKILL_LABEL[s] || s}
                      </span>
                    ))}
                    {w.skills.length > 3 && (
                      <span className="text-[10px] text-[#4B5563]">
                        +{w.skills.length - 3}
                      </span>
                    )}
                  </div>
                )}

                <div className="mt-3 font-mono-label">
                  Joined {new Date(w.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({ active, onClick, children, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
        active
          ? "border-[#0044FF] bg-[#0044FF] text-white"
          : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#0044FF]"
      }`}
    >
      {children}
    </button>
  );
}
