import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
  Briefcase,
} from "@phosphor-icons/react";

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
      }
      const u = await register(payload);
      if (role === "va") {
        toast.success("Welcome! Your VA account is awaiting Program Manager approval.");
      } else {
        toast.success("Welcome to the HCOB crew");
      }
      if (u.role === "worker" && next && next.startsWith("/")) {
        nav(next, { replace: true });
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

  return (
    <div className="min-h-screen bg-white" data-testid="register-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back home
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              {isVA ? (
                <>Earn with HCOB.<br />Your leads, your commissions.</>
              ) : (
                <>Join the<br />HCOB crew.</>
              )}
            </div>
            <div className="mt-6 max-w-md text-sm text-white/70">
              {isVA
                ? "Submit cleaning leads, watch them flow through the pipeline, and earn commissions automatically once they convert."
                : "Workers get a profile, ID upload, and direct access to every gig HCOB Cleaners posts."}
            </div>
            <ul className="mt-8 space-y-2 text-sm text-white/80">
              {(isVA
                ? [
                    "Submit leads through your dashboard",
                    "Auto-calculated commission per converted job",
                    "Self-service earnings + leaderboard",
                  ]
                : [
                    "Cleaning, labor and driver gigs",
                    "Get notified by app, email, or SMS",
                    "Verified by HCOB · No middlemen",
                  ]
              ).map((b) => (
                <li key={b} className="flex items-center gap-2">
                  <CheckCircle size={16} weight="fill" className="text-[#0044FF]" /> {b}
                </li>
              ))}
            </ul>
          </div>
          <div className="font-mono-label text-white/60">© HCOB Network</div>
        </div>

        <div className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            <div className="font-mono-label mb-2">{isVA ? "New VA" : "New worker"}</div>
            <h1 className="font-display text-4xl font-black tracking-tight">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-[#4B5563]">
              {isVA
                ? "VA accounts are reviewed by the Program Manager before activation."
                : "Free for HCOB workers. Use email or continue with Google."}
            </p>

            {/* Role toggle */}
            <div className="mt-5 grid grid-cols-2 gap-2" data-testid="register-role-toggle">
              <button
                type="button"
                data-testid="register-role-worker"
                onClick={() => setRole("worker")}
                className={`flex flex-col items-start gap-1 border px-4 py-3 text-left ${
                  !isVA ? "border-[#030712] bg-[#030712] text-white" : "border-[#E5E7EB] bg-white"
                }`}
              >
                <HardHat size={18} weight="duotone" />
                <div className="font-semibold text-sm">Worker</div>
                <div className={`text-[10px] ${!isVA ? "text-white/70" : "text-[#4B5563]"}`}>
                  Cleaning / labor / driving gigs
                </div>
              </button>
              <button
                type="button"
                data-testid="register-role-va"
                onClick={() => setRole("va")}
                className={`flex flex-col items-start gap-1 border px-4 py-3 text-left ${
                  isVA ? "border-[#0044FF] bg-[#0044FF] text-white" : "border-[#E5E7EB] bg-white"
                }`}
              >
                <Briefcase size={18} weight="duotone" />
                <div className="font-semibold text-sm">Virtual Assistant</div>
                <div className={`text-[10px] ${isVA ? "text-white/80" : "text-[#4B5563]"}`}>
                  Earn commission on cleaning leads
                </div>
              </button>
            </div>

            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <Label htmlFor="name" className="font-mono-label">Full name</Label>
                <Input
                  data-testid="register-name"
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>
              <div>
                <Label htmlFor="email" className="font-mono-label">Email</Label>
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
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>
              <div>
                <Label htmlFor="password" className="font-mono-label">Password</Label>
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
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>

              {isVA && (
                <>
                  <div>
                    <Label htmlFor="va_phone" className="font-mono-label">Phone (optional)</Label>
                    <Input
                      data-testid="register-va-phone"
                      id="va_phone"
                      type="tel"
                      value={vaPhone}
                      onChange={(e) => setVaPhone(e.target.value)}
                      className="mt-2 h-12 rounded-none border-[#030712]"
                    />
                  </div>
                  <div>
                    <Label htmlFor="va_address" className="font-mono-label">
                      Your home address <span className="text-[#9CA3AF]">(used for self-referral check)</span>
                    </Label>
                    <Input
                      data-testid="register-va-address"
                      id="va_address"
                      value={vaAddress}
                      onChange={(e) => setVaAddress(e.target.value)}
                      className="mt-2 h-12 rounded-none border-[#030712]"
                    />
                  </div>
                  <div className="border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    Your account will be flagged <strong>pending</strong> until the Program Manager approves you.
                  </div>
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
                className="h-12 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
              >
                {loading ? "Creating…" : "Create my account"}
              </Button>
            </form>

            {!isVA && (
              <>
                <div className="my-6 flex items-center gap-3 text-xs text-[#4B5563]">
                  <div className="h-px flex-1 bg-[#E5E7EB]" />
                  OR
                  <div className="h-px flex-1 bg-[#E5E7EB]" />
                </div>
                <Button
                  data-testid="register-google-btn"
                  type="button"
                  variant="outline"
                  onClick={google}
                  className="h-12 w-full rounded-none border-[#030712]"
                >
                  <GoogleLogo size={20} weight="bold" className="mr-2" /> Continue with Google
                </Button>
              </>
            )}

            <div className="mt-8 text-sm text-[#4B5563]">
              Already on the crew?{" "}
              <Link to="/login" data-testid="link-login" className="font-semibold text-[#0044FF] hover:underline">
                Sign in
              </Link>
            </div>
            <div className="mt-6 text-[11px] text-[#4B5563]">
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
  );
}
