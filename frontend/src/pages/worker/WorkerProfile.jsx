import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import {
  Camera,
  IdentificationCard,
  CheckCircle,
  UserCircle,
  UploadSimple,
  Warning,
  Car,
  Truck,
  AddressBook,
  ListChecks,
  CalendarBlank,
  TShirt,
} from "@phosphor-icons/react";

// Pretty labels for the profile-complete checklist
const FIELD_LABELS = {
  phone: "Phone number",
  zip_code: "ZIP code",
  date_of_birth: "Date of birth",
  skills: "Skills (pick at least one)",
  availability: "Availability (pick at least one)",
  emergency_contact_name: "Emergency contact name",
  emergency_contact_phone: "Emergency contact phone",
};

const AVAILABILITY_LABELS = {
  weekdays: "Weekdays",
  weekends: "Weekends",
  mornings: "Mornings",
  evenings: "Evenings",
  overnight: "Overnight",
  full_time: "Full-time",
};

const EXPERIENCE_LABELS = {
  none: "No experience",
  "0_1_yr": "Under 1 year",
  "1_3_yr": "1–3 years",
  "3_plus_yr": "3+ years",
};

export default function WorkerProfile() {
  const { user, checkAuth } = useAuth();
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const avatarInput = useRef(null);
  const idInput = useRef(null);

  // Load enum options
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/profile/options");
        setOptions(data);
      } catch (e) {
        toast.error(getErr(e));
      }
    })();
  }, []);

  // Initialize form from user
  useEffect(() => {
    if (user && !form) {
      setForm({
        name: user.name || "",
        phone: user.phone || "",
        address: user.address || "",
        zip_code: user.zip_code || "",
        city: user.city || "",
        state: user.state || "",
        date_of_birth: user.date_of_birth || "",
        has_car: !!user.has_car,
        has_truck: !!user.has_truck,
        has_cdl: !!user.has_cdl,
        experience_level: user.experience_level || "",
        skills: user.skills || [],
        availability: user.availability || [],
        emergency_contact_name: user.emergency_contact_name || "",
        emergency_contact_phone: user.emergency_contact_phone || "",
        tshirt_size: user.tshirt_size || "",
        bio: user.bio || "",
      });
    }
  }, [user, form]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleArr = (k, v) =>
    setForm((f) => {
      const arr = f[k] || [];
      return {
        ...f,
        [k]: arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v],
      };
    });

  const save = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      await api.put("/profile", form);
      await checkAuth();
      toast.success("Profile saved");
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  const uploadAvatar = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/profile/avatar", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await checkAuth();
      toast.success("Photo updated");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const uploadId = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/profile/id", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await checkAuth();
      toast.success("ID uploaded — pending HCOB verification");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const missing = user?.profile_missing_fields || [];
  const needsId = !user?.id_image_path;
  const idPending = !!user?.id_image_path && !user?.id_verified;
  const totalChecks = (user?.profile_missing_fields ? Object.keys(FIELD_LABELS).length : 0) + 1;
  const doneChecks = totalChecks - missing.length - (needsId ? 1 : 0);
  const progressPct = Math.round((doneChecks / Math.max(totalChecks, 1)) * 100);

  if (!user || !form || !options) return null;

  return (
    <div className="px-5 py-6 pb-32" data-testid="worker-profile">
      <div className="font-mono-label">My profile</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{user.name}</h1>

      {/* Completion banner */}
      <CompletionBanner
        missing={missing}
        needsId={needsId}
        idPending={idPending}
        idVerified={!!user.id_verified}
        progressPct={progressPct}
      />

      {/* Avatar + ID */}
      <div className="mt-6 gb-tactile rounded-2xl border border-black/5 bg-white p-5">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="grid h-20 w-20 place-items-center overflow-hidden rounded-2xl bg-[#F0F4FF] text-[#0044FF]">
              {user.avatar_path ? (
                <ProtectedImg path={user.avatar_path} />
              ) : (
                <UserCircle size={50} weight="duotone" />
              )}
            </div>
            <button
              data-testid="upload-avatar-btn"
              onClick={() => avatarInput.current?.click()}
              className="absolute -bottom-2 -right-2 grid h-8 w-8 place-items-center rounded-full bg-[#030712] text-white"
            >
              <Camera size={14} weight="fill" />
            </button>
            <input
              ref={avatarInput}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => uploadAvatar(e.target.files?.[0])}
            />
          </div>
          <div>
            <div className="font-display text-lg font-bold">{user.name}</div>
            <div className="text-xs text-[#4B5563]">{user.email}</div>
          </div>
        </div>

        <div className="mt-5 border-t border-[#E5E7EB] pt-4">
          <div className="font-mono-label mb-2 flex items-center gap-2">
            <IdentificationCard size={14} weight="duotone" /> Government ID
          </div>
          {user.id_image_path ? (
            <div>
              <div className="overflow-hidden rounded-xl border border-[#E5E7EB]">
                <ProtectedImg path={user.id_image_path} className="w-full" />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                {user.id_verified ? (
                  <span className="inline-flex items-center gap-1 text-[#10B981]">
                    <CheckCircle size={12} weight="fill" /> Verified
                  </span>
                ) : (
                  <span className="text-[#F59E0B] font-semibold">Pending verification</span>
                )}
                <button
                  data-testid="replace-id-btn"
                  onClick={() => idInput.current?.click()}
                  className="font-semibold text-[#0044FF]"
                >
                  Replace
                </button>
              </div>
            </div>
          ) : (
            <button
              data-testid="upload-id-dropzone"
              onClick={() => idInput.current?.click()}
              className="gb-dropzone flex w-full flex-col items-center justify-center rounded-xl bg-white p-6 text-center"
            >
              <UploadSimple size={28} weight="duotone" className="text-[#0044FF]" />
              <div className="mt-2 text-sm font-semibold">Upload a photo of your ID</div>
              <div className="mt-1 text-xs text-[#4B5563]">JPG, PNG · 1 image</div>
            </button>
          )}
          <input
            ref={idInput}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => uploadId(e.target.files?.[0])}
          />
        </div>
      </div>

      <form onSubmit={save} className="mt-6 space-y-6">
        {/* Section: Basics */}
        <Section title="Basics">
          <Field label="Full name" required>
            <Input
              data-testid="profile-name"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
            />
          </Field>
          <Field label="Phone" required hint="+1 555 1234567">
            <Input
              data-testid="profile-phone"
              value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              required
            />
          </Field>
          <Field label="Date of birth" required>
            <Input
              data-testid="profile-dob"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => set("date_of_birth", e.target.value)}
              required
            />
          </Field>
        </Section>

        {/* Section: Where you work */}
        <Section title="Where you work" icon={AddressBook}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="ZIP code" required>
              <Input
                data-testid="profile-zip"
                value={form.zip_code}
                onChange={(e) => set("zip_code", e.target.value.replace(/\D/g, "").slice(0, 5))}
                maxLength={5}
                inputMode="numeric"
                placeholder="94110"
                required
              />
            </Field>
            <Field label="City">
              <Input
                data-testid="profile-city"
                value={form.city}
                onChange={(e) => set("city", e.target.value)}
              />
            </Field>
          </div>
          <Field label="State">
            <Input
              data-testid="profile-state"
              value={form.state}
              onChange={(e) => set("state", e.target.value.toUpperCase().slice(0, 2))}
              maxLength={2}
              placeholder="CA"
            />
          </Field>
          <Field label="Street address (optional)" hint="Not shared with other workers">
            <Input
              data-testid="profile-address"
              value={form.address}
              onChange={(e) => set("address", e.target.value)}
            />
          </Field>
        </Section>

        {/* Section: Skills */}
        <Section title="What you do" icon={ListChecks} required>
          <div className="grid grid-cols-2 gap-2">
            {options.skills.map((s) => (
              <ChipToggle
                key={s.value}
                testId={`skill-${s.value}`}
                active={form.skills.includes(s.value)}
                onClick={() => toggleArr("skills", s.value)}
                label={s.label}
              />
            ))}
          </div>
          <Field label="Experience level" className="mt-3">
            <select
              data-testid="profile-experience"
              value={form.experience_level}
              onChange={(e) => set("experience_level", e.target.value)}
              className="h-11 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
            >
              <option value="">Select…</option>
              {options.experience_levels.map((e) => (
                <option key={e} value={e}>
                  {EXPERIENCE_LABELS[e] || e}
                </option>
              ))}
            </select>
          </Field>
        </Section>

        {/* Section: Availability */}
        <Section title="When you're free" icon={CalendarBlank} required>
          <div className="grid grid-cols-2 gap-2">
            {options.availability.map((a) => (
              <ChipToggle
                key={a}
                testId={`avail-${a}`}
                active={form.availability.includes(a)}
                onClick={() => toggleArr("availability", a)}
                label={AVAILABILITY_LABELS[a] || a}
              />
            ))}
          </div>
        </Section>

        {/* Section: Vehicle */}
        <Section title="Vehicle" icon={Car}>
          <p className="-mt-2 mb-2 text-xs text-[#4B5563]">
            Used for driver gigs and labor that needs hauling.
          </p>
          <div className="grid grid-cols-3 gap-2">
            <ChipToggle
              testId="vehicle-car"
              active={form.has_car}
              onClick={() => set("has_car", !form.has_car)}
              label="Car"
              icon={Car}
            />
            <ChipToggle
              testId="vehicle-truck"
              active={form.has_truck}
              onClick={() => set("has_truck", !form.has_truck)}
              label="Truck"
              icon={Truck}
            />
            <ChipToggle
              testId="vehicle-cdl"
              active={form.has_cdl}
              onClick={() => set("has_cdl", !form.has_cdl)}
              label="CDL"
            />
          </div>
        </Section>

        {/* Section: Emergency contact */}
        <Section title="Emergency contact" required>
          <Field label="Name" required>
            <Input
              data-testid="profile-ec-name"
              value={form.emergency_contact_name}
              onChange={(e) => set("emergency_contact_name", e.target.value)}
              required
            />
          </Field>
          <Field label="Phone" required>
            <Input
              data-testid="profile-ec-phone"
              value={form.emergency_contact_phone}
              onChange={(e) => set("emergency_contact_phone", e.target.value)}
              required
            />
          </Field>
        </Section>

        {/* Section: Bio + gear */}
        <Section title="About you" icon={TShirt}>
          <Field label="T-shirt size">
            <select
              data-testid="profile-tshirt"
              value={form.tshirt_size}
              onChange={(e) => set("tshirt_size", e.target.value)}
              className="h-11 w-full rounded-xl border border-[#E5E7EB] bg-white px-3 text-sm"
            >
              <option value="">Select…</option>
              {options.tshirt_sizes.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Tell HCOB about yourself (optional)">
            <Textarea
              data-testid="profile-bio"
              rows={3}
              value={form.bio}
              onChange={(e) => set("bio", e.target.value)}
              placeholder="Your strengths, past work, anything you want HCOB to know…"
              className="rounded-xl border-[#E5E7EB]"
            />
          </Field>
        </Section>

        <Button
          data-testid="save-profile-btn"
          type="submit"
          disabled={saving}
          className="h-12 w-full rounded-2xl bg-[#030712] text-white"
        >
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </form>

      <ChangePasswordCard />
    </div>
  );
}

function CompletionBanner({ missing, needsId, idPending, idVerified, progressPct }) {
  const allDone = missing.length === 0 && idVerified;
  if (allDone) {
    return (
      <div
        data-testid="profile-complete-banner"
        className="mt-4 flex items-start gap-3 rounded-2xl border border-[#10B981]/30 bg-[#ECFDF5] p-4"
      >
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#10B981] text-white">
          <CheckCircle size={20} weight="fill" />
        </div>
        <div>
          <div className="font-display text-base font-bold text-[#065F46]">
            You're all set — request away
          </div>
          <div className="mt-0.5 text-xs text-[#065F46]/80">
            Your profile is complete and HCOB verified your ID.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="profile-completion-banner"
      className="mt-4 rounded-2xl border border-[#F59E0B]/40 bg-[#FFFBEB] p-4"
    >
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#F59E0B] text-white">
          <Warning size={20} weight="fill" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-base font-bold text-[#92400E]">
            Finish your profile to request gigs
          </div>
          <div className="mt-0.5 text-xs text-[#92400E]/80">
            HCOB needs this info before you can claim a gig.
          </div>
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#F59E0B]/20">
        <div
          className="h-full bg-[#F59E0B] transition-all"
          style={{ width: `${progressPct}%` }}
        />
      </div>
      <ul className="mt-3 grid grid-cols-1 gap-1 text-xs text-[#92400E] sm:grid-cols-2">
        {(needsId || idPending) && (
          <li
            data-testid="missing-id"
            className="inline-flex items-center gap-1.5"
          >
            <span className="grid h-4 w-4 place-items-center rounded-full bg-[#F59E0B] text-white text-[10px] font-black">!</span>
            {needsId ? "Upload your ID" : "ID awaiting HCOB verification"}
          </li>
        )}
        {missing.map((m) => (
          <li
            key={m}
            data-testid={`missing-${m}`}
            className="inline-flex items-center gap-1.5"
          >
            <span className="grid h-4 w-4 place-items-center rounded-full bg-[#F59E0B] text-white text-[10px] font-black">!</span>
            {FIELD_LABELS[m] || m}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Section({ title, icon: Icon, required, children }) {
  return (
    <section className="gb-tactile rounded-2xl border border-black/5 bg-white p-5">
      <div className="mb-4 flex items-center gap-2">
        {Icon && <Icon size={16} weight="duotone" className="text-[#0044FF]" />}
        <h2 className="font-display text-lg font-black tracking-tight">{title}</h2>
        {required && (
          <span className="ml-auto text-[10px] font-bold uppercase tracking-widest text-[#F59E0B]">
            Required
          </span>
        )}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({ label, required, hint, className = "", children }) {
  return (
    <div className={className}>
      <Label className="font-mono-label flex items-center gap-1">
        {label}
        {required && <span className="text-[#EF4444]">*</span>}
      </Label>
      <div className="mt-2 [&_input]:h-11 [&_input]:rounded-xl [&_input]:border-[#E5E7EB]">
        {children}
      </div>
      {hint && <div className="mt-1 text-[10px] text-[#4B5563]">{hint}</div>}
    </div>
  );
}

function ChipToggle({ active, onClick, label, icon: Icon, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`flex h-11 items-center justify-center gap-1.5 rounded-xl border text-sm font-bold ${
        active
          ? "border-[#0044FF] bg-[#0044FF] text-white"
          : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#0044FF]/30"
      }`}
    >
      {Icon && <Icon size={14} weight={active ? "fill" : "duotone"} />}
      {label}
    </button>
  );
}

function ChangePasswordCard() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 6) {
      toast.error("New password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      toast.success("Password updated");
      setCurrent("");
      setNext("");
      setOpen(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="mt-6 gb-tactile rounded-2xl border border-black/5 bg-white p-5"
      data-testid="change-password-card"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between"
        data-testid="toggle-change-password"
      >
        <div>
          <div className="font-mono-label">Security</div>
          <div className="mt-1 font-display text-lg font-bold">Change password</div>
        </div>
        <span className="font-mono-label text-[#0044FF]">
          {open ? "Close" : "Edit"}
        </span>
      </button>
      {open && (
        <form onSubmit={submit} className="mt-4 space-y-3 border-t border-[#E5E7EB] pt-4">
          <div>
            <Label className="font-mono-label">Current password</Label>
            <Input
              data-testid="current-password"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
              className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
            />
          </div>
          <div>
            <Label className="font-mono-label">New password</Label>
            <Input
              data-testid="new-password"
              type="password"
              minLength={6}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
              className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
            />
          </div>
          <Button
            data-testid="submit-change-password"
            type="submit"
            disabled={busy}
            className="h-11 w-full rounded-2xl bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            {busy ? "Updating…" : "Update password"}
          </Button>
        </form>
      )}
    </div>
  );
}

function ProtectedImg({ path, className = "h-full w-full object-cover" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        setSrc(url);
      } catch {}
    })();
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!src) return <div className="h-full w-full bg-[#F0F4FF]" />;
  return <img src={src} alt="" className={className} />;
}
