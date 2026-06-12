import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, EnvelopeSimple, CheckCircle } from "@phosphor-icons/react";

export default function ForgotPassword() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white" data-testid="forgot-password-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/login" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back to sign in
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              Forgot password?<br />Happens to all of us.
            </div>
            <p className="mt-6 max-w-md text-sm text-white/70">
              Enter your email. We&apos;ll send a single-use reset link that&apos;s valid for 60 minutes.
            </p>
          </div>
          <div className="font-mono-label text-white/60">© HCOB Network</div>
        </div>

        <div className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            <div className="font-mono-label mb-2">Account recovery</div>
            <h1 className="font-display text-4xl font-black tracking-tight">
              Reset your password
            </h1>
            <p className="mt-2 text-sm text-[#4B5563]">
              We&apos;ll email you a secure link. Works for workers, VAs, and admins.
            </p>

            {sent ? (
              <div
                data-testid="forgot-sent-block"
                className="mt-8 border border-emerald-300 bg-emerald-50 p-5"
              >
                <CheckCircle size={28} weight="fill" className="text-emerald-700" />
                <div className="mt-3 font-display text-xl font-black">Check your inbox</div>
                <p className="mt-2 text-sm text-emerald-900">
                  If <strong>{email}</strong> is registered, a one-time reset link is on its way.
                  The link expires in 60 minutes and can only be used once.
                </p>
                <p className="mt-3 text-xs text-emerald-800">
                  Didn&apos;t get it? Check spam, or contact your Owner to force-reset directly from the admin panel.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    onClick={() => nav("/login")}
                    className="rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
                  >
                    Back to sign in
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setSent(false);
                      setEmail("");
                    }}
                    className="rounded-none border-[#030712]"
                  >
                    Send another link
                  </Button>
                </div>
              </div>
            ) : (
              <form onSubmit={submit} className="mt-6 space-y-4">
                <div>
                  <Label htmlFor="email" className="font-mono-label">Email</Label>
                  <div className="mt-2 flex items-center border border-[#030712] bg-white">
                    <EnvelopeSimple size={18} className="ml-3 text-[#4B5563]" />
                    <Input
                      data-testid="forgot-email"
                      id="email"
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="h-12 rounded-none border-0 bg-transparent focus-visible:ring-0"
                      autoComplete="email"
                    />
                  </div>
                </div>
                {err && (
                  <div data-testid="forgot-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {err}
                  </div>
                )}
                <Button
                  data-testid="forgot-submit"
                  type="submit"
                  disabled={loading || !email}
                  className="h-12 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
                >
                  {loading ? "Sending…" : "Send reset link"}
                </Button>
              </form>
            )}

            <div className="mt-8 text-sm text-[#4B5563]">
              Remembered it?{" "}
              <Link to="/login" data-testid="back-to-login" className="font-semibold text-[#0044FF] hover:underline">
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
