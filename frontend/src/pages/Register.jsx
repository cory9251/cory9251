import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { getErr } from "@/lib/api";
import { toast } from "sonner";
import { GoogleLogo, ArrowLeft, CheckCircle } from "@phosphor-icons/react";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  // `next` is set when someone hits a public gig share link and is bounced
  // here to sign up. It carries them straight to the gig after registration.
  const next = searchParams.get("next");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const u = await register({ email, password, name, role: "worker" });
      toast.success("Welcome to the HCOB crew");
      if (u.role === "worker" && next && next.startsWith("/")) {
        nav(next, { replace: true });
      } else {
        nav(u.role === "admin" ? "/ops" : "/crew", { replace: true });
      }
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  const google = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href =
      "https://auth.emergentagent.com/?redirect=" +
      encodeURIComponent(redirectUrl);
  };

  return (
    <div className="min-h-screen bg-white" data-testid="register-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back home
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              Join the
              <br />
              HCOB crew.
            </div>
            <div className="mt-6 max-w-md text-sm text-white/70">
              Workers get a profile, ID upload, and direct access to every gig
              HCOB Cleaners posts.
            </div>
            <ul className="mt-8 space-y-2 text-sm text-white/80">
              {[
                "Cleaning, labor and driver gigs",
                "Get notified by app, email, or SMS",
                "Verified by HCOB · No middlemen",
              ].map((b) => (
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
            <div className="font-mono-label mb-2">New worker</div>
            <h1 className="font-display text-4xl font-black tracking-tight">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-[#4B5563]">
              Free for HCOB workers. Use email or continue with Google.
            </p>

            <form onSubmit={submit} className="mt-8 space-y-4">
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
