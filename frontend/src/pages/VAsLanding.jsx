import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Lightning,
  ArrowRight,
  CurrencyDollar,
  Briefcase,
  CheckCircle,
  HandCoins,
  Megaphone,
  UsersThree,
  PaintBrush,
  PenNib,
  Code,
  Storefront,
  ShareNetwork,
  Keyboard,
  Cube,
  ClipboardText,
  ChartLineUp,
  Stack,
  Repeat,
  Lifebuoy,
  TrendUp,
} from "@phosphor-icons/react";
import { VPApplicationForm } from "@/components/VPApplicationForm";

const scrollToApply = (e) => {
  e.preventDefault();
  document.getElementById("apply")?.scrollIntoView({ behavior: "smooth" });
};

const ApplyButton = ({ testId, dark }) => (
  <a
    href="#apply"
    onClick={scrollToApply}
    data-testid={testId}
    className={`inline-flex h-14 items-center gap-2 px-7 text-base font-bold ${
      dark
        ? "bg-white text-[#030712] hover:bg-[#E5E7EB]"
        : "bg-[#0044FF] text-white hover:bg-[#0036cc]"
    }`}
  >
    Apply to the Network <ArrowRight size={16} weight="bold" />
  </a>
);

const STREAMS = [
  {
    icon: CurrencyDollar,
    kicker: "Commission Agent",
    title: "Earn Commissions",
    body: "Generate leads for our 13 property service lines and full virtual services catalog. Every job you bring in pays you a percentage of the profit — and recurring clients pay you on every visit, for as long as they stay. No caps. No limits.",
  },
  {
    icon: Briefcase,
    kicker: "Virtual Gig Work",
    title: "Get Paid for Your Skills",
    body: "Our clients need virtual work done — graphic design, website builds, SEO, data entry, social media management, admin support, and more. When work comes in that matches your skills, we route it to you. You do the work, you get paid.",
  },
  {
    icon: UsersThree,
    kicker: "Team Lead Path",
    title: "Build a Team",
    body: "Prove yourself as an agent and step up to Team Lead. Build a team of 3 to 5 agents and earn an override on everything your team produces — on top of your own production.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Apply",
    body: "Fill out the application below. Tell us your skills and what kind of work you want.",
  },
  {
    n: "02",
    title: "Onboard",
    body: "Get your welcome package, platform access, scripts, and training. Most professionals are active within days.",
  },
  {
    n: "03",
    title: "Choose Your Streams",
    body: "Start as an agent, take on virtual gigs, or run both from day one.",
  },
  {
    n: "04",
    title: "Earn",
    body: "Every completed job pays through our platform. Track your pipeline, commissions, and gig payments in one place.",
  },
];

const SERVICES = [
  { icon: PaintBrush, label: "Graphic Design" },
  { icon: PenNib, label: "Logo & Brand Design" },
  { icon: Code, label: "Website Development" },
  { icon: ChartLineUp, label: "SEO" },
  { icon: Storefront, label: "Google Business Listings" },
  { icon: ShareNetwork, label: "Social Media Management" },
  { icon: Keyboard, label: "Data Entry" },
  { icon: Cube, label: "Digital Product Creation" },
  { icon: ClipboardText, label: "Admin Support" },
  { icon: Megaphone, label: "Marketing Support" },
];

const WHY = [
  {
    icon: Stack,
    title: "Multiple streams",
    body: "Most gigs give you one way to earn. We give you three: commissions, gig work, and team overrides.",
  },
  {
    icon: Repeat,
    title: "Recurring income potential",
    body: "Our lifetime tail model means the clients you bring in can keep paying you for years, not weeks.",
  },
  {
    icon: Lifebuoy,
    title: "Real support",
    body: "Scripts, training, a dedicated operations manager, and a platform that tracks every lead and every dollar. You're never guessing.",
  },
  {
    icon: TrendUp,
    title: "A real growth path",
    body: "Agent to Senior to Elite to Team Lead. Your rates and your role grow with your results.",
  },
];

const REQUIREMENTS = [
  "Self-starters who can manage their own schedule and hit activity targets without hand-holding.",
  "Strong written English communication — you'll be messaging prospects and clients daily.",
  "Reliable internet connection and a computer or smartphone you can work from.",
  "Available a minimum of 4 hours per day, Monday through Friday. Work more whenever you want.",
  "For gig work: demonstrable skill in at least one virtual service area (portfolio or work samples requested during onboarding).",
  "Integrity. We enforce ethical outreach standards strictly — spammers and shortcut-takers don't last here.",
];

const FAQ = [
  {
    q: "Is this a salaried job?",
    a: "No. Agent work is 100% commission-based and gig work is paid per project. Your earnings depend on your activity and results. That also means there is no ceiling.",
  },
  {
    q: "Do I have to sell, or can I just do virtual gig work?",
    a: "Your choice. Some professionals only take gigs, some only run commissions, most do both. More streams, more earning potential.",
  },
  {
    q: "When and how do I get paid?",
    a: "Payouts run on a regular weekly or bi-weekly cycle through electronic payment. Every commission and gig payment is tracked in the platform where you can see it at all times.",
  },
  {
    q: "Do I need experience?",
    a: "For agent work, no — we provide scripts, training, and support. For gig work, yes — you'll need to show samples of your skill during onboarding.",
  },
  {
    q: "Where do I need to be located?",
    a: "Anywhere. This is fully remote. You'll need availability overlapping with US Eastern Time business hours.",
  },
  {
    q: "What happens after I apply?",
    a: "Our operations team reviews applications and reaches out to qualified candidates to schedule an onboarding conversation, usually within a few business days.",
  },
];

export default function VAsLanding() {
  useEffect(() => {
    const prevTitle = document.title;
    document.title = "Virtual Professional Opportunities — HCOB Network";
    const desc = document.querySelector('meta[name="description"]');
    const prevDesc = desc?.getAttribute("content") || "";
    if (desc) {
      desc.setAttribute(
        "content",
        "Virtual Professional Opportunities — HCOB Network. Commission agent roles and paid virtual gig work. Remote and flexible. Apply today."
      );
    }
    return () => {
      document.title = prevTitle;
      if (desc && prevDesc) desc.setAttribute("content", prevDesc);
    };
  }, []);

  return (
    <div className="min-h-screen bg-white text-[#030712]" data-testid="vp-landing">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-[#E5E7EB] bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 md:px-6">
          <div className="flex items-center gap-2" data-testid="vp-brand-lockup">
            <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={18} />
            </div>
            <div>
              <div className="font-display text-lg sm:text-xl font-black tracking-tight leading-none">
                HCOB Network
              </div>
              <div className="font-mono-label text-[9px] hidden sm:block">
                Virtual Professional Network
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              data-testid="header-login-link"
              to="/login"
              className="hidden sm:inline-flex items-center gap-1 text-sm font-semibold text-[#030712] hover:underline"
            >
              Sign in
            </Link>
            <a
              data-testid="header-apply-cta"
              href="#apply"
              onClick={scrollToApply}
              className="inline-flex items-center gap-2 bg-[#0044FF] px-4 py-2 text-sm font-bold text-white hover:bg-[#0036cc]"
            >
              <span className="hidden sm:inline">Apply to the Network</span>
              <span className="sm:hidden">Apply</span>
              <ArrowRight size={14} weight="bold" />
            </a>
          </div>
        </div>
      </header>

      {/* 1 — Hero */}
      <section className="border-b border-[#E5E7EB]">
        <div className="mx-auto max-w-7xl px-5 py-16 md:px-8 lg:px-10 lg:py-28">
          <div className="font-mono-label mb-6 flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-[#22C55E]" />
            Virtual Professionals · Now accepting applications
          </div>
          <h1
            data-testid="vp-hero-title"
            className="max-w-4xl font-display text-[44px] sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter"
          >
            One Network.
            <br />
            <span className="text-[#0044FF]">Multiple Ways to Earn.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base sm:text-lg text-[#4B5563] leading-relaxed">
            Join the HCOB Network as a Virtual Professional — earn commissions bringing in
            business, get paid for virtual work we bring to you, or do both. Remote. Flexible.
            Uncapped. Built for people who want more than one income stream.
          </p>
          <div className="mt-9">
            <ApplyButton testId="hero-apply-cta" />
          </div>
        </div>
      </section>

      {/* 2 — The Three Streams */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">Three income streams</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Sell. Fulfill. Or do both.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
            {STREAMS.map((s) => (
              <div
                key={s.title}
                data-testid={`stream-${s.kicker.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className="flex flex-col border border-[#E5E7EB] bg-white p-7 hover:border-[#030712] transition-colors"
              >
                <div className="grid h-12 w-12 place-items-center bg-[#0044FF] text-white">
                  <s.icon size={24} weight="duotone" />
                </div>
                <div className="mt-4 font-mono-label text-[10px] text-[#0044FF]">{s.kicker}</div>
                <div className="mt-1 font-display text-2xl font-black leading-tight">{s.title}</div>
                <div className="mt-3 text-sm text-[#4B5563] leading-relaxed">{s.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3 — How It Works */}
      <section className="border-b border-[#E5E7EB] bg-[#F9FAFB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">The process</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            How It Works
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div
                key={s.n}
                data-testid={`step-${s.n}`}
                className="border border-[#E5E7EB] bg-white p-6"
              >
                <div className="font-display text-4xl font-black text-[#0044FF]">{s.n}</div>
                <div className="mt-3 font-mono-label text-[10px] uppercase">{s.title}</div>
                <div className="mt-2 text-sm text-[#4B5563] leading-relaxed">{s.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4 — Earning Opportunities */}
      <section className="border-b border-[#E5E7EB] bg-[#030712] px-5 py-16 md:px-8 lg:px-10 lg:py-24 text-white">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3 text-white/70">Earning opportunities</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Real Earning Opportunities
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="border border-white/15 bg-white/5 p-7" data-testid="earning-commissions">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center bg-[#0044FF] text-white">
                  <HandCoins size={22} weight="duotone" />
                </div>
                <div className="font-display text-xl font-black">Commission earnings</div>
              </div>
              <p className="mt-4 text-sm text-white/80 leading-relaxed">
                <strong className="text-white">Commission on every job you originate</strong> — paid
                as a percentage of job profit, with higher rates as you level up from Agent to
                Senior to Elite.
              </p>
              <p className="mt-3 text-sm text-white/80 leading-relaxed">
                <strong className="text-white">Recurring clients pay you again and again.</strong>{" "}
                Land a biweekly cleaning client or an Airbnb host and you earn on every single
                visit — including a lifetime rate that never expires while the account stays
                active.
              </p>
              <p className="mt-3 text-sm text-white/80 leading-relaxed">
                <strong className="text-white">Commercial and retainer accounts pay monthly.</strong>{" "}
                Office contracts, SEO packages, and marketing retainers pay you a share of revenue
                every month the client stays.
              </p>
            </div>
            <div className="border border-white/15 bg-white/5 p-7" data-testid="earning-gigs">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center bg-[#0044FF] text-white">
                  <Briefcase size={22} weight="duotone" />
                </div>
                <div className="font-display text-xl font-black">Gig work earnings</div>
              </div>
              <p className="mt-4 text-sm text-white/80 leading-relaxed">
                <strong className="text-white">Virtual gig work pays per project.</strong> Design
                work, website builds, data entry, and admin tasks are paid per completed job at
                rates agreed before you start.
              </p>
              <div className="mt-5 border-l-2 border-[#0044FF] bg-white/5 p-4 text-xs text-white/70">
                Earnings are commission and project-based and depend entirely on your activity and
                results. No income level is guaranteed.
              </div>
            </div>
          </div>
          <div className="mt-10">
            <ApplyButton testId="earnings-apply-cta" />
          </div>
        </div>
      </section>

      {/* 5 — The Virtual Services Catalog */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">Services catalog</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Virtual Work We Route to Our Network
          </h2>
          <div className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {SERVICES.map((s) => (
              <div
                key={s.label}
                data-testid={`service-${s.label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className="flex flex-col items-start gap-3 border border-[#E5E7EB] bg-white p-5 hover:border-[#0044FF] transition-colors"
              >
                <div className="grid h-10 w-10 place-items-center bg-[#F3F4F6] text-[#0044FF]">
                  <s.icon size={20} weight="duotone" />
                </div>
                <div className="text-sm font-bold leading-tight">{s.label}</div>
              </div>
            ))}
          </div>
          <p className="mt-8 text-lg font-semibold">
            Have a skill on this list?{" "}
            <span className="text-[#0044FF]">You&apos;re exactly who we&apos;re looking for.</span>
          </p>
        </div>
      </section>

      {/* 6 — Why the HCOB Network */}
      <section className="border-b border-[#E5E7EB] bg-[#F9FAFB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">Why us</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Why Professionals Join the HCOB Network
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
            {WHY.map((r) => (
              <div
                key={r.title}
                data-testid={`why-${r.title.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className="flex gap-4 border border-[#E5E7EB] bg-white p-6"
              >
                <div className="grid h-12 w-12 shrink-0 place-items-center bg-[#030712] text-white">
                  <r.icon size={22} weight="duotone" />
                </div>
                <div>
                  <div className="font-display text-lg font-black uppercase tracking-wide">
                    {r.title}
                  </div>
                  <div className="mt-1 text-sm text-[#4B5563] leading-relaxed">{r.body}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-10">
            <ApplyButton testId="why-apply-cta" />
          </div>
        </div>
      </section>

      {/* 7 — Who We're Looking For */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <div className="font-mono-label mb-3">Requirements</div>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
              Who We&apos;re Looking For
            </h2>
            <p className="mt-4 text-[#4B5563]">
              We keep the network strong by being selective. If this sounds like you, apply below.
            </p>
          </div>
          <ul className="lg:col-span-7 space-y-3">
            {REQUIREMENTS.map((r, i) => (
              <li
                key={i}
                data-testid={`requirement-${i}`}
                className="flex items-start gap-3 border border-[#E5E7EB] bg-white p-4"
              >
                <CheckCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-[#0044FF]" />
                <span className="text-sm text-[#4B5563] leading-relaxed">{r}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* 8 — Application Form */}
      <section id="apply" className="border-b border-[#E5E7EB] bg-[#F9FAFB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-3xl">
          <div className="font-mono-label mb-3">Apply now</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Apply to the Network
          </h2>
          <p className="mt-4 text-[#4B5563]">
            Takes about 3 minutes. Tell us your skills and what kind of work you want — our
            operations team routes you to the right streams from day one.
          </p>
          <div className="mt-10 border border-[#E5E7EB] bg-white p-6 md:p-8">
            <VPApplicationForm />
          </div>
        </div>
      </section>

      {/* 9 — FAQ */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-4xl">
          <div className="font-mono-label mb-3">FAQ</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Frequently Asked Questions
          </h2>
          <div className="mt-10 space-y-3">
            {FAQ.map((item, i) => (
              <details
                key={item.q}
                data-testid={`faq-${i}`}
                className="group border border-[#E5E7EB] bg-white open:border-[#030712]"
              >
                <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4 text-left">
                  <span className="font-semibold">{item.q}</span>
                  <span className="grid h-7 w-7 shrink-0 place-items-center bg-[#F3F4F6] font-mono text-xs transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <div className="border-t border-[#E5E7EB] px-5 py-4 text-sm text-[#4B5563] leading-relaxed">
                  {item.a}
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-5 py-20 md:px-8 lg:px-10 lg:py-28 bg-[#030712] text-white">
        <div className="mx-auto max-w-4xl text-center">
          <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter leading-[0.95]">
            One network.
            <br />
            <span className="text-[#0044FF]">Multiple ways to earn.</span>
          </h2>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <ApplyButton testId="footer-apply-cta" />
            <Link
              data-testid="footer-signin-cta"
              to="/login"
              className="inline-flex h-14 items-center gap-2 border border-white/30 bg-transparent px-7 text-base font-semibold text-white hover:bg-white/10"
            >
              Already in the network? Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E7EB] bg-white px-5 py-10 md:px-8 lg:px-10">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={14} />
            </div>
            <div className="font-display text-sm font-black">
              HCOB Network · Virtual Professionals
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-[#4B5563]">
            <a href="/privacy.html" className="hover:text-[#030712]">
              Privacy
            </a>
            <span className="text-[#9CA3AF]">·</span>
            <a href="/terms.html" className="hover:text-[#030712]">
              Terms
            </a>
            <span className="text-[#9CA3AF]">·</span>
            <span>© HCOB Network · Baltimore, MD</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
