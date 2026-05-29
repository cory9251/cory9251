import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  EnvelopeSimple,
  DeviceMobile,
  CheckCircle,
  WarningCircle,
  Lock,
  PaperPlaneTilt,
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

  const load = async () => {
    try {
      const { data } = await api.get("/admin/settings");
      setData(data);
      setSenderEmail(data.sender_email || "");
      setTwFrom(data.twilio_from_number || "");
      // Secret fields stay blank — user types only to update
      setResendKey("");
      setTwSid("");
      setTwToken("");
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
