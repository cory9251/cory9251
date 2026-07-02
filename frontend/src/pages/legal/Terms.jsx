import React from "react";
import LegalLayout, { LegalSection } from "./LegalLayout";

/**
 * Public URL: /terms
 * Terms & Conditions for HCOB Network's text messaging program.
 * This is the URL to submit to Twilio for A2P 10DLC / campaign approval.
 */
export default function Terms() {
  return (
    <LegalLayout
      testId="terms-page"
      title="Terms & Conditions — HCOB Network Text Messaging Program"
      effectiveDate="February 26, 2026"
    >
      <LegalSection id="program-description" title="Program Description">
        <p>
          By submitting your mobile phone number through a form on{" "}
          <a
            className="text-[#0044FF] hover:underline"
            href="https://hcobnetwork.com"
          >
            hcobnetwork.com
          </a>{" "}
          or{" "}
          <a
            className="text-[#0044FF] hover:underline"
            href="https://hcobcleaners.com"
          >
            hcobcleaners.com
          </a>
          , you consent to receive text messages from HCOB Network related to:
        </p>
        <ul className="list-disc space-y-2 pl-6">
          <li>Quote follow-ups and booking confirmations</li>
          <li>Job scheduling and dispatch updates</li>
          <li>Invoice and payment reminders</li>
          <li>
            Contractor/VA opportunity notifications (if applicable to your
            account type)
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="opt-in" title="Opt-In Method">
        <p>
          Consent is collected via web form. By checking the consent box and
          submitting your number, you agree to receive text messages as
          described above.
        </p>
      </LegalSection>

      <LegalSection id="message-frequency" title="Message Frequency">
        <p>
          Message frequency varies depending on your activity (e.g., active
          jobs, pending quotes). You may receive anywhere from{" "}
          <strong>1&ndash;10 messages per month</strong>.
        </p>
      </LegalSection>

      <LegalSection id="cost" title="Cost">
        <p>
          Message and data rates may apply. Contact your mobile carrier for
          details on your plan.
        </p>
      </LegalSection>

      <LegalSection id="opt-out" title="Opt-Out">
        <p>
          You can cancel text messages at any time by replying{" "}
          <strong>STOP</strong> to any message we send. After you send STOP, we
          will send a confirmation message and you will not receive further
          texts unless you opt in again.
        </p>
      </LegalSection>

      <LegalSection id="help" title="Help">
        <p>
          Reply <strong>HELP</strong> to any message for assistance, or contact
          us directly:
        </p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            Phone: <strong>410-803-6204</strong> (HCOB Cleaners) /{" "}
            <strong>410-701-0570</strong> (HCOB Network)
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="carrier-liability" title="Carrier Liability">
        <p>Carriers are not liable for delayed or undelivered messages.</p>
      </LegalSection>

      <LegalSection id="supported-carriers" title="Supported Carriers">
        <p>
          Most major U.S. carriers are supported. Carriers are not liable for
          delayed or undelivered messages.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to These Terms">
        <p>
          HCOB Network may update these terms at any time. Continued use of
          our texting program after changes constitutes acceptance of the
          updated terms.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact">
        <p>Home Cleaners of Baltimore / HCOB Network</p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            <a
              className="text-[#0044FF] hover:underline"
              href="https://hcobcleaners.com"
            >
              hcobcleaners.com
            </a>{" "}
            |{" "}
            <a
              className="text-[#0044FF] hover:underline"
              href="https://hcobnetwork.com"
            >
              hcobnetwork.com
            </a>
          </li>
          <li>
            <strong>410-803-6204</strong> / <strong>410-701-0570</strong>
          </li>
        </ul>
      </LegalSection>
    </LegalLayout>
  );
}
