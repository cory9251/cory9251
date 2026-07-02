import React from "react";
import LegalLayout, { LegalSection } from "./LegalLayout";

/**
 * Public URL: /privacy
 * This is the URL to submit to Twilio for A2P 10DLC / campaign approval.
 */
export default function PrivacyPolicy() {
  return (
    <LegalLayout
      testId="privacy-policy-page"
      title="Privacy Policy"
      effectiveDate="February 26, 2026"
    >
      <p>
        Home Cleaners of Baltimore / HCOB Network (&ldquo;HCOB,&rdquo; &ldquo;we,&rdquo;
        &ldquo;us,&rdquo; or &ldquo;our&rdquo;) respects your privacy. This policy explains how
        we collect, use, and protect your information when you use{" "}
        <a
          className="text-[#0044FF] hover:underline"
          href="https://hcobnetwork.com"
        >
          hcobnetwork.com
        </a>
        ,{" "}
        <a
          className="text-[#0044FF] hover:underline"
          href="https://hcobcleaners.com"
        >
          hcobcleaners.com
        </a>
        , or interact with us by phone, form, or text message.
      </p>

      <LegalSection id="information-we-collect" title="Information We Collect">
        <ul className="list-disc space-y-2 pl-6">
          <li>
            Name, phone number, email, and service address when you submit a
            form, request a quote, or sign up as a client, contractor, or VA.
          </li>
          <li>
            Job details you provide (service type, property details, project
            notes).
          </li>
          <li>
            Communication history (calls, texts, emails) related to your
            service or application.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="how-we-use" title="How We Use Your Information">
        <p>We use your information to:</p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            Provide quotes, schedule jobs, and dispatch service providers.
          </li>
          <li>
            Communicate with you about bookings, job status, invoices, and
            follow-ups.
          </li>
          <li>
            Send text message updates if you&rsquo;ve opted in via a form on
            our website.
          </li>
          <li>Improve our services and internal operations.</li>
        </ul>
      </LegalSection>

      <LegalSection id="sms-privacy" title="Text Messaging (SMS) Privacy">
        <p>
          If you provide your mobile number through a form on our website and
          opt in to text messaging:
        </p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            <strong>
              No mobile information will be shared with third parties or
              affiliates for marketing or promotional purposes.
            </strong>{" "}
            Information sharing to subcontractors and third parties for the
            purposes of supporting you in this business relationship is
            permitted, excluding those sharing practices related to text
            messaging originator opt-in data &mdash; this information will not
            be shared with any third party.
          </li>
          <li>
            Message frequency varies based on your activity with us (e.g.,
            booking updates, quote follow-ups).
          </li>
          <li>Message and data rates may apply.</li>
          <li>
            You may opt out at any time by replying <strong>STOP</strong>, or
            get help by replying <strong>HELP</strong>.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="information-sharing" title="Information Sharing">
        <p>
          We do not sell your personal information. We may share necessary job
          details (e.g., name, address, job scope) with the vetted contractor
          or team assigned to your job, solely to complete the service.
        </p>
      </LegalSection>

      <LegalSection id="data-security" title="Data Security">
        <p>
          We take reasonable steps to protect your information from
          unauthorized access, but no method of transmission or storage is 100%
          secure.
        </p>
      </LegalSection>

      <LegalSection id="your-choices" title="Your Choices">
        <p>
          You may request to update or delete your information, or opt out of
          text/email communications at any time, by contacting us at:
        </p>
        <ul className="list-disc space-y-2 pl-6">
          <li>
            Phone: <strong>410-803-6204</strong> (HCOB Cleaners) /{" "}
            <strong>410-701-0570</strong> (HCOB Network)
          </li>
          <li>
            Website:{" "}
            <a
              className="text-[#0044FF] hover:underline"
              href="https://hcobcleaners.com"
            >
              hcobcleaners.com
            </a>{" "}
            /{" "}
            <a
              className="text-[#0044FF] hover:underline"
              href="https://hcobnetwork.com"
            >
              hcobnetwork.com
            </a>
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="changes" title="Changes to This Policy">
        <p>
          We may update this policy from time to time. The &ldquo;Effective
          Date&rdquo; above reflects the most recent revision.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
