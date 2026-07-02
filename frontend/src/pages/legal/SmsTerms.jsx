import React from "react";
import { Link } from "react-router-dom";
import LegalLayout, { LegalSection } from "./LegalLayout";

/**
 * Public URL: /sms-terms
 * Concise SMS-specific terms — the "one-pager" version to link in opt-in
 * forms and share directly with mobile carriers.
 */
export default function SmsTerms() {
  return (
    <LegalLayout
      testId="sms-terms-page"
      title="SMS Messaging Terms"
      effectiveDate="February 26, 2026"
    >
      <p className="text-[#4B5563]">
        This page describes HCOB Network&rsquo;s text messaging program,
        separate from our{" "}
        <Link to="/terms" className="text-[#0044FF] hover:underline">
          general Terms &amp; Conditions
        </Link>
        , for transparency with mobile carriers and customers.
      </p>

      <LegalSection id="what-youre-signing-up-for" title="What You're Signing Up For">
        <p>
          When you enter your phone number on an HCOB Network or HCOB Cleaners
          form and opt in, you agree to receive automated and manual text
          messages about:
        </p>
        <ul className="list-disc space-y-2 pl-6">
          <li>Quotes, bookings, and job scheduling</li>
          <li>Dispatch and project status updates</li>
          <li>Payment/invoice reminders</li>
          <li>
            Referral, contractor, or VA opportunities (where applicable)
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="consent" title="Consent Is Not a Condition of Purchase">
        <p>
          Opting in to text messages is not required to purchase or receive
          HCOB services. You can still book a service or work with us without
          signing up for texts.
        </p>
      </LegalSection>

      <LegalSection id="frequency-cost" title="Frequency & Cost">
        <p>
          Message frequency varies by activity. Message and data rates may
          apply &mdash; check with your carrier.
        </p>
      </LegalSection>

      <LegalSection id="opt-out" title="How to Opt Out">
        <p>
          Text <strong>STOP</strong> at any time to stop receiving messages.
          <br />
          Text <strong>HELP</strong> for support.
        </p>
      </LegalSection>

      <LegalSection id="privacy" title="Privacy">
        <p>
          We do not share your mobile number or opt-in status with third
          parties for their own marketing purposes. See our full{" "}
          <Link to="/privacy" className="text-[#0044FF] hover:underline">
            Privacy Policy
          </Link>{" "}
          for details.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact Us">
        <p>Home Cleaners of Baltimore / HCOB Network</p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            <strong>410-803-6204</strong> (HCOB Cleaners)
          </li>
          <li>
            <strong>410-701-0570</strong> (HCOB Network)
          </li>
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
        </ul>
      </LegalSection>
    </LegalLayout>
  );
}
