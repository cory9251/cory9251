import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { roleHomePath } from "@/components/ProtectedRoute";
import { getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  GoogleLogo,
  ArrowLeft,
  CheckCircle,
  HardHat,
  Headset,
} from "@phosphor-icons/react";

const THEMES = {
  worker: {
    kicker: "New Worker · Field Crew",
    panelBg: "#1B2A22",
    panelAccent: "#8FB89E",
    solid: "#1B2A22",
    headline: (
      <>
        Join the
        <br />
        HCOB crew.
      </>
    ),
    sub: "Workers get a profile, ID upload, and direct access to every gig HCOB Cleaners posts.",
    bullets: [
      "Cleaning, labor and driver gigs",
      "Get notified by app, email, or SMS",
      "Verified by HCOB · No middlemen",
    ],
    formTitle: "Create your worker account",
    formSub: "Free for HCOB workers. Use email or continue with Google.",
    submitLabel: "Create my worker account",
    mobileTag: "You're signing up to work gigs — cleaning, labor & driving",
  },
  va: {
    kicker: "New Virtual Assistant · Remote",
    panelBg: "#C84B31",
    panelAccent: "#F5D8CF",
    solid: "#C84B31",
    headline: (
      <>
        Earn with HCOB.
        <br />
        Your leads, your commissions.
      </>
    ),
    sub: "Submit cleaning leads, watch them flow through the pipeline, and earn commissions automatically once they convert.",
    bullets: [
      "Submit leads through your dashboard",
      "Auto-calculated commission per converted job",
      "Self-service earnings + leaderboard",
    ],
    formTitle: "Create your VA account",
    formSub: "VA accounts are reviewed by the Program Manager before activation.",
    submitLabel: "Apply as a Virtual Assistant",
    mobileTag: "You're applying as a remote VA — earn commission on leads",
  },
};

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const initialRole = searchParams.get("as") === "va" ? "va" : "worker";
  const [role, setRole] = useState(initialRole);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workerPhone, setWorkerPhone] = useState("");
  const [smsOptIn, setSmsOptIn] = useState(false);
  const [vaPhone, setVaPhone] = useState("");
  const [vaAddress, setVaAddress] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const payload = { email, password, name, role };
      if (role === "va") {
        if (vaPhone) payload.va_phone = vaPhone;
        if (vaAddress) payload.va_address = vaAddress;
      } else {
        // Worker signup — phone + SMS opt-in (Twilio A2P 10DLC)
        if (workerPhone) payload.phone = workerPhone;
        payload.sms_opt_in = !!(smsOptIn && workerPhone);
      }
      const u = await register(payload);
      if (role === "va") {
        toast.success("Welcome! Your VA account is awaiting Program Manager approval.");
      } else {
        toast.success("Welcome to the HCOB crew");
      }
      if (u.role === "worker" && next && next.startsWith("/")) {
        nav(next, { replace: true });
      } else if (u.role === "worker") {
        // New workers go straight into the work questionnaire wizard.
        nav("/crew/onboarding", { replace: true });
      } else {
        nav(roleHomePath(u), { replace: true });
      }
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  const google = () => {
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href =
      "https://auth.emergentagent.com/?redirect=" +
      encodeURIComponent(redirectUrl);
  };

  const isVA = role === "va";
  const t = THEMES[role];

  return (
    <div className="min-h-screen bg-[#F5F4F0] text-[#1C1A17]" data-testid="register-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        {/* ── Left themed panel (desktop) ─────────────────────── */}
        <motion.div
          animate={{ backgroundColor: t.panelBg }}
          transition={{ duration: 0.45 }}
          className="hidden lg:flex flex-col justify-between p-12 text-[#F5F4F0]"
          data-testid="register-side-panel"
        >
          <Link
            to={isVA ? "/vas" : "/work"}
            className="font-mono-label flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[#F5F4F0]/70 hover:text-[#F5F4F0]"
          >
            <ArrowLeft size={14} /> Back home
          </Link>

          <AnimatePresence mode="wait">
            <motion.div
              key={role}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3 }}
            >
              <div
                className="mb-6 inline-flex items-center gap-2 border px-3 py-1.5 font-mono-label text-xs uppercase tracking-[0.2em]"
                style={{ borderColor: `${t.panelAccent}66`, color: t.panelAccent }}
              >
                {isVA ? <Headset size={14} weight="duotone" /> : <HardHat size={14} weight="duotone" />}
                {isVA ? "Virtual Assistant Track" : "Field Worker Track"}
              </div>
              <div className="font-display text-6xl font-black leading-[0.95] tracking-tight">
                {t.headline}
              </div>
              <div className="mt-6 max-w-md text-sm leading-relaxed text-[#F5F4F0]/75">
                {t.sub}
              </div>
              <ul className="mt-8 space-y-2 text-sm text-[#F5F4F0]/85">
                {t.bullets.map((b) => (
                  <li key={b} className="flex items-center gap-2">
                    <CheckCircle size={16} weight="fill" style={{ color: t.panelAccent }} /> {b}
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>

          <div className="font-mono-label text-xs uppercase tracking-[0.2em] text-[#F5F4F0]/50">
            © HCOB Network
          </div>
        </motion.div>

        {/* ── Right form column ──────────────────────────────── */}
        <div className="flex flex-col">
          {/* Mobile role banner — visible only below lg */}
          <motion.div
            animate={{ backgroundColor: t.panelBg }}
            transition={{ duration: 0.45 }}
            className="flex items-center gap-3 px-6 py-4 text-[#F5F4F0] lg:hidden"
            data-testid="register-mobile-role-banner"
          >
            {isVA ? (
              <Headset size={22} weight="duotone" style={{ color: t.panelAccent }} />
            ) : (
              <HardHat size={22} weight="duotone" style={{ color: t.panelAccent }} />
            )}
            <div>
              <div className="font-mono-label text-[10px] uppercase tracking-[0.2em]" style={{ color: t.panelAccent }}>
                {isVA ? "Virtual Assistant Track" : "Field Worker Track"}
              </div>
              <div className="text-xs text-[#F5F4F0]/85">{t.mobileTag}</div>
            </div>
          </motion.div>

          <div className="flex flex-1 items-center justify-center p-6 sm:p-12">
            <div className="w-full max-w-md">
              <div
                className="font-mono-label mb-2 text-xs uppercase tracking-[0.2em]"
                style={{ color: t.solid }}
                data-testid="register-kicker"
              >
                {t.kicker}
              </div>
              <h1 className="font-display text-4xl font-black tracking-tight" data-testid="register-title">
                {t.formTitle}
              </h1>
              <p className="mt-2 text-sm text-[#1C1A17]/65">{t.formSub}</p>

              {/* Role toggle */}
              <div className="mt-6">
                <div className="font-mono-label mb-2 text-[10px] uppercase tracking-[0.2em] text-[#1C1A17]/50">
                  Which side are you applying for?
                </div>
                <div className="grid grid-cols-2 gap-3" data-testid="register-role-toggle">
                  <button
                    type="button"
                    data-testid="register-role-worker"
                    onClick={() => setRole("worker")}
                    className={`relative flex flex-col items-start gap-1.5 border-2 px-4 py-4 text-left transition-all duration-200 ${
                      !isVA
                        ? "border-[#1B2A22] bg-[#1B2A22] text-[#F5F4F0]"
                        : "border-[#1C1A17]/15 bg-white text-[#1C1A17] hover:border-[#1B2A22]/50 hover:-translate-y-0.5"
                    }`}
                  >
                    {!isVA && (
                      <CheckCircle size={18} weight="fill" className="absolute right-3 top-3 text-[#8FB89E]" />
                    )}
                    <HardHat size={22} weight="duotone" className={!isVA ? "text-[#8FB89E]" : "text-[#1B2A22]"} />
                    <div className="font-display text-base font-bold">Worker</div>
                    <div className={`text-[11px] leading-snug ${!isVA ? "text-[#F5F4F0]/70" : "text-[#1C1A17]/60"}`}>
                      On-site gigs: cleaning, labor & driving
                    </div>
                  </button>
                  <button
                    type="button"
                    data-testid="register-role-va"
                    onClick={() => setRole("va")}
                    className={`relative flex flex-col items-start gap-1.5 border-2 px-4 py-4 text-left transition-all duration-200 ${
                      isVA
                        ? "border-[#C84B31] bg-[#C84B31] text-[#F5F4F0]"
                        : "border-[#1C1A17]/15 bg-white text-[#1C1A17] hover:border-[#C84B31]/60 hover:-translate-y-0.5"
                    }`}
                  >
                    {isVA && (
                      <CheckCircle size={18} weight="fill" className="absolute right-3 top-3 text-[#F5D8CF]" />
                    )}
                    <Headset size={22} weight="duotone" className={isVA ? "text-[#F5D8CF]" : "text-[#C84B31]"} />
                    <div className="font-display text-base font-bold">Virtual Assistant</div>
                    <div className={`text-[11px] leading-snug ${isVA ? "text-[#F5F4F0]/80" : "text-[#1C1A17]/60"}`}>
                      Remote — earn commission on leads
                    </div>
                  </button>
                </div>
              </div>

              <form onSubmit={submit} className="mt-6 space-y-4">
                <div>
                  <Label htmlFor="name" className="font-mono-label text-xs uppercase tracking-[0.2em]">Full name</Label>
                  <Input
                    data-testid="register-name"
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                    style={{ borderColor: undefined }}
                  />
                </div>
                <div>
                  <Label htmlFor="email" className="font-mono-label text-xs uppercase tracking-[0.2em]">Email</Label>
                  <Input
                    data-testid="register-email"
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    autoCapitalize="off"
                    autoCorrect="off"
                    spellCheck="false"
                    inputMode="email"
                    className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                  />
                </div>
                <div>
                  <Label htmlFor="password" className="font-mono-label text-xs uppercase tracking-[0.2em]">Password</Label>
                  <Input
                    data-testid="register-password"
                    id="password"
                    type="password"
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    autoCapitalize="off"
                    autoCorrect="off"
                    spellCheck="false"
                    className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                  />
                </div>

                {isVA && (
                  <>
                    <div>
                      <Label htmlFor="va_phone" className="font-mono-label text-xs uppercase tracking-[0.2em]">Phone (optional)</Label>
                      <Input
                        data-testid="register-va-phone"
                        id="va_phone"
                        type="tel"
                        value={vaPhone}
                        onChange={(e) => setVaPhone(e.target.value)}
                        className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                      />
                    </div>
                    <div>
                      <Label htmlFor="va_address" className="font-mono-label text-xs uppercase tracking-[0.2em]">
                        Your home address <span className="normal-case tracking-normal text-[#1C1A17]/40">(used for self-referral check)</span>
                      </Label>
                      <Input
                        data-testid="register-va-address"
                        id="va_address"
                        value={vaAddress}
                        onChange={(e) => setVaAddress(e.target.value)}
                        className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                      />
                    </div>
                    <div className="border border-[#C84B31]/40 bg-[#C84B31]/10 p-3 text-xs text-[#7A2E1D]">
                      Your account will be flagged <strong>pending</strong> until the Program Manager approves you.
                    </div>
                  </>
                )}

                {!isVA && (
                  <>
                    <div>
                      <Label htmlFor="worker_phone" className="font-mono-label text-xs uppercase tracking-[0.2em]">
                        Mobile phone <span className="normal-case tracking-normal text-[#1C1A17]/40">(optional — needed to receive text alerts)</span>
                      </Label>
                      <Input
                        data-testid="register-worker-phone"
                        id="worker_phone"
                        type="tel"
                        autoComplete="tel"
                        inputMode="tel"
                        placeholder="(410) 555-0123"
                        value={workerPhone}
                        onChange={(e) => {
                          setWorkerPhone(e.target.value);
                          if (!e.target.value) setSmsOptIn(false);
                        }}
                        className="mt-2 h-12 rounded-none border-[#1C1A17]/30 bg-white focus-visible:ring-0"
                      />
                    </div>

                    {/* Twilio A2P 10DLC opt-in — checkbox must not be pre-checked
                        and consent language must appear next to it. */}
                    <label
                      htmlFor="sms_opt_in"
                      className={`flex cursor-pointer items-start gap-3 border p-3 text-xs transition-colors ${
                        workerPhone
                          ? "border-[#1C1A17]/15 bg-white hover:border-[#1B2A22]"
                          : "cursor-not-allowed border-[#1C1A17]/15 bg-white opacity-60"
                      }`}
                    >
                      <input
                        data-testid="register-sms-opt-in"
                        id="sms_opt_in"
                        type="checkbox"
                        checked={smsOptIn}
                        onChange={(e) => setSmsOptIn(e.target.checked)}
                        disabled={!workerPhone}
                        className="mt-0.5 h-4 w-4 accent-[#1B2A22]"
                      />
                      <span className="leading-relaxed text-[#1C1A17]/80">
                        I agree to receive text messages from HCOB Network about assignment
                        opportunities, dispatch, and job updates at the mobile number I provided.
                        Message frequency varies (about 1&ndash;10 per month). Message and data
                        rates may apply. Reply <strong>STOP</strong> to opt out, <strong>HELP</strong>
                        {" "}for help. Consent is not a condition of joining. See our{" "}
                        <a
                          href="/privacy.html"
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-[#1B2A22] underline"
                          data-testid="register-privacy-link"
                        >
                          Privacy Policy
                        </a>{" "}
                        and{" "}
                        <a
                          href="/sms-terms.html"
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-[#1B2A22] underline"
                          data-testid="register-sms-terms-link"
                        >
                          SMS Messaging Terms
                        </a>
                        .
                      </span>
                    </label>
                  </>
                )}

                {err && (
                  <div data-testid="register-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {err}
                  </div>
                )}

                <Button
                  data-testid="register-submit"
                  type="submit"
                  disabled={loading}
                  className={`h-12 w-full rounded-none font-semibold text-[#F5F4F0] transition-colors ${
                    isVA
                      ? "bg-[#C84B31] hover:bg-[#A03A24]"
                      : "bg-[#1B2A22] hover:bg-[#12211A]"
                  }`}
                >
                  {loading ? "Creating…" : t.submitLabel}
                </Button>
              </form>

              {!isVA && (
                <>
                  <div className="my-6 flex items-center gap-3 text-xs text-[#1C1A17]/50">
                    <div className="h-px flex-1 bg-[#1C1A17]/15" />
                    OR
                    <div className="h-px flex-1 bg-[#1C1A17]/15" />
                  </div>
                  <Button
                    data-testid="register-google-btn"
                    type="button"
                    variant="outline"
                    onClick={google}
                    className="h-12 w-full rounded-none border-[#1C1A17]/40 bg-white hover:bg-[#1C1A17]/5"
                  >
                    <GoogleLogo size={20} weight="bold" className="mr-2" /> Continue with Google
                  </Button>
                </>
              )}

              <div className="mt-8 text-sm text-[#1C1A17]/65">
                Already on the crew?{" "}
                <Link
                  to="/login"
                  data-testid="link-login"
                  className="font-semibold underline"
                  style={{ color: t.solid }}
                >
                  Sign in
                </Link>
              </div>
              <div className="mt-6 text-[11px] text-[#1C1A17]/55">
                HCOB management?{" "}
                <Link to="/login" className="underline">
                  Sign in here
                </Link>{" "}
                with your admin credentials — no separate signup.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
