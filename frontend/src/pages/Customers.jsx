import React, { useEffect } from "react";
import { Button } from "@/components/ui/button";
import QuoteRequestForm from "@/components/QuoteRequestForm";
import {
  Phone,
  ArrowRight,
  PaperPlaneTilt,
  Lightning,
  ShieldCheck,
  CheckCircle,
  IdentificationCard,
  Sparkle,
  Broom,
  Buildings,
  ArrowsClockwise,
  House,
  Trash,
  Stack,
  Drop,
  Couch,
  Tree,
  Wrench,
  PaintBrushHousehold,
  HardHat,
  Star,
  CalendarCheck,
  ChatTeardropDots,
  ListChecks,
  PhoneCall,
} from "@phosphor-icons/react";

const PHONE_DISPLAY = "(410) 870-9347";
const PHONE_HREF = "tel:+14108709347";

const SERVICES = [
  { icon: Broom, title: "Residential Cleaning", sub: "Recurring or one-time deep cleans" },
  { icon: Buildings, title: "Commercial & Office Cleaning", sub: "Weekly, nightly, or after-hours" },
  { icon: ArrowsClockwise, title: "Move-Out Cleaning", sub: "Deposit-saving turnover cleans" },
  { icon: House, title: "Apartment Turnovers", sub: "Landlord-grade unit prep" },
  { icon: Trash, title: "Junk Removal", sub: "Full hauls, single items, debris" },
  { icon: Stack, title: "Estate Cleanouts", sub: "Sensitive, end-to-end coordination" },
  { icon: Drop, title: "Pressure Washing", sub: "Driveways, decks, siding, walkways" },
  { icon: Couch, title: "Carpet Cleaning", sub: "Stain treatment & deep extraction" },
  { icon: Tree, title: "Landscaping & Yard Cleanup", sub: "Seasonal cleanup & maintenance" },
  { icon: Wrench, title: "Handyman Services", sub: "Repairs, installs, small fixes" },
  { icon: PaintBrushHousehold, title: "Painting", sub: "Interior & exterior, touch-ups" },
  { icon: HardHat, title: "Property Maintenance", sub: "Ongoing care contracts" },
  { icon: Sparkle, title: "Specialty Property Services", sub: "Anything else — just ask" },
];

const TRUST = [
  {
    icon: ShieldCheck,
    title: "Insurance verification",
    body: "We confirm coverage before pros step on your property.",
  },
  {
    icon: IdentificationCard,
    title: "Background screening",
    body: "Conducted when appropriate for the work being performed.",
  },
  {
    icon: CheckCircle,
    title: "Licensing verification",
    body: "Where licensing applies, we verify and document it.",
  },
  {
    icon: Star,
    title: "Skill validation",
    body: "Selected on experience, reliability, communication, and quality.",
  },
];

const STEPS = [
  {
    n: "01",
    icon: PhoneCall,
    title: "One call",
    body: "Tell us what you need. We scope the work and propose a plan.",
  },
  {
    n: "02",
    icon: ListChecks,
    title: "We coordinate",
    body: "We dispatch the right vetted pros and manage the schedule.",
  },
  {
    n: "03",
    icon: CalendarCheck,
    title: "Work gets done",
    body: "We oversee the job, handle quality, and keep you updated.",
  },
  {
    n: "04",
    icon: ChatTeardropDots,
    title: "Single point of contact",
    body: "One number for every service — no contractor juggling.",
  },
];

export default function CustomersPage() {
  // Customer-focused page title + meta description override.
  useEffect(() => {
    const prevTitle = document.title;
    const desc = document.querySelector('meta[name="description"]');
    const prevDesc = desc?.getAttribute("content");
    document.title =
      "HCOB Network — Project management for cleaning, labor & property services in Baltimore, MD";
    if (desc) {
      desc.setAttribute(
        "content",
        "One call. One point of contact. Complete project management. HCOB Network coordinates trusted service professionals across Baltimore, Maryland — call (410) 870-9347."
      );
    }
    return () => {
      document.title = prevTitle;
      if (desc && prevDesc) desc.setAttribute("content", prevDesc);
    };
  }, []);

  return (
    <div className="min-h-screen bg-white text-[#030712]" data-testid="customers-page">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-[#E5E7EB] bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 md:px-6">
          <div
            data-testid="customers-brand-lockup"
            className="flex items-center gap-2"
          >
            <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={18} />
            </div>
            <div>
              <div className="font-display text-lg sm:text-xl font-black tracking-tight leading-none">
                HCOB Network
              </div>
              <div className="font-mono-label text-[9px] hidden sm:block">
                Project management · Baltimore, MD
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              data-testid="header-phone-cta"
              href={PHONE_HREF}
              className="hidden sm:inline-flex items-center gap-2 border border-[#030712] bg-[#030712] px-4 py-2 text-sm font-bold text-white hover:bg-[#1f2937]"
            >
              <Phone size={14} weight="fill" /> {PHONE_DISPLAY}
            </a>
            <a
              data-testid="header-phone-cta-mobile"
              href={PHONE_HREF}
              aria-label={`Call ${PHONE_DISPLAY}`}
              className="grid h-10 w-10 place-items-center sm:hidden border border-[#030712] bg-[#030712] text-white"
            >
              <Phone size={16} weight="fill" />
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-[#E5E7EB]">
        <div className="mx-auto grid max-w-7xl grid-cols-1 lg:grid-cols-12">
          <div className="lg:col-span-7 lg:border-r border-[#E5E7EB] px-5 py-14 md:px-8 lg:px-10 lg:py-24">
            <div className="font-mono-label mb-6 flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-[#22C55E]" />
              Project management · Baltimore, MD
            </div>
            <h1
              data-testid="customers-hero-title"
              className="font-display text-[44px] sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter"
            >
              One call.
              <br />
              One point of contact.
              <br />
              <span className="text-[#0044FF]">Complete project management.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base sm:text-lg text-[#4B5563] leading-relaxed">
              The HCOB Network connects you with{" "}
              <strong className="text-[#030712]">trusted service professionals</strong>{" "}
              and provides complete oversight from start to finish — for residential
              service calls, commercial contracts, and large-scale property
              improvements alike.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-3">
              <a
                data-testid="hero-quote-cta"
                href="#quote"
                className="inline-flex h-14 items-center gap-2 bg-[#0044FF] px-6 text-base font-bold text-white hover:bg-[#0036cc]"
              >
                <PaperPlaneTilt size={18} weight="fill" /> Request a quote
              </a>
              <a
                data-testid="hero-call-cta"
                href={PHONE_HREF}
                className="inline-flex h-14 items-center gap-2 border border-[#030712] bg-white px-6 text-base font-semibold text-[#030712] hover:bg-[#F3F4F6]"
              >
                <Phone size={18} weight="fill" /> Call {PHONE_DISPLAY}
              </a>
            </div>

            <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Stat label="One point of contact" value="Single call" />
              <Stat label="Vetted professionals" value="100%" />
              <Stat label="Project sizes" value="Any" accent />
            </div>
          </div>

          {/* Hero side card */}
          <aside className="lg:col-span-5 px-5 py-10 md:px-8 lg:px-10 lg:py-24 bg-[#F9FAFB]">
            <div className="border border-[#030712] bg-white p-6 md:p-7 gb-tactile">
              <div className="font-mono-label text-[10px] text-[#4B5563]">
                What we handle
              </div>
              <div className="mt-2 font-display text-2xl font-black leading-tight">
                Project coordination from intake to wrap-up.
              </div>
              <ul className="mt-5 space-y-3 text-sm">
                {[
                  "Contractor sourcing & management",
                  "Scheduling & timeline oversight",
                  "Quality assurance at every visit",
                  "Customer communication, end-to-end",
                  "Insurance, licensing & screening checks",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-2">
                    <CheckCircle
                      size={16}
                      weight="fill"
                      className="mt-0.5 shrink-0 text-[#0044FF]"
                    />
                    <span className="text-[#030712]">{t}</span>
                  </li>
                ))}
              </ul>
              <a
                data-testid="aside-phone-cta"
                href={PHONE_HREF}
                className="mt-6 inline-flex w-full items-center justify-center gap-2 bg-[#0044FF] px-4 py-3 text-sm font-bold text-white hover:bg-[#0036cc]"
              >
                <Phone size={14} weight="fill" /> Talk to us · {PHONE_DISPLAY}
              </a>
              <div className="mt-3 text-center font-mono-label text-[10px] text-[#4B5563]">
                Mon–Sat · Baltimore, Maryland
              </div>
            </div>
          </aside>
        </div>
      </section>

      {/* Quote-request form — primary lead capture */}
      <section
        id="quote"
        data-testid="customers-quote"
        className="border-b border-[#E5E7EB] bg-[#F9FAFB] py-12 md:py-20"
      >
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 px-5 md:px-8 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <div className="font-mono-label mb-3">Get a quote</div>
            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black leading-[1.02] tracking-tight">
              Send us the basics. We&apos;ll text you back.
            </h2>
            <p className="mt-4 text-[#4B5563]">
              Tell us what you need and we&apos;ll line up the right pro. No accounts,
              no logins, no spam — just a quick reply from a real person.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-[#030712]">
              <li className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-6 bg-[#0044FF]" />
                Reply usually within the hour during business hours
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-6 bg-[#0044FF]" />
                Free estimates · no obligation
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-6 bg-[#0044FF]" />
                One point of contact for every service
              </li>
            </ul>
          </div>
          <div className="lg:col-span-3">
            <QuoteRequestForm />
          </div>
        </div>
      </section>

      {/* Mission strip */}
      <section className="border-b border-[#E5E7EB] bg-[#030712] py-10 text-white md:py-14">
        <div className="mx-auto max-w-5xl px-6">
          <div className="font-mono-label mb-3 text-[#0044FF]">Our mission</div>
          <p className="font-display text-2xl md:text-3xl font-black leading-tight tracking-tight">
            &ldquo;Create a better experience for customers while creating better
            opportunities for local professionals.&rdquo;
          </p>
          <p className="mt-5 max-w-3xl text-sm md:text-base text-[#9CA3AF] leading-relaxed">
            We believe customers deserve affordable, dependable services from
            people they can trust — and skilled professionals deserve access to
            meaningful opportunities that help them grow.
          </p>
        </div>
      </section>

      {/* Services grid */}
      <section
        id="services"
        data-testid="customers-services"
        className="border-b border-[#E5E7EB] py-14 md:py-20"
      >
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <div className="mb-10 max-w-3xl">
            <div className="font-mono-label mb-3">Services we coordinate</div>
            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black leading-[1.02] tracking-tight">
              Qualified pros across a wide range of industries.
            </h2>
            <p className="mt-4 text-[#4B5563]">
              We coordinate one service or many — and we manage the process so
              you don&apos;t have to source, screen, schedule, or chase contractors.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-px bg-[#E5E7EB] sm:grid-cols-2 lg:grid-cols-3 border border-[#E5E7EB]">
            {SERVICES.map((s, i) => {
              const I = s.icon;
              return (
                <div
                  key={s.title}
                  data-testid={`service-card-${i}`}
                  className="group flex items-start gap-4 bg-white p-5 transition-colors hover:bg-[#F0F4FF]"
                >
                  <div className="grid h-11 w-11 shrink-0 place-items-center border border-[#030712] bg-[#030712] text-white transition-colors group-hover:bg-[#0044FF] group-hover:border-[#0044FF]">
                    <I size={20} weight="duotone" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-base font-black">
                      {s.title}
                    </div>
                    <div className="mt-0.5 text-xs text-[#4B5563]">{s.sub}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border border-dashed border-[#030712]/30 bg-[#F9FAFB] px-5 py-4">
            <div className="text-sm text-[#4B5563]">
              Don&apos;t see your service?{" "}
              <strong className="text-[#030712]">We probably handle it.</strong>
            </div>
            <a
              data-testid="services-call-cta"
              href={PHONE_HREF}
              className="inline-flex items-center gap-2 border border-[#030712] bg-white px-4 py-2 text-sm font-bold hover:bg-[#030712] hover:text-white"
            >
              <Phone size={14} weight="fill" /> Call to scope it
            </a>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section
        data-testid="customers-process"
        className="border-b border-[#E5E7EB] bg-[#F9FAFB] py-14 md:py-20"
      >
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <div className="mb-10 max-w-3xl">
            <div className="font-mono-label mb-3">How it works</div>
            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black leading-[1.02] tracking-tight">
              Four steps. Zero contractor juggling.
            </h2>
          </div>
          <ol className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => {
              const I = s.icon;
              return (
                <li
                  key={s.n}
                  className="border border-[#030712] bg-white p-5 gb-tactile"
                >
                  <div className="font-mono-label text-[10px] text-[#0044FF]">
                    Step {s.n}
                  </div>
                  <I size={28} weight="duotone" className="mt-3 text-[#030712]" />
                  <div className="mt-4 font-display text-lg font-black tracking-tight">
                    {s.title}
                  </div>
                  <p className="mt-1 text-sm text-[#4B5563]">{s.body}</p>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* Trust / vetting */}
      <section
        data-testid="customers-trust"
        className="border-b border-[#E5E7EB] py-14 md:py-20"
      >
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <div className="mb-10 max-w-3xl">
            <div className="font-mono-label mb-3">How we vet our network</div>
            <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-black leading-[1.02] tracking-tight">
              Trusted pros, properly checked.
            </h2>
            <p className="mt-4 text-[#4B5563]">
              Every professional in our network is selected based on experience,
              professionalism, reliability, communication, and service quality.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            {TRUST.map((t) => {
              const I = t.icon;
              return (
                <div
                  key={t.title}
                  className="border border-[#030712]/10 bg-white p-5"
                >
                  <I size={28} weight="duotone" className="text-[#0044FF]" />
                  <div className="mt-3 font-display text-base font-black">
                    {t.title}
                  </div>
                  <p className="mt-1 text-xs text-[#4B5563]">{t.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Big CTA */}
      <section
        data-testid="customers-cta"
        className="bg-[#030712] py-16 text-white md:py-24"
      >
        <div className="mx-auto max-w-5xl px-5 text-center md:px-8">
          <div className="font-mono-label mb-4 text-[#0044FF]">
            No project too big or too small
          </div>
          <h2 className="font-display text-3xl sm:text-5xl md:text-6xl font-black leading-[0.98] tracking-tighter">
            Recurring office cleaning. Full estate cleanouts. Property
            transformations. — We manage it.
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-base text-[#9CA3AF]">
            One call. One point of contact. Complete project management.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              data-testid="footer-quote-cta"
              href="#quote"
              className="inline-flex h-14 items-center gap-2 bg-[#0044FF] px-6 text-base font-bold text-white hover:bg-[#0036cc]"
            >
              <PaperPlaneTilt size={18} weight="fill" /> Request a quote
            </a>
            <a
              data-testid="footer-call-cta"
              href={PHONE_HREF}
              className="inline-flex h-14 items-center gap-2 border border-white/30 bg-transparent px-6 text-base font-semibold text-white hover:bg-white/10"
            >
              <Phone size={18} weight="fill" /> Call {PHONE_DISPLAY}
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E7EB] bg-white">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-5 py-10 md:grid-cols-2 md:px-8">
          <div>
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
                <Lightning weight="fill" size={18} />
              </div>
              <div className="font-display text-lg font-black tracking-tight">
                HCOB Network
              </div>
            </div>
            <p className="mt-3 max-w-xs text-xs text-[#4B5563]">
              A project management company connecting customers with trusted
              service professionals — Baltimore, MD.
            </p>
          </div>
          <div>
            <div className="font-mono-label mb-3">Contact</div>
            <a
              href={PHONE_HREF}
              className="block font-display text-2xl font-black hover:text-[#0044FF]"
            >
              {PHONE_DISPLAY}
            </a>
            <div className="mt-2 text-xs text-[#4B5563]">
              Mon–Sat · Serving Baltimore, Maryland
            </div>
            <a
              href="#quote"
              className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#0044FF] hover:underline"
            >
              Request a quote <ArrowRight size={14} />
            </a>
          </div>
        </div>
        <div className="border-t border-[#E5E7EB] py-5 text-center text-[11px] text-[#4B5563]">
          <div className="mb-2 flex flex-wrap items-center justify-center gap-x-5 gap-y-1">
            <a
              data-testid="footer-contractors-link"
              href="/work"
              className="font-semibold hover:text-[#0044FF]"
            >
              For contractors — join the crew →
            </a>
            <a href="/vas" className="hover:text-[#0044FF]">
              Refer leads · earn
            </a>
          </div>
          © {new Date().getFullYear()} HCOB Network · Baltimore, MD
        </div>
      </footer>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div
      className={`border ${
        accent ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#030712]/10 bg-white"
      } px-4 py-3`}
    >
      <div className="font-mono-label text-[10px] text-[#4B5563]">{label}</div>
      <div className="mt-1 font-display text-lg font-black tracking-tight">
        {value}
      </div>
    </div>
  );
}
