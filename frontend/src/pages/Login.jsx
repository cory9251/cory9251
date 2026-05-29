import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { getErr } from "@/lib/api";
import { toast } from "sonner";
import { GoogleLogo, ArrowLeft } from "@phosphor-icons/react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success("Welcome back");
      nav(u.role === "admin" ? "/admin" : "/app", { replace: true });
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
    <div className="min-h-screen bg-white" data-testid="login-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back home
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              Welcome back
              <br />
              to HCOB.
            </div>
            <div className="mt-6 max-w-md text-sm text-white/70">
              Sign in to the HCOB Network — workers see their feed, HCOB staff see the operations console.
            </div>
          </div>
          <div className="font-mono-label text-white/60">© HCOB Network</div>
        </div>
        <div className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            <div className="font-mono-label mb-2">Sign in</div>
            <h1 className="font-display text-4xl font-black tracking-tight">Welcome back</h1>
            <p className="mt-2 text-sm text-[#4B5563]">Use your email or continue with Google.</p>

            <form onSubmit={submit} className="mt-8 space-y-4">
              <div>
                <Label htmlFor="email" className="font-mono-label">Email</Label>
                <Input
                  data-testid="login-email"
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>
              <div>
                <Label htmlFor="password" className="font-mono-label">Password</Label>
                <Input
                  data-testid="login-password"
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>
              {err && (
                <div data-testid="login-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {err}
                </div>
              )}
              <Button
                data-testid="login-submit"
                type="submit"
                disabled={loading}
                className="h-12 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
              >
                {loading ? "Signing in…" : "Sign in"}
              </Button>
            </form>

            <div className="my-6 flex items-center gap-3 text-xs text-[#4B5563]">
              <div className="h-px flex-1 bg-[#E5E7EB]" />
              OR
              <div className="h-px flex-1 bg-[#E5E7EB]" />
            </div>

            <Button
              data-testid="login-google-btn"
              type="button"
              variant="outline"
              onClick={google}
              className="h-12 w-full rounded-none border-[#030712]"
            >
              <GoogleLogo size={20} weight="bold" className="mr-2" /> Continue with Google
            </Button>

            <div className="mt-8 text-sm text-[#4B5563]">
              No account?{" "}
              <Link to="/register" data-testid="link-register" className="font-semibold text-[#0044FF] hover:underline">
                Create one
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
