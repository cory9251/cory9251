import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  EnvelopeSimple,
  DeviceMobile,
  CheckCircle,
  WarningCircle,
  Lock,
  PaperPlaneTilt,
  Table,
} from "@phosphor-icons/react";

const PLACEHOLDER = "•••••••••• (saved)";

export default function AdminSettings() {
  const [data, setData] = useState(null);
  const [resendKey, setResendKey] = useState("");
  const [senderEmail, setSenderEmail] = useState("");
  const [twSid, setTwSid] = useState("");
  const [twToken, setTwToken] = useState("");
  const [twFrom, setTwFrom] = useState("");
  const [testEmailTo, setTestEmailTo] = useState("");
  const [testSmsTo, setTestSmsTo] = useState("");
  const [savingEmail, setSavingEmail] = useState(false);
  const [savingSms, setSavingSms] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [testingSms, setTestingSms] = useState(false);
  const [gsJson, setGsJson] = useState("");
  const [gsShareEmail, setGsShareEmail] = useState("");
  const [savingGs, setSavingGs] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/settings");
      setData(data);
      setSenderEmail(data.sender_email || "");
      setTwFrom(data.twilio_from_number || "");
      setGsShareEmail(data.google_sheets_share_email || "");
      // Secret fields stay blank — user types only to update
      setResendKey("");
      setTwSid("");
      setTwToken("");
      setGsJson("");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveEmail = async (e) => {
    e.preventDefault();
    setSavingEmail(true);
    try {
      const payload = { sender_email: senderEmail };
      if (resendKey.trim() !== "") payload.resend_api_key = resendKey.trim();
      await api.put("/admin/settings", payload);
      toast.success("Email settings saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingEmail(false);
    }
  };

  const clearResend = async () => {
    if (!confirm("Clear the saved Resend API key?")) return;
    try {
      await api.put("/admin/settings", { resend_api_key: "" });
      toast.success("Resend key cleared");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const saveSms = async (e) => {
    e.preventDefault();
    setSavingSms(true);
    try {
      const payload = { twilio_from_number: twFrom };
      if (twSid.trim() !== "") payload.twilio_account_sid = twSid.trim();
      if (twToken.trim() !== "") payload.twilio_auth_token = twToken.trim();
      await api.put("/admin/settings", payload);
      toast.success("Twilio settings saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingSms(false);
    }
  };

  const clearTwilio = async () => {
    if (!confirm("Clear all saved Twilio credentials?")) return;
    try {
      await api.put("/admin/settings", {
        twilio_account_sid: "",
        twilio_auth_token: "",
      });
      toast.success("Twilio credentials cleared");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const sendTest = async (channel) => {
    const to = channel === "email" ? testEmailTo : testSmsTo;
    if (!to.trim()) {
      toast.error(`Enter a ${channel === "email" ? "destination email" : "phone (+1…)"} to test`);
      return;
    }
    channel === "email" ? setTestingEmail(true) : setTestingSms(true);
    try {
      await api.post("/admin/settings/test", { channel, to: to.trim() });
      toast.success(`Test ${channel} sent`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      channel === "email" ? setTestingEmail(false) : setTestingSms(false);
    }
  };

  const saveGoogleSheets = async (e) => {
    e.preventDefault();
    setSavingGs(true);
    try {
      const payload = { google_sheets_share_email: gsShareEmail };
      if (gsJson.trim() !== "") {
        try {
          JSON.parse(gsJson.trim());
        } catch {
          toast.error("The pasted text isn't valid JSON. Paste the full service-account JSON file content.");
          setSavingGs(false);
          return;
        }
        payload.google_service_account_json = gsJson.trim();
      }
      await api.put("/admin/settings", payload);
      toast.success("Google Sheets settings saved");
      load();
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSavingGs(false);
    }
  };

  const clearGoogleSheets = async () => {
    if (!confirm("Clear the saved Google service account JSON?")) return;
    try {
      await api.put("/admin/settings", { google_service_account_json: "" });
      toast.success("Google service account cleared");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (!data) return <div className="p-10 font-mono-label">Loading…</div>;

  return (
    <div data-testid="admin-settings">
      <div className="border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div className="font-mono-label">System</div>
        <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
          Settings
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
          Paste your Resend and Twilio credentials here. Workers will only receive
          email or SMS blasts once the corresponding channel reads <span className="font-semibold text-[#10B981]">READY</span>.
        </p>
      </div>

      {/* Status strip */}
      <div className="grid grid-cols-2 border-b border-[#E5E7EB]">
        <StatusCard
          ready={data.email_ready}
          icon={EnvelopeSimple}
          channel="Email"
          provider="Resend"
        />
        <StatusCard
          ready={data.sms_ready}
          icon={DeviceMobile}
          channel="SMS"
          provider="Twilio"
        />
      </div>

      <BlastKillSwitchPanel />

      <ChangeMyPasswordPanel />

      <div className="grid grid-cols-1 gap-0 lg:grid-cols-2">
        {/* ---- Email / Resend ---- */}
        <form
          onSubmit={saveEmail}
          className="border-b border-r-0 border-[#E5E7EB] p-6 md:p-10 lg:border-r"
          data-testid="resend-form"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-mono-label flex items-center gap-2">
                <EnvelopeSimple size={14} weight="duotone" /> Email · Resend
              </div>
              <h2 className="mt-2 font-display text-2xl font-black">
                Resend credentials
              </h2>
              <p className="mt-2 text-sm text-[#4B5563]">
                Get an API key at{" "}
                <a
                  href="https://resend.com/api-keys"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#0044FF] underline"
                >
                  resend.com/api-keys
                </a>
                . Verify your sender domain to send to anyone.
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div>
              <Label className="font-mono-label flex items-center gap-1.5">
                <Lock size={11} /> Resend API key
              </Label>
              <Input
                data-testid="resend-api-key"
                type="password"
                value={resendKey}
                onChange={(e) => setResendKey(e.target.value)}
                placeholder={
                  data.resend_api_key.has_value
                    ? `${PLACEHOLDER} ending ${data.resend_api_key.last4}`
                    : "re_xxxxxxxxxxxx"
                }
                className="mt-2 h-11 rounded-none border-[#030712] font-mono text-sm"
              />
              <div className="mt-1 text-[11px] text-[#4B5563]">
                {data.resend_api_key.has_value
                  ? "Leave blank to keep the saved key."
                  : "Paste your key to enable email blasts."}
              </div>
            </div>

            <div>
              <Label className="font-mono-label">Sender email (from)</Label>
              <Input
                data-testid="sender-email"
                value={senderEmail}
                onChange={(e) => setSenderEmail(e.target.value)}
                placeholder="ops@yourdomain.com"
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                data-testid="save-resend"
                type="submit"
                disabled={savingEmail}
                className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              >
                {savingEmail ? "Saving…" : "Save email settings"}
              </Button>
              {data.resend_api_key.has_value && (
                <Button
                  data-testid="clear-resend"
                  type="button"
                  variant="outline"
                  onClick={clearResend}
                  className="h-11 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                >
                  Clear key
                </Button>
              )}
            </div>
          </div>

          <div className="mt-8 border-t border-[#E5E7EB] pt-6">
            <div className="font-mono-label">Send test email</div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Input
                data-testid="test-email-to"
                value={testEmailTo}
                onChange={(e) => setTestEmailTo(e.target.value)}
                placeholder="me@example.com"
                className="h-11 flex-1 min-w-[200px] rounded-none border-[#030712]"
              />
              <Button
                data-testid="send-test-email"
                type="button"
                onClick={() => sendTest("email")}
                disabled={testingEmail || !data.email_ready}
                className="h-11 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
              >
                <PaperPlaneTilt size={14} className="mr-2" />
                {testingEmail ? "Sending…" : "Send test"}
              </Button>
            </div>
            {!data.email_ready && (
              <div className="mt-2 text-xs text-[#4B5563]">
                Save a valid API key + sender first.
              </div>
            )}
          </div>
        </form>

        {/* ---- SMS / Twilio ---- */}
        <form
          onSubmit={saveSms}
          className="p-6 md:p-10"
          data-testid="twilio-form"
        >
          <div>
            <div className="font-mono-label flex items-center gap-2">
              <DeviceMobile size={14} weight="duotone" /> SMS · Twilio
            </div>
            <h2 className="mt-2 font-display text-2xl font-black">
              Twilio credentials
            </h2>
            <p className="mt-2 text-sm text-[#4B5563]">
              Find these at{" "}
              <a
                href="https://console.twilio.com"
                target="_blank"
                rel="noreferrer"
                className="text-[#0044FF] underline"
              >
                console.twilio.com
              </a>
              . You'll need an SMS-enabled phone number from Twilio.
            </p>
          </div>

          <div className="mt-6 space-y-4">
            <div>
              <Label className="font-mono-label flex items-center gap-1.5">
                <Lock size={11} /> Account SID
              </Label>
              <Input
                data-testid="twilio-sid"
                value={twSid}
                onChange={(e) => setTwSid(e.target.value)}
                placeholder={
                  data.twilio_account_sid.has_value
                    ? `${PLACEHOLDER} ending ${data.twilio_account_sid.last4}`
                    : "ACxxxxxxxx…"
                }
                className="mt-2 h-11 rounded-none border-[#030712] font-mono text-sm"
              />
            </div>
            <div>
              <Label className="font-mono-label flex items-center gap-1.5">
                <Lock size={11} /> Auth token
              </Label>
              <Input
                data-testid="twilio-token"
                type="password"
                value={twToken}
                onChange={(e) => setTwToken(e.target.value)}
                placeholder={
                  data.twilio_auth_token.has_value
                    ? `${PLACEHOLDER} ending ${data.twilio_auth_token.last4}`
                    : "your auth token"
                }
                className="mt-2 h-11 rounded-none border-[#030712] font-mono text-sm"
              />
              <div className="mt-1 text-[11px] text-[#4B5563]">
                Leave blank to keep the saved token.
              </div>
            </div>
            <div>
              <Label className="font-mono-label">From number (E.164)</Label>
              <Input
                data-testid="twilio-from"
                value={twFrom}
                onChange={(e) => setTwFrom(e.target.value)}
                placeholder="+15555550100"
                className="mt-2 h-11 rounded-none border-[#030712]"
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                data-testid="save-twilio"
                type="submit"
                disabled={savingSms}
                className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              >
                {savingSms ? "Saving…" : "Save SMS settings"}
              </Button>
              {(data.twilio_account_sid.has_value ||
                data.twilio_auth_token.has_value) && (
                <Button
                  data-testid="clear-twilio"
                  type="button"
                  variant="outline"
                  onClick={clearTwilio}
                  className="h-11 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                >
                  Clear credentials
                </Button>
              )}
            </div>
          </div>

          <div className="mt-8 border-t border-[#E5E7EB] pt-6">
            <div className="font-mono-label">Send test SMS</div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Input
                data-testid="test-sms-to"
                value={testSmsTo}
                onChange={(e) => setTestSmsTo(e.target.value)}
                placeholder="+15555550100"
                className="h-11 flex-1 min-w-[200px] rounded-none border-[#030712]"
              />
              <Button
                data-testid="send-test-sms"
                type="button"
                onClick={() => sendTest("sms")}
                disabled={testingSms || !data.sms_ready}
                className="h-11 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
              >
                <PaperPlaneTilt size={14} className="mr-2" />
                {testingSms ? "Sending…" : "Send test"}
              </Button>
            </div>
            {!data.sms_ready && (
              <div className="mt-2 text-xs text-[#4B5563]">
                Save SID + token + from-number first.
              </div>
            )}
          </div>
        </form>
      </div>

      {/* ---- Google Sheets export ---- */}
      <form
        onSubmit={saveGoogleSheets}
        className="border-t border-[#E5E7EB] p-6 md:p-10"
        data-testid="google-sheets-form"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-mono-label flex items-center gap-2">
              <Table size={14} weight="duotone" /> Reports · Google Sheets
            </div>
            <h2 className="mt-2 font-display text-2xl font-black">
              Google Sheets export
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
              Paste the full JSON of a Google Cloud{" "}
              <span className="font-semibold">service account</span> that has the
              Sheets API + Drive API enabled. HCOB will use it to create fresh
              spreadsheets when you export reports.
            </p>
            <p className="mt-2 max-w-2xl text-xs text-[#4B5563]">
              How: console.cloud.google.com → IAM &amp; Admin → Service Accounts →
              Create → Add key (JSON). Enable Sheets API + Drive API. Then paste
              the JSON below.
            </p>
          </div>
          <div
            className={`hidden md:block shrink-0 px-3 py-1 text-[10px] font-bold tracking-widest text-white ${
              data.google_sheets_ready ? "bg-[#10B981]" : "bg-[#F59E0B]"
            }`}
            data-testid="gs-status-badge"
          >
            {data.google_sheets_ready ? "READY" : "NOT CONFIGURED"}
          </div>
        </div>

        <div className="mt-6 space-y-4">
          <div>
            <Label className="font-mono-label flex items-center gap-1.5">
              <Lock size={11} /> Service account JSON
            </Label>
            <Textarea
              data-testid="gs-json"
              value={gsJson}
              onChange={(e) => setGsJson(e.target.value)}
              rows={6}
              placeholder={
                data.google_sheets_ready
                  ? `Saved — service account: ${data.google_sheets_service_email}\nPaste fresh JSON here to replace.`
                  : '{\n  "type": "service_account",\n  "project_id": "...",\n  ...\n}'
              }
              className="mt-2 rounded-none border-[#030712] font-mono text-xs"
            />
            {data.google_sheets_ready && (
              <div className="mt-2 text-xs text-[#065F46]">
                Connected as <span className="font-semibold">{data.google_sheets_service_email}</span>
                . Make sure your destination drive share is set below.
              </div>
            )}
          </div>

          <div>
            <Label className="font-mono-label">Share new sheets with (your Google account email)</Label>
            <Input
              data-testid="gs-share-email"
              type="email"
              value={gsShareEmail}
              onChange={(e) => setGsShareEmail(e.target.value)}
              placeholder="you@hcobcleaners.com"
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
            <div className="mt-1 text-xs text-[#4B5563]">
              Required — service accounts don't have a Drive UI, so we share each
              exported sheet with this email so you can open it.
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          <Button
            data-testid="save-gs-btn"
            type="submit"
            disabled={savingGs}
            className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            {savingGs ? "Saving…" : "Save Google Sheets settings"}
          </Button>
          {data.google_sheets_ready && (
            <Button
              data-testid="clear-gs-btn"
              type="button"
              variant="outline"
              onClick={clearGoogleSheets}
              className="h-11 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
            >
              Clear service account
            </Button>
          )}
        </div>
      </form>

      <AdminUsersPanel />

      {data.updated_at && (
        <div className="border-t border-[#E5E7EB] px-6 py-4 text-xs text-[#4B5563] md:px-10">
          Last updated {new Date(data.updated_at).toLocaleString()}
          {data.updated_by ? ` by ${data.updated_by}` : ""}
        </div>
      )}
    </div>
  );
}

function StatusCard({ ready, icon: Icon, channel, provider }) {
  return (
    <div className="flex items-center gap-4 border-r border-[#E5E7EB] p-6 last:border-r-0">
      <div
        className={`grid h-10 w-10 place-items-center ${
          ready ? "bg-[#10B981]" : "bg-[#F59E0B]"
        } text-white`}
      >
        <Icon size={20} weight="duotone" />
      </div>
      <div>
        <div className="font-mono-label">{channel} · {provider}</div>
        <div className="mt-1 flex items-center gap-2 font-display text-lg font-bold">
          {ready ? (
            <>
              <CheckCircle size={16} weight="fill" className="text-[#10B981]" />
              READY
            </>
          ) : (
            <>
              <WarningCircle size={16} weight="fill" className="text-[#F59E0B]" />
              NOT CONFIGURED
            </>
          )}
        </div>
      </div>
    </div>
  );
}


/**
 * Blast safety panel — Owner-only kill switch and recent-blast audit.
 * Lets the Owner instantly disable every /blast endpoint without a redeploy.
 * Added after the Feb-2026 SEV1 quota-drain incident.
 */
function BlastKillSwitchPanel() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/blast-kill-switch");
      setStatus(data);
    } catch (e) {
      // Non-fatal — non-admins shouldn't see this panel anyway.
      setStatus({ enabled: false, source: "off", cooldown_seconds: 300, error: true });
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async () => {
    if (!status) return;
    const next = !status.enabled;
    if (next && !window.confirm("Disable ALL blasts? Admins won't be able to send emails / SMS / push until you turn this back off.")) {
      return;
    }
    setBusy(true);
    try {
      await api.post("/admin/blast-kill-switch", { enabled: next });
      toast.success(next ? "Blasts disabled — every /blast endpoint now returns 503." : "Blasts re-enabled.");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status || status.error) return null;

  const envLocked = status.source === "env";
  const on = status.enabled;

  return (
    <div
      data-testid="blast-kill-switch-panel"
      className={`border-b border-[#E5E7EB] p-6 md:p-10 ${on ? "bg-[#FEF2F2]" : ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono-label">Safety</div>
          <h2 className="mt-2 font-display text-2xl font-black flex items-center gap-2">
            <WarningCircle size={20} weight={on ? "fill" : "duotone"} className={on ? "text-[#DC2626]" : ""} />
            Blast kill switch · {on ? <span className="text-[#DC2626]">ON</span> : <span className="text-[#10B981]">OFF</span>}
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
            When ON, every <code className="rounded bg-[#F3F4F6] px-1 font-mono text-xs">/blast</code> endpoint returns 503 and any
            in-flight background fan-out exits immediately. Use this to instantly stop a runaway blast.
            Cooldown between repeat blasts of the same gig/project: <strong>{status.cooldown_seconds}s</strong>.
          </p>
          {status.toggled_at && (
            <p className="mt-1 text-xs text-[#737373]">
              Last toggled <strong>{new Date(status.toggled_at).toLocaleString()}</strong>
              {status.toggled_by ? <> by <strong>{status.toggled_by}</strong></> : null}
            </p>
          )}
          {envLocked && (
            <p className="mt-2 text-xs text-[#DC2626]">
              Currently forced ON by the <code>BLAST_KILL_SWITCH</code> environment variable. UI toggle is read-only until that env var is removed.
            </p>
          )}
        </div>
        <Button
          data-testid="blast-kill-switch-toggle"
          onClick={toggle}
          disabled={busy || envLocked}
          className={`h-10 rounded-none ${on ? "bg-[#10B981] text-white hover:bg-[#059669]" : "bg-[#DC2626] text-white hover:bg-[#B91C1C]"}`}
        >
          {busy ? "Working…" : on ? "Re-enable blasts" : "Disable all blasts"}
        </Button>
      </div>
    </div>
  );
}


/**
 * Change-my-password panel — self-service. Requires current password.
 * Always visible at the top of Settings; works for any logged-in admin.
 */
function ChangeMyPasswordPanel() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    if (next !== confirm) {
      toast.error("Passwords don't match");
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
      setConfirm("");
      setOpen(false);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="change-my-password-panel"
      className="border-b border-[#E5E7EB] p-6 md:p-10"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono-label">Security</div>
          <h2 className="mt-2 font-display text-2xl font-black flex items-center gap-2">
            <Lock size={20} weight="duotone" /> Change my password
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
            Update your own login password. Requires your current password. Forgot it?
            Sign out and use the &ldquo;Forgot password&rdquo; link on the login screen.
          </p>
        </div>
        {!open && (
          <Button
            data-testid="open-change-pw-btn"
            onClick={() => setOpen(true)}
            className="h-10 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            Change my password
          </Button>
        )}
      </div>

      {open && (
        <form
          onSubmit={submit}
          className="mt-5 grid grid-cols-1 gap-3 border border-[#030712] bg-[#F9FAFB] p-4 md:max-w-xl"
        >
          <div>
            <Label className="font-mono-label">Current password</Label>
            <Input
              data-testid="change-pw-current"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
              autoComplete="current-password"
            />
          </div>
          <div>
            <Label className="font-mono-label">New password (6+ chars)</Label>
            <Input
              data-testid="change-pw-new"
              type="password"
              minLength={6}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
              autoComplete="new-password"
            />
          </div>
          <div>
            <Label className="font-mono-label">Confirm new password</Label>
            <Input
              data-testid="change-pw-confirm"
              type="password"
              minLength={6}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
              autoComplete="new-password"
            />
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                setCurrent("");
                setNext("");
                setConfirm("");
              }}
              className="h-10 rounded-none border-[#030712]"
            >
              Cancel
            </Button>
            <Button
              data-testid="change-pw-submit"
              type="submit"
              disabled={busy || !current || !next || !confirm}
              className="h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {busy ? "Updating…" : "Update password"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}


/**
 * Admin users management — lists all admin accounts, allows creating new
 * ones (full-access or read-only), and toggling/demoting/deleting existing
 * ones. Lives inline at the bottom of Settings.
 */
function AdminUsersPanel() {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resetInfo, setResetInfo] = useState(null);
  // New-admin form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isReadOnly, setIsReadOnly] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/admins");
      setAdmins(data);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/admin/admins", {
        name,
        email,
        password,
        is_read_only: isReadOnly,
      });
      toast.success(`Created ${isReadOnly ? "read-only" : "full-access"} admin`);
      setName("");
      setEmail("");
      setPassword("");
      setIsReadOnly(false);
      setShowForm(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleReadOnly = async (a) => {
    try {
      await api.put(`/admin/admins/${a.user_id}`, {
        is_read_only: !a.is_read_only,
      });
      toast.success(
        a.is_read_only
          ? `${a.name} can now make changes`
          : `${a.name} is now read-only`
      );
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const demote = async (a) => {
    if (!window.confirm(`Demote ${a.name} to a regular worker?`)) return;
    try {
      await api.put(`/admin/admins/${a.user_id}`, { demote_to_worker: true });
      toast.success(`${a.name} demoted to worker`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const remove = async (a) => {
    if (
      !window.confirm(
        `Delete ${a.name}'s admin account? This cannot be undone.`
      )
    )
      return;
    try {
      await api.delete(`/admin/admins/${a.user_id}`);
      toast.success(`Deleted ${a.name}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const resetPw = async (a) => {
    if (!window.confirm(`Force-reset password for ${a.name}? All their sessions will end immediately.`)) return;
    try {
      const { data } = await api.post(`/admin/users/${a.user_id}/reset-password`, {});
      setResetInfo({ email: data.email, name: data.name, password: data.new_password });
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  return (
    <div
      data-testid="admin-users-panel"
      className="border-t border-[#E5E7EB] p-6 md:p-10"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono-label">Access control</div>
          <h2 className="mt-2 font-display text-2xl font-black">Admin users</h2>
          <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
            Full-access admins can do anything. Read-only admins can view every
            page but can't make changes — perfect for accountants, auditors, or
            new staff who are still learning the platform.
          </p>
        </div>
        {!showForm && (
          <Button
            data-testid="show-add-admin-btn"
            onClick={() => setShowForm(true)}
            className="h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            + Add admin user
          </Button>
        )}
      </div>

      {showForm && (
        <form
          data-testid="add-admin-form"
          onSubmit={submit}
          className="mt-5 grid grid-cols-1 gap-3 border border-[#030712] bg-[#F9FAFB] p-4 md:grid-cols-2"
        >
          <div>
            <Label className="font-mono-label">Name</Label>
            <Input
              data-testid="new-admin-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Sam Johnson"
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div>
            <Label className="font-mono-label">Email</Label>
            <Input
              data-testid="new-admin-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="sam@hcobcleaners.com"
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div className="md:col-span-2">
            <Label className="font-mono-label">Temp password (8+ chars)</Label>
            <Input
              data-testid="new-admin-password"
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Share securely; they can change it later"
              required
              className="mt-2 h-11 rounded-none border-[#030712]"
            />
          </div>
          <div className="md:col-span-2">
            <label className="flex h-11 cursor-pointer items-center gap-2 border border-[#030712] bg-white px-3">
              <input
                data-testid="new-admin-readonly"
                type="checkbox"
                checked={isReadOnly}
                onChange={(e) => setIsReadOnly(e.target.checked)}
                className="accent-[#0044FF]"
              />
              <span className="text-sm">
                <span className="font-bold">Read-only access</span> — can view
                everything but can't create / edit / delete anything
              </span>
            </label>
          </div>
          <div className="flex flex-wrap justify-end gap-2 md:col-span-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowForm(false)}
              className="rounded-none"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={busy}
              data-testid="submit-add-admin"
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {busy ? "Creating…" : "Create admin"}
            </Button>
          </div>
        </form>
      )}

      <div className="mt-6 overflow-x-auto border border-[#E5E7EB]">
        <table className="w-full text-sm">
          <thead className="bg-[#F9FAFB]">
            <tr className="text-left">
              <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                Name
              </th>
              <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                Email
              </th>
              <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                Access
              </th>
              <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">
                Created
              </th>
              <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-[#4B5563]">
                  Loading…
                </td>
              </tr>
            ) : admins.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-[#4B5563]">
                  No admins yet — odd.
                </td>
              </tr>
            ) : (
              admins.map((a) => (
                <tr
                  key={a.user_id}
                  data-testid={`admin-row-${a.user_id}`}
                  className="hover:bg-[#F9FAFB]"
                >
                  <td className="border-b border-[#E5E7EB] px-3 py-2 font-semibold">
                    {a.name}
                    {a.is_self && (
                      <span className="ml-1.5 inline-flex items-center rounded-full bg-[#0044FF] px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-white">
                        you
                      </span>
                    )}
                  </td>
                  <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs text-[#4B5563]">
                    {a.email}
                  </td>
                  <td className="border-b border-[#E5E7EB] px-3 py-2">
                    {a.is_read_only ? (
                      <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">
                        READ-ONLY
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">
                        FULL
                      </span>
                    )}
                  </td>
                  <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs text-[#4B5563]">
                    {a.created_at
                      ? new Date(a.created_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="border-b border-[#E5E7EB] px-3 py-2">
                    {!a.is_self && (
                      <div className="flex flex-wrap justify-end gap-1.5">
                        <Button
                          data-testid={`reset-pw-admin-${a.user_id}`}
                          onClick={() => resetPw(a)}
                          variant="outline"
                          className="h-7 rounded-none border-[#0044FF] px-2 text-[10px] text-[#0044FF] hover:bg-[#0044FF] hover:text-white"
                        >
                          Reset PW
                        </Button>
                        <Button
                          data-testid={`toggle-readonly-${a.user_id}`}
                          onClick={() => toggleReadOnly(a)}
                          variant="outline"
                          className="h-7 rounded-none border-[#030712] px-2 text-[10px]"
                        >
                          {a.is_read_only ? "Grant full" : "Make read-only"}
                        </Button>
                        <Button
                          data-testid={`demote-${a.user_id}`}
                          onClick={() => demote(a)}
                          variant="outline"
                          className="h-7 rounded-none border-[#F59E0B] px-2 text-[10px] text-[#92400E]"
                        >
                          Demote
                        </Button>
                        <Button
                          data-testid={`delete-admin-${a.user_id}`}
                          onClick={() => remove(a)}
                          variant="outline"
                          className="h-7 rounded-none border-[#EF4444] px-2 text-[10px] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                        >
                          Delete
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {resetInfo && (
        <div
          data-testid="reset-pw-modal"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          onClick={() => setResetInfo(null)}
        >
          <div
            className="w-full max-w-md border-2 border-[#0044FF] bg-white p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-mono-label text-[#0044FF]">Password reset</div>
            <h3 className="mt-1 font-display text-2xl font-black">Share these credentials</h3>
            <p className="mt-2 text-sm text-[#4B5563]">
              {resetInfo.name}&apos;s sessions have been terminated. They&apos;ll be prompted to change
              this temporary password on their next login.
            </p>
            <div className="mt-4 border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="text-xs text-[#4B5563]">Email</div>
              <div className="font-mono">{resetInfo.email}</div>
            </div>
            <div className="mt-2 border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="text-xs text-[#4B5563]">Temporary password</div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="font-mono text-lg">{resetInfo.password}</span>
                <button
                  data-testid="copy-reset-pw"
                  onClick={() => {
                    navigator.clipboard.writeText(resetInfo.password);
                    toast.success("Copied to clipboard");
                  }}
                  className="border border-[#030712] px-3 py-1 text-xs hover:bg-[#030712] hover:text-white"
                >
                  Copy
                </button>
              </div>
            </div>
            <Button
              data-testid="close-reset-pw-modal"
              onClick={() => setResetInfo(null)}
              className="mt-5 h-10 w-full rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
            >
              Done
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

