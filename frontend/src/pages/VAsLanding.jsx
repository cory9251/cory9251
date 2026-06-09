import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Lightning,
  ArrowRight,
  CurrencyDollar,
  Briefcase,
  Phone,
  CheckCircle,
  Sparkle,
  Trophy,
  ChatTeardropDots,
  HandCoins,
  Receipt,
  Confetti,
  ShieldCheck,
  Clock,
  Megaphone,
  ArrowUpRight,
  Star,
  Users,
} from "@phosphor-icons/react";

const PHONE_DISPLAY = "(410) 870-9347";
const PHONE_HREF = "tel:+14108709347";

const STEPS = [
  {
    n: "01",
    icon: Megaphone,
    title: "Spot a lead",
    body:
      "Anywhere you network — Facebook groups, Marketplace, Craigslist, neighbors, your DMs. When someone needs a clean, you have a job to refer.",
  },
  {
    n: "02",
    icon: ChatTeardropDots,
    title: "Submit it in your dashboard",
    body:
      "One form locks the lead to you with a timestamp. Ownership is yours forever — nobody else can claim it.",
  },
  {
    n: "03",
    icon: Briefcase,
    title: "Ops takes it from here",
    body:
      "Our team contacts the client, schedules the job, and handles every detail. You watch the pipeline move: Contacted → Quoted → Booked → Completed → Paid.",
  },
  {
    n: "04",
    icon: HandCoins,
    title: "Get paid",
    body:
      "Once the client pays HCOB, your commission auto-calculates and goes into our weekly review queue. Approved commissions are paid by Venmo, Zelle, Check, or ACH.",
  },
];

const RATES = [
  {
    icon: Sparkle,
    label: "Routine cleaning",
    amount: "$10",
    note: "Per one-time routine clean",
  },
  {
    icon: Briefcase,
    label: "Deep · Move-Out · Specialty",
    amount: "$25",
    note: "Flat per booked job",
    highlight: true,
  },
  {
    icon: Receipt,
    label: "Recurring routine",
    amount: "$15 → $25 → $10",
    note: "Visit 1 · Visit 2 · Visits 3-6 (each)",
  },
  {
    icon: Trophy,
    label: "Commercial accounts",
    amount: "5%",
    note: "Of monthly revenue, every month it's active",
    highlight: true,
  },
];

const REASONS = [
  {
    icon: ShieldCheck,
    title: "Timestamp ownership lock",
    body:
      "The moment you submit, the lead is yours. No \"someone else got there first\" — the database protects your work.",
  },
  {
    icon: Clock,
    title: "Weekly payouts",
    body:
      "Every Friday the Owner signs off on the week's approved commissions. You get paid early the following week by your preferred method.",
  },
  {
    icon: CheckCircle,
    title: "Transparent pipeline",
    body:
      "Watch every stage of every lead in real time. No black box — you always know where your money stands.",
  },
  {
    icon: Confetti,
    title: "Real leads, real payouts",
    body:
      "Commercial accounts earn you 5% every single month they stay with HCOB. Stack recurring clients, build a residual income.",
  },
];

const FAQ = [
  {
    q: "How much can I actually make?",
    a: "Depends on you. One booked deep clean = $25. Land a recurring weekly client and earn $15+$25+$10×4 across their first 6 visits. Bring in a small office (say, $1,200/mo cleaning contract) and that's $60/month for as long as the account stays active.",
  },
  {
    q: "When do I get paid?",
    a: "Commissions are reviewed every week by your Program Manager. Once the Owner signs off (typically Fridays), approved payouts are released by Venmo, Zelle, Check, or ACH — your choice — by the start of the next week.",
  },
  {
    q: "What if two VAs submit the same lead?",
    a: "Whoever submits first wins — the timestamp ownership lock is enforced at the database level. Duplicate submissions are blocked automatically and the original VA keeps the lead.",
  },
  {
    q: "What happens if the client doesn't pay?",
    a: "No payment from the client = no commission. We're a 100% performance-based program. But once HCOB collects, you get paid — period.",
  },
  {
    q: "Can I submit my own house as a lead?",
    a: "No. Self-referrals are blocked automatically (we match against your registered home address). VAs are here to bring in new clients, not double-dip.",
  },
  {
    q: "Do I need experience?",
    a: "Just two things: a phone, and the willingness to ask people if they need cleaning. We provide the dashboard, the pipeline tooling, and Ops handles everything else.",
  },
];

function Stat({ label, value, accent }) {
  return (
    <div
      className={`flex flex-col gap-1 border ${
        accent ? "border-[#0044FF]" : "border-[#E5E7EB]"
      } p-4`}
    >
      <span className="font-mono-label">{label}</span>
      <span
        className={`font-display text-2xl font-black ${
          accent ? "text-[#0044FF]" : "text-[#030712]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export default function VAsLanding() {
  useEffect(() => {
    const prevTitle = document.title;
    document.title = "Become a VA — Earn with HCOB Network";
    const desc = document.querySelector('meta[name="description"]');
    const prevDesc = desc?.getAttribute("content") || "";
    if (desc) {
      desc.setAttribute(
        "content",
        "Join HCOB's VA crew. Submit cleaning leads from anywhere, watch your pipeline, and earn weekly payouts. Real leads. Real money. Baltimore, MD."
      );
    }
    return () => {
      document.title = prevTitle;
      if (desc && prevDesc) desc.setAttribute("content", prevDesc);
    };
  }, []);

  return (
    <div className="min-h-screen bg-white text-[#030712]" data-testid="vas-landing">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-[#E5E7EB] bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 md:px-6">
          <div className="flex items-center gap-2" data-testid="vas-brand-lockup">
            <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={18} />
            </div>
            <div>
              <div className="font-display text-lg sm:text-xl font-black tracking-tight leading-none">
                HCOB Network
              </div>
              <div className="font-mono-label text-[9px] hidden sm:block">
                VA Commission Program · Baltimore, MD
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
            <Link
              data-testid="header-apply-cta"
              to="/register?as=va"
              className="inline-flex items-center gap-2 bg-[#0044FF] px-4 py-2 text-sm font-bold text-white hover:bg-[#0036cc]"
            >
              <span className="hidden sm:inline">Apply now</span>
              <span className="sm:hidden">Apply</span>
              <ArrowRight size={14} weight="bold" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-[#E5E7EB]">
        <div className="mx-auto grid max-w-7xl grid-cols-1 lg:grid-cols-12">
          <div className="lg:col-span-7 lg:border-r border-[#E5E7EB] px-5 py-14 md:px-8 lg:px-10 lg:py-24">
            <div className="font-mono-label mb-6 flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-[#22C55E]" />
              VA Commission Program · Now accepting
            </div>
            <h1
              data-testid="vas-hero-title"
              className="font-display text-[44px] sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter"
            >
              Join HCOB&apos;s
              <br />
              <span className="text-[#0044FF]">VA crew.</span>
              <br />
              Real leads, real payouts,
              <br />
              every week.
            </h1>
            <p className="mt-6 max-w-xl text-base sm:text-lg text-[#4B5563] leading-relaxed">
              You bring the lead. We handle the rest — scheduling, cleaning, billing, customer
              support. When HCOB gets paid, <strong className="text-[#030712]">you get paid</strong>.
              No experience required. No upfront cost. No upselling.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                data-testid="hero-apply-cta"
                to="/register?as=va"
                className="inline-flex h-14 items-center gap-2 bg-[#0044FF] px-6 text-base font-bold text-white hover:bg-[#0036cc]"
              >
                <CurrencyDollar size={20} weight="fill" /> Apply to become a VA
              </Link>
              <a
                data-testid="hero-call-cta"
                href={PHONE_HREF}
                className="inline-flex h-14 items-center gap-2 border border-[#030712] bg-white px-6 text-base font-semibold text-[#030712] hover:bg-[#F3F4F6]"
              >
                <Phone size={18} weight="fill" /> {PHONE_DISPLAY}
              </a>
            </div>

            <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Stat label="Per deep clean" value="$25" />
              <Stat label="Commercial account" value="5% / mo" accent />
              <Stat label="Payouts" value="Weekly" />
            </div>
          </div>

          {/* Hero side card */}
          <aside className="lg:col-span-5 px-5 py-10 md:px-8 lg:px-10 lg:py-24 bg-[#F9FAFB]">
            <div className="border border-[#030712] bg-white p-6 md:p-7">
              <div className="font-mono-label text-[10px] text-[#4B5563]">
                Who this is for
              </div>
              <div className="mt-2 font-display text-2xl font-black leading-tight">
                You network. We do the work.
              </div>
              <ul className="mt-5 space-y-3 text-sm leading-relaxed text-[#4B5563]">
                {[
                  "Active on Facebook groups, Marketplace, Craigslist, or just well-connected in Baltimore",
                  "Already get asked \"do you know a cleaner?\" — and want to monetize that",
                  "Looking for flexible side income with zero physical labor",
                  "Comfortable on your phone, can fill out a form",
                ].map((b) => (
                  <li key={b} className="flex items-start gap-2">
                    <CheckCircle
                      size={18}
                      weight="fill"
                      className="mt-0.5 shrink-0 text-[#0044FF]"
                    />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-7 border-t border-[#E5E7EB] pt-5">
                <div className="font-mono-label text-[10px]">
                  Approval flow
                </div>
                <div className="mt-2 text-sm text-[#4B5563]">
                  Apply → Program Manager reviews →{" "}
                  <strong className="text-[#030712]">activated within 1 business day</strong>.
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      {/* How it works */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">How it works</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Four steps. Zero physical labor.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div
                key={s.n}
                data-testid={`step-${s.n}`}
                className="flex flex-col border border-[#E5E7EB] bg-white p-6 hover:border-[#030712] transition-colors"
              >
                <div className="font-mono-label text-[10px] text-[#9CA3AF]">{s.n}</div>
                <div className="mt-3 grid h-12 w-12 place-items-center bg-[#0044FF] text-white">
                  <s.icon size={24} weight="duotone" />
                </div>
                <div className="mt-4 font-display text-xl font-black leading-tight">
                  {s.title}
                </div>
                <div className="mt-2 text-sm text-[#4B5563] leading-relaxed">{s.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Rate table */}
      <section
        id="rates"
        className="border-b border-[#E5E7EB] bg-[#030712] px-5 py-16 md:px-8 lg:px-10 lg:py-24 text-white"
      >
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3 text-white/70">Commission rates</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Transparent payouts.
            <br />
            <span className="text-[#0044FF]">No fine print.</span>
          </h2>
          <p className="mt-4 max-w-2xl text-white/70">
            Auto-calculated the moment a job is marked Paid. Reviewed by your Program Manager,
            signed off by the Owner, paid out weekly.
          </p>

          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
            {RATES.map((r) => (
              <div
                key={r.label}
                data-testid={`rate-${r.label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className={`flex items-center justify-between gap-4 border p-5 ${
                  r.highlight
                    ? "border-[#0044FF] bg-[#0044FF]/10"
                    : "border-white/15 bg-white/5"
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className="grid h-12 w-12 place-items-center bg-white/10">
                    <r.icon size={22} weight="duotone" />
                  </div>
                  <div>
                    <div className="font-semibold">{r.label}</div>
                    <div className="text-xs text-white/60">{r.note}</div>
                  </div>
                </div>
                <div className="font-display text-2xl sm:text-3xl font-black tracking-tight">
                  {r.amount}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 border-l-2 border-[#0044FF] bg-white/5 p-4 text-sm text-white/80">
            <strong className="text-white">Stack recurring clients.</strong> Bring in a weekly
            recurring cleaning client and earn across multiple visits. Land a commercial account
            and earn 5% every month it stays with HCOB.
          </div>
        </div>
      </section>

      {/* Payout schedule */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 lg:grid-cols-2 lg:gap-16">
          <div>
            <div className="font-mono-label mb-3">Payout schedule</div>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
              You get paid weekly.
              <br />
              <span className="text-[#0044FF]">Predictable. Documented. On time.</span>
            </h2>
            <p className="mt-5 text-base text-[#4B5563] leading-relaxed">
              Every commission flows through the same audit trail — auto-calculated, Program
              Manager-reviewed, Owner-signed. Once you&apos;re in the payable queue, payout lands
              in your account by the following week.
            </p>
            <Link
              to="/register?as=va"
              data-testid="payout-cta"
              className="mt-8 inline-flex items-center gap-2 bg-[#030712] px-5 py-3 text-sm font-bold text-white hover:bg-[#1f2937]"
            >
              Start submitting leads <ArrowUpRight size={14} weight="bold" />
            </Link>
          </div>
          <ol className="space-y-4">
            {[
              {
                day: "Day 0",
                title: "You submit a lead",
                body: "Locked to you with a timestamp the second you hit submit.",
              },
              {
                day: "Day 1-N",
                title: "Ops works the lead",
                body: "Contact, quote, schedule, clean, invoice. You see every stage in real time.",
              },
              {
                day: "Client pays HCOB",
                title: "Commission auto-calculates",
                body: "Status becomes \"Pending Approval\" in your dashboard the moment payment lands.",
              },
              {
                day: "Friday",
                title: "Program Manager reviews",
                body: "Mechie audits every commission for accuracy and program compliance.",
              },
              {
                day: "Friday → Monday",
                title: "Owner signs off",
                body: "Bulk approvals are processed per VA per week — your batch is signed and queued for payout.",
              },
              {
                day: "Following week",
                title: "Money hits your account",
                body: "Choose Venmo, Zelle, Check, or ACH. Reference + method logged on every payment.",
              },
            ].map((step) => (
              <li
                key={step.title}
                className="border border-[#E5E7EB] bg-white p-5"
                data-testid={`payout-step-${step.title.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
              >
                <div className="font-mono-label text-[10px] text-[#0044FF]">{step.day}</div>
                <div className="mt-1 font-display text-lg font-black leading-tight">
                  {step.title}
                </div>
                <div className="mt-1 text-sm text-[#4B5563]">{step.body}</div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Why HCOB */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24 bg-[#F9FAFB]">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">Why HCOB Network</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            The crew is the product.
          </h2>
          <p className="mt-4 max-w-2xl text-[#4B5563]">
            We built the dashboard, the pipeline tooling, and the safeguards so you can focus on
            one thing: bringing in leads.
          </p>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
            {REASONS.map((r) => (
              <div
                key={r.title}
                data-testid={`why-${r.title.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                className="flex gap-4 border border-[#E5E7EB] bg-white p-6"
              >
                <div className="grid h-12 w-12 shrink-0 place-items-center bg-[#030712] text-white">
                  <r.icon size={22} weight="duotone" />
                </div>
                <div>
                  <div className="font-display text-lg font-black">{r.title}</div>
                  <div className="mt-1 text-sm text-[#4B5563] leading-relaxed">{r.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Earnings examples */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="font-mono-label mb-3">Earnings examples</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            What a typical month looks like.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
            {[
              {
                tag: "Casual",
                title: "1 deep clean / week",
                amount: "$100",
                detail: "4 deep cleans × $25 commission",
              },
              {
                tag: "Active",
                title: "Mixed pipeline",
                amount: "$300+",
                detail: "2 move-outs + 4 deep cleans + 2 recurring routine",
                accent: true,
              },
              {
                tag: "Power VA",
                title: "Commercial + recurring",
                amount: "$800+",
                detail: "1 small commercial account ($1k/mo × 5%) + 6 deep cleans + recurring stack",
              },
            ].map((e) => (
              <div
                key={e.title}
                data-testid={`earning-${e.tag.toLowerCase()}`}
                className={`border bg-white p-6 ${
                  e.accent ? "border-[#0044FF] border-2" : "border-[#E5E7EB]"
                }`}
              >
                <div
                  className={`font-mono-label text-[10px] ${
                    e.accent ? "text-[#0044FF]" : "text-[#4B5563]"
                  }`}
                >
                  {e.tag}
                </div>
                <div className="mt-2 font-display text-xl font-black">{e.title}</div>
                <div
                  className={`mt-4 font-display text-5xl font-black tracking-tight ${
                    e.accent ? "text-[#0044FF]" : "text-[#030712]"
                  }`}
                >
                  {e.amount}
                </div>
                <div className="mt-2 text-xs text-[#4B5563]">{e.detail}</div>
              </div>
            ))}
          </div>
          <p className="mt-6 max-w-2xl text-xs text-[#4B5563]">
            Examples are illustrative. Actual earnings depend on the leads you submit and the
            outcomes Ops drives. No guarantees — but no caps either.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-b border-[#E5E7EB] px-5 py-16 md:px-8 lg:px-10 lg:py-24 bg-[#F9FAFB]">
        <div className="mx-auto max-w-4xl">
          <div className="font-mono-label mb-3">FAQ</div>
          <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight">
            Real questions, real answers.
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
      <section className="px-5 py-20 md:px-8 lg:px-10 lg:py-32 bg-[#030712] text-white">
        <div className="mx-auto max-w-4xl text-center">
          <div className="font-mono-label mb-4 text-white/70">Ready?</div>
          <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter leading-[0.95]">
            Stop telling people about HCOB
            <br />
            for free.{" "}
            <span className="text-[#0044FF]">Get paid for it.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-white/70">
            Apply in under a minute. Get reviewed within 1 business day. Submit your first lead
            today.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link
              data-testid="footer-apply-cta"
              to="/register?as=va"
              className="inline-flex h-14 items-center gap-2 bg-[#0044FF] px-7 text-base font-bold text-white hover:bg-[#0036cc]"
            >
              <CurrencyDollar size={20} weight="fill" /> Apply now
            </Link>
            <Link
              data-testid="footer-signin-cta"
              to="/login"
              className="inline-flex h-14 items-center gap-2 border border-white/30 bg-transparent px-7 text-base font-semibold text-white hover:bg-white/10"
            >
              Already a VA? Sign in
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
            <div className="font-display text-sm font-black">HCOB Network · VA Commission</div>
          </div>
          <div className="flex items-center gap-4 text-xs text-[#4B5563]">
            <a href={PHONE_HREF} className="hover:text-[#030712]">
              {PHONE_DISPLAY}
            </a>
            <span className="text-[#9CA3AF]">·</span>
            <span>© HCOB Network · Baltimore, MD</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
