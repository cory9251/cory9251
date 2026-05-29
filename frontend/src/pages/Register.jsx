import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useAuth } from "@/context/AuthContext";
import { getErr } from "@/lib/api";
import { toast } from "sonner";
import { GoogleLogo, ArrowLeft } from "@phosphor-icons/react";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("worker");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const u = await register({ email, password, name, role });
      toast.success("Account created");
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
    <div className="min-h-screen bg-white" data-testid="register-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back home
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              Join the crew.
            </div>
            <div className="mt-6 max-w-md text-sm text-white/70">
              Workers get a profile, ID upload, and instant access to all open gigs near them.
            </div>
          </div>
          <div className="font-mono-label text-white/60">© GigBlast</div>
        </div>

        <div className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            <div className="font-mono-label mb-2">Create account</div>
            <h1 className="font-display text-4xl font-black tracking-tight">Get started</h1>

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
                  className="mt-2 h-12 rounded-none border-[#030712]"
                />
              </div>

              <div>
                <Label className="font-mono-label">I am</Label>
                <RadioGroup
                  value={role}
                  onValueChange={setRole}
                  className="mt-2 grid grid-cols-2 gap-2"
                >
                  <label
                    data-testid="role-worker"
                    className={`flex cursor-pointer items-center gap-3 border p-3 ${
                      role === "worker" ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#E5E7EB]"
                    }`}
                  >
                    <RadioGroupItem value="worker" id="rw" />
                    <div>
                      <div className="text-sm font-semibold">A Worker</div>
                      <div className="text-xs text-[#4B5563]">Find & accept gigs</div>
                    </div>
                  </label>
                  <label
                    data-testid="role-admin"
                    className={`flex cursor-pointer items-center gap-3 border p-3 ${
                      role === "admin" ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#E5E7EB]"
                    }`}
                  >
                    <RadioGroupItem value="admin" id="ra" />
                    <div>
                      <div className="text-sm font-semibold">A Manager</div>
                      <div className="text-xs text-[#4B5563]">Post & blast gigs</div>
                    </div>
                  </label>
                </RadioGroup>
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
                {loading ? "Creating…" : "Create account"}
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
              Already have an account?{" "}
              <Link to="/login" data-testid="link-login" className="font-semibold text-[#0044FF] hover:underline">
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
