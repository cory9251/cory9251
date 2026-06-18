import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  BellRinging,
  BellSlash,
  CheckCircle,
  Warning,
  ArrowSquareOut,
  ShareNetwork,
  DeviceMobile,
} from "@phosphor-icons/react";
import {
  enablePush,
  disablePush,
  sendTestPush,
  getPushStatus,
  pushReadiness,
  detectPlatform,
} from "@/lib/push";

export default function PushNotificationToggle() {
  const [readiness, setReadiness] = useState("unsupported");
  const [serverStatus, setServerStatus] = useState({
    enabled: false,
    device_count: 0,
    server_configured: true,
  });
  const [working, setWorking] = useState(false);
  const platform = detectPlatform();

  const refresh = async () => {
    setReadiness(pushReadiness());
    setServerStatus(await getPushStatus());
  };

  useEffect(() => {
    refresh();
  }, []);

  const turnOn = async () => {
    setWorking(true);
    try {
      await enablePush();
      toast.success("Push notifications enabled on this device.");
      await refresh();
    } catch (e) {
      toast.error(e.message || "Couldn't enable push notifications.");
    } finally {
      setWorking(false);
    }
  };

  const turnOff = async () => {
    if (!window.confirm("Turn off push notifications on this device?")) return;
    setWorking(true);
    try {
      await disablePush();
      toast.success("Push notifications disabled on this device.");
      await refresh();
    } catch (e) {
      toast.error(e.message || "Couldn't disable push notifications.");
    } finally {
      setWorking(false);
    }
  };

  const fireTest = async () => {
    setWorking(true);
    try {
      const r = await sendTestPush();
      if (r.sent > 0) {
        toast.success(`Test sent to ${r.sent} device${r.sent === 1 ? "" : "s"}.`);
      } else {
        toast.error(
          "No active devices found. Try enabling push first, or check your browser permission."
        );
      }
    } catch (e) {
      toast.error("Test push failed. Try toggling push off and on again.");
    } finally {
      setWorking(false);
    }
  };

  // ----- iOS PWA install instructions -----
  if (readiness === "ios_needs_pwa") {
    return (
      <Card
        title="Push notifications"
        subtitle="On iPhone, you need to add HCOB to your Home Screen first."
        icon={DeviceMobile}
        accent="amber"
        testid="push-card-ios"
      >
        <ol className="mt-3 space-y-2 text-sm text-[#030712]">
          <li className="flex gap-3">
            <Step n="1" />
            <span>
              Tap the <strong>Share</strong> button{" "}
              <ShareNetwork
                size={16}
                weight="fill"
                className="inline align-text-bottom"
              />{" "}
              at the bottom of Safari.
            </span>
          </li>
          <li className="flex gap-3">
            <Step n="2" />
            <span>
              Scroll down and tap <strong>Add to Home Screen</strong>.
            </span>
          </li>
          <li className="flex gap-3">
            <Step n="3" />
            <span>
              Open <strong>HCOB Network</strong> from your Home Screen — come back
              here and the toggle will appear.
            </span>
          </li>
        </ol>
        <div className="mt-4 inline-flex items-center gap-1 text-[11px] text-[#4B5563]">
          <Warning size={12} weight="fill" className="text-[#F59E0B]" />
          Apple requires this once. SMS still works if you skip it.
        </div>
      </Card>
    );
  }

  // ----- Unsupported browser -----
  if (readiness === "unsupported") {
    return (
      <Card
        title="Push notifications"
        subtitle="This browser doesn't support push notifications."
        icon={BellSlash}
        accent="grey"
        testid="push-card-unsupported"
      >
        <p className="mt-2 text-xs text-[#4B5563]">
          Try Chrome, Firefox, or the Safari iOS app (after Add to Home Screen).
          You'll still receive SMS and email for blasts.
        </p>
      </Card>
    );
  }

  // ----- Blocked by user (need to flip browser setting) -----
  if (readiness === "blocked") {
    return (
      <Card
        title="Push notifications"
        subtitle="You blocked notifications on this device."
        icon={BellSlash}
        accent="red"
        testid="push-card-blocked"
      >
        <p className="mt-2 text-xs text-[#4B5563]">
          Open your browser site settings and switch{" "}
          <strong>Notifications</strong> back to <em>Allow</em>, then refresh
          this page. (Chrome: tap the lock icon → Permissions →
          Notifications.)
        </p>
        <a
          href="https://support.google.com/chrome/answer/3220216"
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[#0044FF] hover:underline"
        >
          How to allow notifications <ArrowSquareOut size={12} />
        </a>
      </Card>
    );
  }

  // ----- Enabled state -----
  if (serverStatus.enabled || readiness === "enabled") {
    return (
      <Card
        title="Push notifications"
        subtitle={`Active on ${serverStatus.device_count} device${
          serverStatus.device_count === 1 ? "" : "s"
        }.`}
        icon={CheckCircle}
        accent="green"
        testid="push-card-enabled"
      >
        <p className="mt-2 text-xs text-[#4B5563]">
          You&apos;ll get a push the moment HCOB blasts a new assignment or project — even
          when the browser is closed.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            data-testid="push-test-btn"
            disabled={working}
            onClick={fireTest}
            className="border border-[#030712] bg-white px-3 py-2 text-xs font-semibold hover:bg-[#030712] hover:text-white disabled:opacity-50"
          >
            <BellRinging size={12} className="mr-1 inline" weight="duotone" />
            Send me a test push
          </button>
          <button
            data-testid="push-disable-btn"
            disabled={working}
            onClick={turnOff}
            className="border border-[#E5E7EB] bg-white px-3 py-2 text-xs font-semibold text-[#4B5563] hover:border-[#EF4444] hover:text-[#EF4444] disabled:opacity-50"
          >
            <BellSlash size={12} className="mr-1 inline" />
            Turn off on this device
          </button>
        </div>
      </Card>
    );
  }

  // ----- Available — ready to enable -----
  return (
    <Card
      title="Push notifications"
      subtitle="Get a push the second new assignments hit the feed."
      icon={BellRinging}
      accent="blue"
      testid="push-card-available"
    >
      <p className="mt-2 text-xs text-[#4B5563]">
        Faster than SMS. Free. Works even when this tab is closed. Tap below to
        enable — your browser will ask you once.
      </p>
      {platform === "android" && (
        <p className="mt-2 text-[11px] text-[#4B5563]">
          Heads-up: when the prompt appears, tap <strong>Allow</strong>.
        </p>
      )}
      <button
        data-testid="push-enable-btn"
        disabled={working}
        onClick={turnOn}
        className="mt-4 inline-flex items-center gap-2 bg-[#0044FF] px-4 py-3 text-sm font-bold text-white hover:bg-[#0036cc] disabled:opacity-60"
      >
        <BellRinging size={14} weight="fill" />
        {working ? "Enabling…" : "Enable push notifications"}
      </button>
    </Card>
  );
}

function Card({ title, subtitle, icon: Icon, accent, testid, children }) {
  const accents = {
    blue: { border: "border-[#0044FF]", bg: "bg-[#F0F4FF]", icon: "text-[#0044FF]" },
    green: { border: "border-[#22C55E]", bg: "bg-[#ECFDF5]", icon: "text-[#22C55E]" },
    red: { border: "border-[#EF4444]", bg: "bg-[#FEF2F2]", icon: "text-[#EF4444]" },
    amber: { border: "border-[#F59E0B]", bg: "bg-[#FEF3C7]", icon: "text-[#92400E]" },
    grey: { border: "border-[#E5E7EB]", bg: "bg-[#F9FAFB]", icon: "text-[#4B5563]" },
  };
  const a = accents[accent] || accents.grey;
  return (
    <div
      data-testid={testid}
      className={`border ${a.border} ${a.bg} p-5 gb-tactile`}
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${a.icon}`}>
          <Icon size={22} weight="duotone" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-base font-black tracking-tight">
            {title}
          </div>
          <div className="mt-0.5 text-xs text-[#4B5563]">{subtitle}</div>
          {children}
        </div>
      </div>
    </div>
  );
}

function Step({ n }) {
  return (
    <span className="grid h-6 w-6 shrink-0 place-items-center bg-[#030712] text-[10px] font-black text-white">
      {n}
    </span>
  );
}
