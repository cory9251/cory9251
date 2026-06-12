import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Lock, CheckCircle, Eye, EyeSlash } from "@phosphor-icons/react";

export default function ResetPassword() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null); // email when successful
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (pw.length < 6) {
      setErr("Password must be at least 6 characters");
      return;
    }
    if (pw !== pw2) {
      setErr("Passwords don't match");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/reset-password", {
        token,
        new_password: pw,
      });
      setDone(data.email);
      toast.success("Password updated");
    } catch (e) {
      setErr(getErr(e));
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-6">
        <div className="max-w-md text-center">
          <div className="font-mono-label mb-2">Invalid link</div>
          <h1 className="font-display text-3xl font-black">No reset token found</h1>
          <p className="mt-3 text-sm text-[#4B5563]">
            This page needs a one-time token in the URL. Start over from the forgot-password screen.
          </p>
          <Link
            to="/forgot-password"
            className="mt-6 inline-flex items-center gap-2 bg-[#030712] px-5 py-3 text-sm font-bold text-white hover:bg-[#1f2937]"
          >
            Go to Forgot Password →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white" data-testid="reset-password-page">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-[#030712] p-12 text-white">
          <Link to="/login" className="font-mono-label flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft size={14} /> Back to sign in
          </Link>
          <div>
            <div className="font-display text-6xl font-black leading-[0.95]">
              Pick a new<br />password.
            </div>
            <p className="mt-6 max-w-md text-sm text-white/70">
              Single-use token — once you set the new password, the link burns.
            </p>
          </div>
          <div className="font-mono-label text-white/60">© HCOB Network</div>
        </div>

        <div className="flex items-center justify-center p-6 sm:p-12">
          <div className="w-full max-w-md">
            {done ? (
              <>
                <div className="font-mono-label mb-2">Done</div>
                <h1 className="font-display text-4xl font-black tracking-tight">
                  Password updated
                </h1>
                <div
                  data-testid="reset-success"
                  className="mt-6 border border-emerald-300 bg-emerald-50 p-5"
                >
                  <CheckCircle size={28} weight="fill" className="text-emerald-700" />
                  <p className="mt-3 text-sm text-emerald-900">
                    Password for <strong>{done}</strong> has been updated. All existing sessions
                    have been invalidated for security.
                  </p>
                </div>
                <Button
                  data-testid="reset-go-login"
                  onClick={() => nav("/login")}
                  className="mt-6 h-12 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
                >
                  Sign in with new password →
                </Button>
              </>
            ) : (
              <>
                <div className="font-mono-label mb-2">Step 2 of 2</div>
                <h1 className="font-display text-4xl font-black tracking-tight">
                  Set new password
                </h1>
                <p className="mt-2 text-sm text-[#4B5563]">
                  Make it strong — at least 6 characters. Once you confirm, your other sessions sign out.
                </p>
                <form onSubmit={submit} className="mt-6 space-y-4">
                  <div>
                    <Label htmlFor="pw" className="font-mono-label">New password</Label>
                    <div className="mt-2 flex items-center border border-[#030712] bg-white">
                      <Lock size={18} className="ml-3 text-[#4B5563]" />
                      <Input
                        data-testid="reset-pw"
                        id="pw"
                        type={show ? "text" : "password"}
                        required
                        minLength={6}
                        value={pw}
                        onChange={(e) => setPw(e.target.value)}
                        className="h-12 rounded-none border-0 bg-transparent focus-visible:ring-0"
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShow((s) => !s)}
                        className="mr-2 grid h-9 w-9 place-items-center text-[#4B5563] hover:text-[#030712]"
                        aria-label="Toggle visibility"
                      >
                        {show ? <EyeSlash size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="pw2" className="font-mono-label">Confirm password</Label>
                    <Input
                      data-testid="reset-pw2"
                      id="pw2"
                      type={show ? "text" : "password"}
                      required
                      minLength={6}
                      value={pw2}
                      onChange={(e) => setPw2(e.target.value)}
                      className="mt-2 h-12 rounded-none border-[#030712]"
                      autoComplete="new-password"
                    />
                  </div>
                  {err && (
                    <div data-testid="reset-error" className="border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                      {err}
                    </div>
                  )}
                  <Button
                    data-testid="reset-submit"
                    type="submit"
                    disabled={loading || !pw || !pw2}
                    className="h-12 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
                  >
                    {loading ? "Updating…" : "Update password"}
                  </Button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
