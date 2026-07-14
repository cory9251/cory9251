import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";
import {
  HardHat,
  Toolbox,
  CheckCircle,
  Warning,
  Car,
  Truck,
  CaretDown,
  CaretUp,
  Camera,
  X,
  SealCheck,
  ArrowLeft,
  ArrowRight,
  Trash,
} from "@phosphor-icons/react";

const EXPERIENCE_LABELS = {
  none: "No experience",
  "0_1_yr": "Under 1 year",
  "1_3_yr": "1–3 years",
  "3_plus_yr": "3+ years",
};
const AVAILABILITY_LABELS = {
  weekdays: "Weekdays",
  weekends: "Weekends",
  mornings: "Mornings",
  evenings: "Evenings",
  overnight: "Overnight",
  full_time: "Full-time",
};
const STATUS_PILL = {
  incomplete: { bg: "#F59E0B", label: "INCOMPLETE" },
  pending: { bg: "#0044FF", label: "PENDING VERIFICATION" },
  verified: { bg: "#10B981", label: "VERIFIED" },
  returned: { bg: "#EF4444", label: "RETURNED" },
};

function claimErrors(c, tdef) {
  const errs = [];
  const checked = Object.entries(c.checklist || {}).filter(([, v]) => v).map(([k]) => k);
  if (!checked.length) errs.push("Check at least one item you own");
  for (const it of tdef.checklist || []) {
    if (checked.includes(it.key) && it.detail_label && !String(c.detail_fields?.[it.key] || "").trim())
      errs.push(`${it.label}: add ${it.detail_label}`);
  }
  if (tdef.licensed && !String(c.license_number || "").trim()) errs.push("License number required");
  if (!(c.photos || []).length) errs.push(tdef.licensed ? "Upload your license" : "Add at least one equipment photo");
  if (!c.experience) errs.push("Pick your experience level");
  return errs;
}

export default function WorkerQuestionnaire({ onboarding = false }) {
  const { user, checkAuth } = useAuth();
  const nav = useNavigate();
  const [options, setOptions] = useState(null);
  const [defs, setDefs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);

  const [workClasses, setWorkClasses] = useState([]);
  const [generalSkills, setGeneralSkills] = useState([]);
  const [generalExperience, setGeneralExperience] = useState("");
  const [attributes, setAttributes] = useState([]);
  const [bilingualLanguages, setBilingualLanguages] = useState("");
  const [availability, setAvailability] = useState([]);
  const [hasCar, setHasCar] = useState(false);
  const [hasTruck, setHasTruck] = useState(false);
  const [claims, setClaims] = useState({});
  const [badges, setBadges] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const [{ data: opt }, { data: d }, { data: cl }, { data: b }] = await Promise.all([
          api.get("/profile/options"),
          api.get("/trades/definitions"),
          api.get("/profile/trades"),
          api.get("/worker/badges"),
        ]);
        setOptions(opt);
        setDefs(d);
        setBadges(b || []);
        const map = {};
        for (const c of cl.claims || []) map[c.trade] = c;
        setClaims(map);
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, []);

  useEffect(() => {
    if (!user) return;
    setWorkClasses(user.work_classes || []);
    setGeneralSkills(user.general_skills || []);
    setGeneralExperience(user.general_experience || "");
    setAttributes(user.work_attributes || []);
    setBilingualLanguages(user.bilingual_languages || "");
    setAvailability(user.availability || []);
    setHasCar(!!user.has_car);
    setHasTruck(!!user.has_truck);
    // eslint-disable-next-line
  }, [user?.user_id]);

  const isCrew = workClasses.includes("general_labor");
  const isSpec = workClasses.includes("specialist");

  const steps = useMemo(() => {
    const s = ["how"];
    if (isCrew) s.push("general");
    if (isSpec) s.push("trades");
    s.push("certs", "attributes", "logistics", "review");
    return s;
  }, [isCrew, isSpec]);
  const step = steps[Math.min(stepIdx, steps.length - 1)];

  const toggle = (arr, set, v) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  // ---- persistence per step ------------------------------------------------
  const saveVehicle = async () =>
    api.put("/profile", { has_car: hasCar, has_truck: hasTruck });

  const saveClaim = async (tid) => {
    const c = claims[tid];
    if (!c) return;
    const { data } = await api.put(`/profile/trades/${tid}`, {
      checklist: c.checklist || {},
      detail_fields: c.detail_fields || {},
      experience: c.experience || null,
      license_number: c.license_number || null,
    });
    setClaims((m) => ({ ...m, [tid]: { ...m[tid], status: data.status } }));
  };

  const next = async () => {
    setBusy(true);
    try {
      if (step === "how") {
        if (!workClasses.length) {
          toast.error("Pick at least one — crew work, a specialty, or both");
          return;
        }
        await api.put("/profile/questionnaire", { work_classes: workClasses });
      } else if (step === "general") {
        if (!generalSkills.length) {
          toast.error("Pick at least one skill");
          return;
        }
        await saveVehicle();
        await api.put("/profile/questionnaire", {
          general_skills: generalSkills,
          general_experience: generalExperience || null,
        });
      } else if (step === "trades") {
        for (const tid of Object.keys(claims)) await saveClaim(tid);
      } else if (step === "attributes") {
        await api.put("/profile/questionnaire", {
          work_attributes: attributes,
          bilingual_languages: attributes.includes("bilingual") ? bilingualLanguages : "",
        });
      } else if (step === "logistics") {
        if (!availability.length) {
          toast.error("Pick at least one availability window");
          return;
        }
        await api.put("/profile", { availability, has_car: hasCar, has_truck: hasTruck });
      }
      setStepIdx((i) => Math.min(i + 1, steps.length - 1));
      window.scrollTo({ top: 0 });
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      for (const tid of Object.keys(claims)) await saveClaim(tid);
      for (const [tid, c] of Object.entries(claims)) {
        if (["incomplete", "returned"].includes(c.status)) {
          await api.post(`/profile/trades/${tid}/submit`);
        }
      }
      await checkAuth();
      toast.success(onboarding ? "You're set — welcome to the crew" : "Work profile updated");
      nav(onboarding ? "/crew" : "/crew/me");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (!user || !options || !defs) return null;

  const tdefs = defs.trades || [];
  const defMap = Object.fromEntries(tdefs.map((t) => [t.trade_id, t]));
  const blockingClaims = Object.entries(claims)
    .filter(([tid, c]) => c.status !== "verified" && c.status !== "pending")
    .map(([tid, c]) => ({ tid, c, errs: claimErrors(c, defMap[tid] || {}) }))
    .filter((x) => x.errs.length);

  return (
    <div className="px-5 py-6 pb-32" data-testid="worker-questionnaire">
      <div className="font-mono-label">{onboarding ? "Welcome to HCOB" : "Work profile"}</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">
        {onboarding ? "Set up how you work" : "How you work"}
      </h1>
      <p className="mt-1 text-sm text-[#4B5563]">
        Two ways to earn in the network — join managed crews, or run your specialty. Many pros do both.
      </p>

      {/* Progress */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
          <span data-testid="questionnaire-step-indicator">Step {stepIdx + 1} of {steps.length}</span>
          {onboarding && (
            <Link to="/crew" data-testid="questionnaire-skip" className="text-[#0044FF]">
              Do this later
            </Link>
          )}
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#E5E7EB]">
          <div className="h-full bg-[#0044FF] transition-all" style={{ width: `${((stepIdx + 1) / steps.length) * 100}%` }} />
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {step === "how" && (
          <StepCard title="How do you work?" subtitle="Pick one or both — you can change this anytime.">
            <div className="grid grid-cols-1 gap-3">
              <ClassCard
                testId="class-general-labor"
                active={isCrew}
                icon={HardHat}
                title="Crew & Labor Work"
                desc="Cleaning, moving, warehouse, hourly labor — work on HCOB-managed crews with job checklists. No equipment needed."
                onClick={() => toggle(workClasses, setWorkClasses, "general_labor")}
              />
              <ClassCard
                testId="class-specialist"
                active={isSpec}
                icon={Toolbox}
                title="I Run a Specialty Trade"
                desc="Painting, landscaping, carpet cleaning & more — you own the tools and run jobs independently. Equipment proof required."
                onClick={() => toggle(workClasses, setWorkClasses, "specialist")}
              />
            </div>
          </StepCard>
        )}

        {step === "general" && (
          <StepCard title="Crew & labor skills" subtitle="Everything here works on managed crews — no proof needed.">
            <div className="font-mono-label mb-2">Cleaning</div>
            <div className="grid grid-cols-2 gap-2">
              {options.general_cleaning_skills.map((s) => (
                <Chip key={s.value} testId={`gskill-${s.value}`} active={generalSkills.includes(s.value)}
                  onClick={() => toggle(generalSkills, setGeneralSkills, s.value)} label={s.label} />
              ))}
            </div>
            <div className="font-mono-label mb-2 mt-4">Labor & driving</div>
            <div className="grid grid-cols-2 gap-2">
              {options.general_labor_skills.map((s) => {
                const needsVehicle = s.value === "driving" || s.value === "delivery";
                const locked = needsVehicle && !hasCar && !hasTruck;
                return (
                  <Chip key={s.value} testId={`gskill-${s.value}`}
                    active={generalSkills.includes(s.value)}
                    disabled={locked}
                    onClick={() => {
                      if (locked) { toast.info("Declare a car or truck below first"); return; }
                      toggle(generalSkills, setGeneralSkills, s.value);
                    }}
                    label={s.label} />
                );
              })}
            </div>
            <div className="mt-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="font-mono-label mb-2">Vehicle (needed for driving/delivery)</div>
              <div className="grid grid-cols-2 gap-2">
                <Chip testId="q-vehicle-car" active={hasCar} icon={Car}
                  onClick={() => { const v = !hasCar; setHasCar(v); if (!v && !hasTruck) setGeneralSkills((g) => g.filter((s) => s !== "driving" && s !== "delivery")); }}
                  label="Car" />
                <Chip testId="q-vehicle-truck" active={hasTruck} icon={Truck}
                  onClick={() => { const v = !hasTruck; setHasTruck(v); if (!v && !hasCar) setGeneralSkills((g) => g.filter((s) => s !== "driving" && s !== "delivery")); }}
                  label="Truck" />
              </div>
            </div>
            <div className="mt-4">
              <div className="font-mono-label mb-2">Your overall labor experience</div>
              <select
                data-testid="general-experience"
                value={generalExperience}
                onChange={(e) => setGeneralExperience(e.target.value)}
                className="h-11 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
              >
                <option value="">Select…</option>
                {options.experience_levels.map((e) => (
                  <option key={e} value={e}>{EXPERIENCE_LABELS[e] || e}</option>
                ))}
              </select>
            </div>
          </StepCard>
        )}

        {step === "trades" && (
          <StepCard
            title="Your specialist trades"
            subtitle="Verified specialists get first access to specialist jobs and specialist pay."
          >
            <div className="rounded-xl border border-[#F59E0B]/30 bg-[#FFFBEB] p-3 text-[11px] leading-relaxed text-[#92400E]">
              {defs.ownership_language}
            </div>
            <div className="mt-3 space-y-3">
              {tdefs.map((t) => (
                <TradePanel
                  key={t.trade_id}
                  tdef={t}
                  claim={claims[t.trade_id]}
                  onClaim={async () => {
                    try {
                      const { data } = await api.put(`/profile/trades/${t.trade_id}`, {});
                      setClaims((m) => ({ ...m, [t.trade_id]: data }));
                    } catch (e) { toast.error(getErr(e)); }
                  }}
                  onRemove={async () => {
                    try {
                      await api.delete(`/profile/trades/${t.trade_id}`);
                      setClaims((m) => { const n = { ...m }; delete n[t.trade_id]; return n; });
                      toast.success(`${t.label} claim removed`);
                    } catch (e) { toast.error(getErr(e)); }
                  }}
                  onChange={(patch) =>
                    setClaims((m) => ({ ...m, [t.trade_id]: { ...m[t.trade_id], ...patch } }))
                  }
                  onSave={() => saveClaim(t.trade_id)}
                  experienceLevels={options.experience_levels}
                />
              ))}
            </div>
          </StepCard>
        )}

        {step === "certs" && (
          <StepCard title="Certifications" subtitle="Forklift, CDL and more — upload the document and HCOB verifies it. You can do this now or later.">
            <div className="space-y-2">
              {badges.map((b) => (
                <div key={b.badge_id} className="flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-white p-3" data-testid={`cert-row-${b.badge_id}`}>
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-white" style={{ backgroundColor: b.color }}>
                    <SealCheck size={18} weight="fill" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-bold">{b.name}</div>
                    <div className="text-[10px] text-[#4B5563]">
                      {b.question_count === 0 ? "Document upload only" : `${b.question_count}-question test + credentials`}
                    </div>
                  </div>
                  {b.certified ? (
                    <span className="rounded-full bg-[#10B981] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">CERTIFIED</span>
                  ) : b.application ? (
                    <span className="rounded-full bg-[#F59E0B] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">IN PROGRESS</span>
                  ) : null}
                </div>
              ))}
            </div>
            <Link
              to="/crew/certifications"
              data-testid="questionnaire-certs-link"
              className="mt-3 block rounded-xl bg-[#F0F4FF] p-3 text-center text-sm font-bold text-[#1D4ED8]"
            >
              Open Certifications page →
            </Link>
          </StepCard>
        )}

        {step === "attributes" && (
          <StepCard title="Work attributes" subtitle="Used for matching only — these never show as skills or badges.">
            <div className="grid grid-cols-1 gap-2">
              {options.work_attributes.map((a) => (
                <Chip key={a.value} testId={`attr-${a.value}`} active={attributes.includes(a.value)}
                  onClick={() => toggle(attributes, setAttributes, a.value)} label={a.label} />
              ))}
            </div>
            {attributes.includes("bilingual") && (
              <div className="mt-3">
                <div className="font-mono-label mb-2">Which language(s)?</div>
                <Input
                  data-testid="bilingual-languages"
                  value={bilingualLanguages}
                  onChange={(e) => setBilingualLanguages(e.target.value)}
                  placeholder="e.g. Spanish"
                  className="h-11 rounded-xl border-[#E5E7EB]"
                />
              </div>
            )}
          </StepCard>
        )}

        {step === "logistics" && (
          <StepCard title="When you're free & your vehicle" subtitle="CDL now lives under Certifications — upload your license there.">
            <div className="font-mono-label mb-2">Availability</div>
            <div className="grid grid-cols-2 gap-2">
              {options.availability.map((a) => (
                <Chip key={a} testId={`q-avail-${a}`} active={availability.includes(a)}
                  onClick={() => toggle(availability, setAvailability, a)} label={AVAILABILITY_LABELS[a] || a} />
              ))}
            </div>
            <div className="font-mono-label mb-2 mt-4">Vehicle</div>
            <div className="grid grid-cols-2 gap-2">
              <Chip testId="q2-vehicle-car" active={hasCar} icon={Car} onClick={() => setHasCar(!hasCar)} label="Car" />
              <Chip testId="q2-vehicle-truck" active={hasTruck} icon={Truck} onClick={() => setHasTruck(!hasTruck)} label="Truck" />
            </div>
          </StepCard>
        )}

        {step === "review" && (
          <StepCard title="Review & finish" subtitle="Here's how HCOB will see you.">
            <ReviewRow label="Work classes">
              {workClasses.length ? workClasses.map((c) => (c === "general_labor" ? "Crew & Labor" : "Specialist")).join(" + ") : "—"}
            </ReviewRow>
            {isCrew && (
              <ReviewRow label="Crew skills">
                {generalSkills.map((s) => {
                  const all = [...options.general_cleaning_skills, ...options.general_labor_skills];
                  return all.find((x) => x.value === s)?.label || s;
                }).join(", ") || "—"}
              </ReviewRow>
            )}
            {Object.keys(claims).length > 0 && (
              <div className="border-b border-[#E5E7EB] py-3">
                <div className="font-mono-label mb-2">Specialist trades</div>
                <div className="space-y-1.5">
                  {Object.entries(claims).map(([tid, c]) => {
                    const pill = STATUS_PILL[c.status] || STATUS_PILL.incomplete;
                    const errs = c.status === "verified" || c.status === "pending" ? [] : claimErrors(c, defMap[tid] || {});
                    return (
                      <div key={tid} className="flex items-center justify-between text-sm">
                        <span className="font-semibold">{defMap[tid]?.label || tid}</span>
                        <span className="rounded-full px-2 py-0.5 text-[9px] font-bold tracking-widest text-white"
                          style={{ backgroundColor: errs.length ? "#F59E0B" : pill.bg }}>
                          {errs.length ? "INCOMPLETE" : c.status === "incomplete" || c.status === "returned" ? "READY TO SUBMIT" : pill.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            <ReviewRow label="Attributes">
              {attributes.map((a) => options.work_attributes.find((x) => x.value === a)?.label || a).join(", ") || "—"}
            </ReviewRow>
            <ReviewRow label="Availability">
              {availability.map((a) => AVAILABILITY_LABELS[a] || a).join(", ") || "—"}
            </ReviewRow>

            {blockingClaims.length > 0 && (
              <div data-testid="review-blocking-claims" className="mt-3 rounded-xl border border-[#F59E0B]/40 bg-[#FFFBEB] p-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#92400E]">
                  <Warning size={14} weight="fill" /> Finish these trades (or remove the claim) before submitting:
                </div>
                <ul className="mt-2 space-y-1 text-[11px] text-[#92400E]">
                  {blockingClaims.map(({ tid, errs }) => (
                    <li key={tid}>
                      <strong>{defMap[tid]?.label || tid}:</strong> {errs.join(" · ")}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  data-testid="review-back-to-trades"
                  onClick={() => setStepIdx(steps.indexOf("trades"))}
                  className="mt-2 text-xs font-bold text-[#0044FF]"
                >
                  ← Back to trades
                </button>
              </div>
            )}

            <Button
              data-testid="questionnaire-finish"
              onClick={finish}
              disabled={busy || blockingClaims.length > 0}
              className="mt-4 h-12 w-full rounded-2xl bg-[#030712] text-white"
            >
              {busy ? "Saving…" : onboarding ? "Finish setup" : "Save work profile"}
            </Button>
          </StepCard>
        )}
      </div>

      {/* Nav buttons */}
      {step !== "review" && (
        <div className="mt-6 flex gap-3">
          {stepIdx > 0 && (
            <Button
              data-testid="questionnaire-back"
              variant="outline"
              onClick={() => setStepIdx((i) => Math.max(0, i - 1))}
              className="h-12 flex-1 rounded-2xl border-[#E5E7EB]"
            >
              <ArrowLeft size={16} className="mr-1" /> Back
            </Button>
          )}
          <Button
            data-testid="questionnaire-next"
            onClick={next}
            disabled={busy}
            className="h-12 flex-1 rounded-2xl bg-[#0044FF] text-white"
          >
            {busy ? "Saving…" : "Next"} <ArrowRight size={16} className="ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}

function StepCard({ title, subtitle, children }) {
  return (
    <section className="gb-tactile rounded-2xl border border-black/5 bg-white p-5">
      <h2 className="font-display text-lg font-black tracking-tight">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-[#4B5563]">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ClassCard({ active, icon: Icon, title, desc, onClick, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`relative flex items-start gap-3 rounded-2xl border-2 p-4 text-left transition-colors ${
        active ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#E5E7EB] bg-white hover:border-[#0044FF]/40"
      }`}
    >
      {active && <CheckCircle size={18} weight="fill" className="absolute right-3 top-3 text-[#0044FF]" />}
      <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${active ? "bg-[#0044FF] text-white" : "bg-[#F0F4FF] text-[#0044FF]"}`}>
        <Icon size={22} weight="duotone" />
      </div>
      <div>
        <div className="font-display text-base font-bold">{title}</div>
        <div className="mt-0.5 text-xs leading-relaxed text-[#4B5563]">{desc}</div>
      </div>
    </button>
  );
}

function Chip({ active, onClick, label, icon: Icon, testId, disabled }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`flex h-11 items-center justify-center gap-1.5 rounded-xl border text-sm font-bold ${
        active
          ? "border-[#0044FF] bg-[#0044FF] text-white"
          : disabled
          ? "border-[#E5E7EB] bg-[#F9FAFB] text-[#9CA3AF]"
          : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#0044FF]/30"
      }`}
    >
      {Icon && <Icon size={14} weight={active ? "fill" : "duotone"} />}
      {label}
    </button>
  );
}

function ReviewRow({ label, children }) {
  return (
    <div className="border-b border-[#E5E7EB] py-3">
      <div className="font-mono-label">{label}</div>
      <div className="mt-1 text-sm">{children}</div>
    </div>
  );
}

function TradePanel({ tdef, claim, onClaim, onRemove, onChange, onSave, experienceLevels }) {
  const [open, setOpen] = useState(false);
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const claimed = !!claim;
  const errs = claimed && claim.status !== "verified" && claim.status !== "pending" ? claimErrors(claim, tdef) : [];
  const pill = claimed ? (STATUS_PILL[claim.status] || STATUS_PILL.incomplete) : null;

  const uploadPhoto = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/profile/trades/${tdef.trade_id}/photos`, fd);
      onChange({ photos: [...(claim.photos || []), data.path] });
      toast.success("Photo added");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removePhoto = async (path) => {
    try {
      await api.delete(`/profile/trades/${tdef.trade_id}/photos`, { params: { path } });
      onChange({ photos: (claim.photos || []).filter((p) => p !== path) });
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div
      data-testid={`trade-card-${tdef.trade_id}`}
      className={`rounded-2xl border-2 ${claimed ? "border-[#0044FF]/40 bg-white" : "border-[#E5E7EB] bg-white"}`}
    >
      <button
        type="button"
        data-testid={`trade-toggle-${tdef.trade_id}`}
        onClick={async () => {
          if (!claimed) {
            await onClaim();
            setOpen(true);
          } else {
            if (open) await onSave();
            setOpen(!open);
          }
        }}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${claimed ? "bg-[#0044FF] text-white" : "bg-[#F0F4FF] text-[#0044FF]"}`}>
          <Toolbox size={20} weight="duotone" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-sm font-bold">{tdef.label}</div>
          {claimed ? (
            <span
              data-testid={`trade-status-${tdef.trade_id}`}
              className="mt-1 inline-block rounded-full px-2 py-0.5 text-[9px] font-bold tracking-widest text-white"
              style={{ backgroundColor: errs.length ? "#F59E0B" : pill.bg }}
            >
              {errs.length ? "INCOMPLETE" : pill.label}
            </span>
          ) : (
            <div className="text-[10px] text-[#4B5563]">Tap to claim · equipment checklist + photo proof</div>
          )}
        </div>
        {claimed && (open ? <CaretUp size={16} /> : <CaretDown size={16} />)}
      </button>

      {claimed && open && (
        <div className="border-t border-[#E5E7EB] p-4">
          {claim.status === "returned" && claim.admin_note && (
            <div className="mb-3 rounded-xl border border-[#EF4444]/30 bg-[#FEF2F2] p-3 text-xs text-[#991B1B]" data-testid={`trade-return-note-${tdef.trade_id}`}>
              <strong>HCOB returned this:</strong> {claim.admin_note}
            </div>
          )}
          <div className="font-mono-label mb-2">Equipment you own</div>
          <div className="space-y-2">
            {(tdef.checklist || []).map((it) => {
              const checked = !!claim.checklist?.[it.key];
              return (
                <div key={it.key}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-[#E5E7EB] bg-white p-3">
                    <input
                      type="checkbox"
                      data-testid={`trade-item-${tdef.trade_id}-${it.key}`}
                      checked={checked}
                      onChange={(e) =>
                        onChange({ checklist: { ...(claim.checklist || {}), [it.key]: e.target.checked } })
                      }
                      className="h-4 w-4 accent-[#0044FF]"
                    />
                    <span className="text-sm font-semibold">{it.label}</span>
                    {it.photo_required && (
                      <span className="ml-auto text-[9px] font-bold uppercase tracking-widest text-[#F59E0B]">Photo req.</span>
                    )}
                  </label>
                  {checked && it.detail_label && (
                    <Input
                      data-testid={`trade-detail-${tdef.trade_id}-${it.key}`}
                      value={claim.detail_fields?.[it.key] || ""}
                      onChange={(e) =>
                        onChange({ detail_fields: { ...(claim.detail_fields || {}), [it.key]: e.target.value } })
                      }
                      placeholder={it.detail_label}
                      className="mt-1.5 h-10 rounded-xl border-[#E5E7EB] text-sm"
                    />
                  )}
                </div>
              );
            })}
          </div>

          {tdef.licensed && (
            <div className="mt-3">
              <div className="font-mono-label mb-2">MD license number</div>
              <Input
                data-testid={`trade-license-${tdef.trade_id}`}
                value={claim.license_number || ""}
                onChange={(e) => onChange({ license_number: e.target.value })}
                placeholder="e.g. 12345"
                className="h-10 rounded-xl border-[#E5E7EB] text-sm"
              />
            </div>
          )}

          <div className="mt-3">
            <div className="font-mono-label mb-2">Experience in this trade</div>
            <select
              data-testid={`trade-experience-${tdef.trade_id}`}
              value={claim.experience || ""}
              onChange={(e) => onChange({ experience: e.target.value })}
              className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
            >
              <option value="">Select…</option>
              {experienceLevels.map((e) => (
                <option key={e} value={e}>{EXPERIENCE_LABELS[e] || e}</option>
              ))}
            </select>
          </div>

          <div className="mt-3">
            <div className="font-mono-label mb-1">{tdef.licensed ? "License upload" : "Photo proof"}</div>
            {tdef.photo_hint && <div className="mb-2 text-[10px] text-[#4B5563]">{tdef.photo_hint}</div>}
            <input
              ref={fileRef}
              type="file"
              accept={tdef.licensed ? "image/*,.pdf" : "image/*"}
              className="hidden"
              data-testid={`trade-photo-input-${tdef.trade_id}`}
              onChange={(e) => uploadPhoto(e.target.files?.[0])}
            />
            {(claim.photos || []).length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {claim.photos.map((p) => (
                  <div key={p} className="relative">
                    <ProtectedThumb path={p} />
                    <button
                      type="button"
                      data-testid={`trade-photo-remove-${tdef.trade_id}`}
                      onClick={() => removePhoto(p)}
                      className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-[#EF4444] text-white"
                    >
                      <X size={10} weight="bold" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              type="button"
              data-testid={`trade-photo-add-${tdef.trade_id}`}
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[#93C5FD] bg-[#F0F4FF] px-3 py-3 text-xs font-semibold text-[#1D4ED8]"
            >
              <Camera size={14} weight="duotone" /> {uploading ? "Uploading…" : "Add photo"}
            </button>
          </div>

          {errs.length > 0 && (
            <div className="mt-3 rounded-xl border border-[#F59E0B]/30 bg-[#FFFBEB] p-2.5 text-[11px] text-[#92400E]" data-testid={`trade-errors-${tdef.trade_id}`}>
              {errs.join(" · ")}
            </div>
          )}

          <div className="mt-3 flex items-center justify-between">
            <button
              type="button"
              data-testid={`trade-remove-${tdef.trade_id}`}
              onClick={onRemove}
              className="inline-flex items-center gap-1 text-xs font-bold text-[#EF4444]"
            >
              <Trash size={13} /> Remove claim
            </button>
            <button
              type="button"
              data-testid={`trade-save-${tdef.trade_id}`}
              onClick={async () => { await onSave(); setOpen(false); }}
              className="rounded-xl bg-[#030712] px-4 py-2 text-xs font-bold text-white"
            >
              Save trade
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProtectedThumb({ path }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, { credentials: "include" });
        if (!res.ok) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        setSrc(url);
      } catch {}
    })();
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (!src) return <div className="h-16 w-16 rounded-lg bg-[#F0F4FF]" />;
  return <img src={src} alt="" className="h-16 w-16 rounded-lg border border-[#E5E7EB] object-cover" />;
}
