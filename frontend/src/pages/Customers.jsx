import React, { useEffect } from "react";
import { motion } from "framer-motion";
import QuoteRequestForm from "@/components/QuoteRequestForm";
import {
  Phone,
  ArrowRight,
  ArrowUpRight,
  PaperPlaneTilt,
  CheckCircle,
  XCircle,
  Broom,
  Buildings,
  ArrowsClockwise,
  Trash,
  Stack,
  Drop,
  Couch,
  Tree,
  Wrench,
  PaintBrushHousehold,
  HardHat,
  Sparkle,
  Laptop,
  House,
  MapTrifold,
  Clock,
  Users,
  ChartBar,
  ShieldCheck,
} from "@phosphor-icons/react";

const PHONE_DISPLAY = "(410) 870-9347";
const PHONE_HREF = "tel:+14108709347";

// ── Palette ────────────────────────────────────────────────────────────────
// Warm bone background · charcoal text · deep forest primary · terracotta accent
const BONE = "#F5F4F0";
const CHAR = "#1C1A17";
const FOREST = "#1B2A22";
const TERRA = "#C84B31";
const TERRA_DARK = "#A03A24";

// ── Data ───────────────────────────────────────────────────────────────────
const SERVICES = [
  { icon: Broom, label: "Residential Cleaning" },
  { icon: Buildings, label: "Commercial Cleaning" },
  { icon: ArrowsClockwise, label: "Move-Out & Turnover Cleaning" },
  { icon: Trash, label: "Junk Removal" },
  { icon: Stack, label: "Estate Cleanouts" },
  { icon: Drop, label: "Pressure Washing" },
  { icon: Couch, label: "Carpet Cleaning" },
  { icon: Tree, label: "Landscaping" },
  { icon: Wrench, label: "Handyman Services" },
  { icon: PaintBrushHousehold, label: "Painting" },
  { icon: HardHat, label: "Property Maintenance" },
  { icon: House, label: "Roofing & Windows" },
  { icon: Sparkle, label: "Specialty Property Services" },
  { icon: Laptop, label: "Virtual & Admin Services" },
];

const STEPS = [
  {
    n: "01",
    title: "Tell Us the Project",
    body:
      "One conversation covers everything — whether it's a single deep clean or a full multi-trade renovation. We scope it, price it, and hand you one clear quote.",
  },
  {
    n: "02",
    title: "We Dispatch Vetted Pros",
    body:
      "Every professional in our network is vetted and managed by our operations team. Crews clock in with GPS verification, work from a custom checklist built for your exact job, and answer to us — not to chance.",
  },
  {
    n: "03",
    title: "One Team Manages It Start to Finish",
    body:
      "We sequence the trades, coordinate the schedules, handle the crews, and keep you updated through one point of contact. You review the finished work. That's your whole job.",
  },
];

const COMPARISON_ROWS = [
  {
    dim: "Professionals",
    hcob: "Vetted, managed local crews",
    leadGen: "Anyone who paid for a listing",
  },
  {
    dim: "Coordination",
    hcob: "One point of contact for the entire project",
    leadGen: "You chase 4 different strangers",
  },
  {
    dim: "Project Management",
    hcob: "Multi-trade projects sequenced and coordinated for you",
    leadGen: "One trade at a time — you are the project manager",
  },
  {
    dim: "Accountability",
    hcob: "GPS-verified clock-in and platform-tracked work",
    leadGen: "Hope they show up",
  },
  {
    dim: "Billing",
    hcob: "One quote, one invoice, one accountable team",
    leadGen: "4 quotes, 4 contracts, 4 chances for surprises",
  },
  {
    dim: "Problem Resolution",
    hcob: "Problems fixed by us — accountability is built in",
    leadGen: "Disputes are between you and the contractor",
  },
];

const CASE_METRICS = [
  { icon: Users, k: "2×", label: "Workforce doubled without adding management overhead" },
  { icon: Clock, k: "24/7", label: "Two-shift model — daily output capacity doubled" },
  { icon: MapTrifold, k: "GPS", label: "Verified clock-in through the HCOB Network app" },
  { icon: ChartBar, k: "Live", label: "Automated quota tracking and payroll on-platform" },
];

// Image URLs from design_guidelines.json
const HERO_IMG =
  "https://images.unsplash.com/photo-1613490493576-7fde63acd811?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MTJ8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBob21lJTIwcmVub3ZhdGlvbiUyMGNvbnN0cnVjdGlvbnxlbnwwfHx8fDE3ODM5OTk5NTJ8MA&ixlib=rb-4.1.0&q=85";
const TEAM_IMG =
  "https://images.unsplash.com/photo-1694521787193-9293daeddbaa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDF8MHwxfHNlYXJjaHwzfHxjb250cmFjdG9yJTIwdGVhbSUyMHdvcmtpbmd8ZW58MHx8fHwxNzgzOTk5OTUyfDA&ixlib=rb-4.1.0&q=85";
const CASE_IMG =
  "https://images.unsplash.com/photo-1781243680823-aae6c7f1ff12?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NTZ8MHwxfHNlYXJjaHwzfHxpbmR1c3RyaWFsJTIwcmVjeWNsaW5nJTIwZmFjaWxpdHl8ZW58MHx8fHwxNzgzOTk5OTUyfDA&ixlib=rb-4.1.0&q=85";

// ── Motion helpers ─────────────────────────────────────────────────────────
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

// ── Page ───────────────────────────────────────────────────────────────────
export default function CustomersPage() {
  useEffect(() => {
    const prevTitle = document.title;
    const desc = document.querySelector('meta[name="description"]');
    const prevDesc = desc?.getAttribute("content");
    document.title =
      "HCOB Network | Managed Home & Property Services in Baltimore";
    if (desc) {
      desc.setAttribute(
        "content",
        "One call, every trade. HCOB Network manages your entire project — cleaning, junk removal, painting, roofing & more — with vetted local pros in Maryland."
      );
    }
    return () => {
      document.title = prevTitle;
      if (desc && prevDesc) desc.setAttribute("content", prevDesc);
    };
  }, []);

  return (
    <div
      data-testid="customers-page"
      className="min-h-screen bg-[#F5F4F0] text-[#1C1A17] antialiased"
      style={{ backgroundColor: BONE, color: CHAR }}
    >
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-[#1C1A17]/12 bg-[#F5F4F0]/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-3 px-5 py-4 md:px-10">
          <a
            href="/"
            data-testid="customers-brand-lockup"
            className="group flex items-center gap-3"
          >
            <div
              className="grid h-9 w-9 place-items-center rounded-sm text-[#F5F4F0]"
              style={{ backgroundColor: FOREST }}
            >
              <span className="font-display text-[15px] font-black leading-none">
                H
              </span>
            </div>
            <div className="leading-none">
              <div className="font-display text-[18px] font-black tracking-tight">
                HCOB Network
              </div>
              <div className="font-mono-label mt-1 text-[9px] tracking-[0.24em] text-[#1C1A17]/60">
                Baltimore · Maryland
              </div>
            </div>
          </a>

          <nav className="hidden items-center gap-8 md:flex">
            <a
              href="#how-it-works"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              How it works
            </a>
            <a
              href="#services"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Services
            </a>
            <a
              href="#case-study"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Case Study
            </a>
            <a
              href="#quote"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Get a Quote
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <a
              data-testid="header-phone-cta"
              href={PHONE_HREF}
              className="hidden sm:inline-flex items-center gap-2 rounded-sm px-4 py-2.5 text-[13px] font-bold text-[#F5F4F0] transition-transform hover:scale-[1.02]"
              style={{ backgroundColor: TERRA }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = TERRA_DARK)}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = TERRA)}
            >
              <Phone size={14} weight="fill" /> {PHONE_DISPLAY}
            </a>
            <a
              data-testid="header-phone-cta-mobile"
              href={PHONE_HREF}
              aria-label={`Call ${PHONE_DISPLAY}`}
              className="grid h-10 w-10 place-items-center rounded-sm text-[#F5F4F0] sm:hidden"
              style={{ backgroundColor: TERRA }}
            >
              <Phone size={16} weight="fill" />
            </a>
          </div>
        </div>
      </header>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="border-b border-[#1C1A17]/12">
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 lg:grid-cols-12">
          {/* Left: Forest panel */}
          <motion.div
            initial="hidden"
            animate="show"
            variants={stagger}
            className="lg:col-span-7 px-5 py-16 md:px-10 md:py-20 lg:py-28"
            style={{ backgroundColor: FOREST, color: BONE }}
          >
            <motion.div
              variants={fadeUp}
              className="font-mono-label flex items-center gap-2 text-[10px] tracking-[0.26em] text-[#F5F4F0]/70"
            >
              <span
                className="inline-block h-1.5 w-6"
                style={{ backgroundColor: TERRA }}
              />
              Baltimore, MD · Serving all of Maryland
            </motion.div>

            <motion.h1
              data-testid="customers-hero-title"
              variants={fadeUp}
              className="font-display mt-8 text-5xl font-black leading-[0.94] tracking-tighter sm:text-6xl lg:text-[76px]"
            >
              One&nbsp;call.
              <br />
              Every&nbsp;trade.
              <br />
              <span style={{ color: TERRA }}>Fully&nbsp;managed.</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mt-7 max-w-[560px] text-[15px] leading-[1.65] text-[#F5F4F0]/80 md:text-base"
            >
              HCOB Network connects you with{" "}
              <span className="text-[#F5F4F0]">vetted local professionals</span>{" "}
              across 13+ services — cleaning, junk removal, painting, landscaping,
              handyman work and more — all coordinated by one project management
              team. You get one point of contact, one plan, and a finished project.
              No chasing. No guesswork.
            </motion.p>

            <motion.div
              variants={fadeUp}
              className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
            >
              <a
                data-testid="hero-quote-cta"
                href="#quote"
                className="group inline-flex h-14 items-center justify-center gap-2 rounded-sm px-7 text-[14px] font-bold text-[#F5F4F0] transition-all"
                style={{ backgroundColor: TERRA }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = TERRA_DARK)}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = TERRA)}
              >
                <PaperPlaneTilt size={16} weight="fill" />
                Get Your Free Project Quote
                <ArrowRight
                  size={16}
                  className="transition-transform group-hover:translate-x-1"
                />
              </a>
              <a
                data-testid="hero-call-cta"
                href={PHONE_HREF}
                className="inline-flex h-14 items-center justify-center gap-2 rounded-sm border border-[#F5F4F0]/25 px-6 text-[13px] font-semibold text-[#F5F4F0] hover:bg-[#F5F4F0]/8"
              >
                <Phone size={16} weight="fill" /> Or call {PHONE_DISPLAY}
              </a>
            </motion.div>

            <motion.p
              variants={fadeUp}
              className="mt-5 text-[12px] text-[#F5F4F0]/55"
            >
              Talk to a real project coordinator today.
            </motion.p>

            {/* Signature strip */}
            <motion.div
              variants={fadeUp}
              className="mt-14 grid grid-cols-3 gap-6 border-t border-[#F5F4F0]/15 pt-8"
            >
              {[
                { k: "13+", l: "Trade services" },
                { k: "1", l: "Point of contact" },
                { k: "MD", l: "Statewide coverage" },
              ].map((s) => (
                <div key={s.l}>
                  <div
                    className="font-display text-3xl font-black leading-none tracking-tight"
                    style={{ color: TERRA }}
                  >
                    {s.k}
                  </div>
                  <div className="font-mono-label mt-2 text-[10px] tracking-[0.22em] text-[#F5F4F0]/60">
                    {s.l}
                  </div>
                </div>
              ))}
            </motion.div>
          </motion.div>

          {/* Right: Image */}
          <div className="relative min-h-[320px] lg:col-span-5 lg:min-h-0">
            <img
              src={HERO_IMG}
              alt="Modern construction site — HCOB Network manages multi-trade property projects across Maryland"
              className="absolute inset-0 h-full w-full object-cover"
              loading="eager"
            />
            {/* Editorial overlay label */}
            <div className="absolute bottom-6 left-6 right-6 flex items-end justify-between gap-4">
              <div
                className="max-w-[240px] rounded-sm px-4 py-3 text-[11px] leading-snug text-[#1C1A17] shadow-lg"
                style={{ backgroundColor: BONE }}
              >
                <div className="font-mono-label text-[9px] tracking-[0.28em] text-[#1C1A17]/60">
                  Multi-trade · sequenced
                </div>
                <div className="mt-1 font-display text-[13px] font-bold">
                  Roof, windows, carpet, admin — one crew of crews.
                </div>
              </div>
              <div
                className="font-display text-4xl font-black leading-none text-[#F5F4F0] drop-shadow-lg sm:text-5xl"
                aria-hidden
              >
                01
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Problem ───────────────────────────────────────────────────── */}
      <section
        data-testid="customers-problem"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            className="md:col-span-5 md:sticky md:top-24 md:self-start"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              02 · The problem
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              Managing contractors
              <br />
              shouldn&apos;t be a
              <br />
              <span style={{ color: TERRA }}>second job.</span>
            </h2>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.55, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="md:col-span-7"
          >
            <p className="font-display text-[22px] leading-[1.5] tracking-tight text-[#1C1A17] md:text-[26px]">
              <span
                className="float-left mr-3 mt-1 font-display text-[72px] font-black leading-[0.8]"
                style={{ color: TERRA }}
                aria-hidden
              >
                “
              </span>
              Finding reliable help means searching, calling, comparing quotes,
              and hoping the person who shows up is the person you vetted.
            </p>
            <div className="mt-6 space-y-5 text-[15px] leading-[1.75] text-[#1C1A17]/78 md:text-base">
              <p>
                Multiply that by every trade your project needs, and you&apos;ve
                become an unpaid project manager. One no-show throws off the whole
                timeline. One miscommunication means paying twice for the same
                work.
              </p>
              <p>
                And when something goes wrong, every contractor points at the
                other one.
              </p>
              <p className="font-display text-lg font-bold text-[#1C1A17]">
                There&apos;s a better way to get things done.
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────────────── */}
      <section
        id="how-it-works"
        data-testid="customers-process"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-28">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
                03 · How the network works
              </div>
              <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
                Three steps. Zero contractor juggling.
              </h2>
            </div>
            <a
              href="#quote"
              className="hidden md:inline-flex items-center gap-2 text-[13px] font-bold hover:opacity-70"
              style={{ color: TERRA }}
            >
              Skip ahead — get a quote <ArrowUpRight size={14} weight="bold" />
            </a>
          </div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger}
            className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3"
          >
            {STEPS.map((s, i) => (
              <motion.div
                key={s.n}
                data-testid={`process-step-${s.n}`}
                variants={fadeUp}
                className="group relative flex flex-col justify-between rounded-sm border border-[#1C1A17]/15 bg-[#FBFAF6] p-7 transition-all hover:border-[#1C1A17]/40 hover:-translate-y-1"
              >
                <div>
                  <div
                    className="font-display text-[68px] font-black leading-none tracking-tighter"
                    style={{ color: TERRA }}
                  >
                    {s.n}
                  </div>
                  <div className="mt-6 font-display text-xl font-black tracking-tight">
                    {s.title}
                  </div>
                  <p className="mt-3 text-[14px] leading-[1.65] text-[#1C1A17]/75">
                    {s.body}
                  </p>
                </div>
                {i < STEPS.length - 1 && (
                  <div className="mt-6 hidden items-center gap-2 text-[10px] font-mono-label tracking-[0.28em] text-[#1C1A17]/40 md:flex">
                    NEXT <ArrowRight size={12} />
                  </div>
                )}
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── Multi-trade narrative ─────────────────────────────────────── */}
      <section
        data-testid="customers-multi-trade"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="md:col-span-5"
          >
            <div className="relative">
              <img
                src={TEAM_IMG}
                alt="HCOB Network coordinated contractor team on a multi-trade job"
                className="w-full rounded-sm object-cover"
                style={{ aspectRatio: "4/5" }}
                loading="lazy"
              />
              <div
                className="absolute -bottom-6 -right-4 max-w-[220px] rounded-sm p-4 text-[#F5F4F0] shadow-lg sm:-right-6"
                style={{ backgroundColor: TERRA }}
              >
                <div className="font-mono-label text-[9px] tracking-[0.26em] text-[#F5F4F0]/85">
                  One outcome
                </div>
                <div className="mt-1 font-display text-[15px] font-bold leading-snug">
                  You don&apos;t hire four contractors — you hire one outcome.
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="md:col-span-7"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              04 · Multi-trade projects
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              One project. Every trade.
              <br />
              <span style={{ color: TERRA }}>One point of accountability.</span>
            </h2>

            <div className="mt-8 space-y-5 text-[15px] leading-[1.75] text-[#1C1A17]/78 md:text-base">
              <p>
                Say your property needs a new roof, window installation, carpet
                cleaning, and someone to handle the admin work behind it all. On a
                lead-gen site, that&apos;s four separate searches, four vetting
                processes, four contracts — and you personally coordinating the
                sequence so the roofer finishes before the window crew arrives and
                the carpets get cleaned last.
              </p>
              <p className="border-l-2 pl-4" style={{ borderColor: TERRA }}>
                If one contractor flakes, your whole timeline collapses, and nobody
                is accountable.
              </p>
              <p>
                With HCOB Network, it&apos;s one call. We scope the full project,
                sequence every trade in the right order, manage every crew on
                site, and deliver a finished project — with{" "}
                <span className="font-semibold text-[#1C1A17]">
                  better combined value than piecing it together yourself
                </span>
                , because one coordinated team means no overlap costs, no re-dos,
                and no paying twice for miscommunication.
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Comparison ledger ─────────────────────────────────────────── */}
      <section
        id="comparison"
        data-testid="customers-comparison"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="max-w-3xl"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              05 · The comparison
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              HCOB Network vs. Lead-Gen Sites
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-[#1C1A17]/70">
              Lead-gen sites sell you contacts.{" "}
              <span
                className="font-display font-bold"
                style={{ color: TERRA }}
              >
                We deliver outcomes.
              </span>
            </p>
          </motion.div>

          {/* Ledger */}
          <div className="mt-12 overflow-hidden rounded-sm border border-[#1C1A17]/15">
            {/* Header row */}
            <div className="grid grid-cols-12 border-b border-[#1C1A17]/15 bg-[#FBFAF6]">
              <div className="col-span-3 px-5 py-4 font-mono-label text-[10px] tracking-[0.26em] text-[#1C1A17]/60 md:px-8">
                Dimension
              </div>
              <div
                className="col-span-5 px-5 py-4 text-[#F5F4F0] md:col-span-5 md:px-8"
                style={{ backgroundColor: FOREST }}
              >
                <div className="font-mono-label text-[10px] tracking-[0.26em] text-[#F5F4F0]/70">
                  HCOB NETWORK
                </div>
                <div className="mt-0.5 font-display text-[13px] font-bold">
                  Managed outcome
                </div>
              </div>
              <div className="col-span-4 px-5 py-4 font-mono-label text-[10px] tracking-[0.26em] text-[#1C1A17]/60 md:px-8">
                Lead-gen sites
                <div className="mt-0.5 font-display text-[13px] font-bold normal-case tracking-normal text-[#1C1A17]/70">
                  (Angi, Thumbtack, Facebook)
                </div>
              </div>
            </div>

            {COMPARISON_ROWS.map((r, i) => (
              <motion.div
                key={r.dim}
                data-testid={`comparison-row-${r.dim.toLowerCase().replace(/\s+/g, "-")}`}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className={`grid grid-cols-12 ${
                  i !== COMPARISON_ROWS.length - 1 ? "border-b border-[#1C1A17]/10" : ""
                }`}
              >
                <div className="col-span-3 px-5 py-6 md:px-8">
                  <div className="font-display text-[15px] font-bold tracking-tight">
                    {r.dim}
                  </div>
                </div>
                <div
                  className="col-span-5 flex items-start gap-3 px-5 py-6 md:col-span-5 md:px-8"
                  style={{ backgroundColor: "rgba(27, 42, 34, 0.06)" }}
                >
                  <CheckCircle
                    size={18}
                    weight="fill"
                    className="mt-[3px] shrink-0"
                    style={{ color: FOREST }}
                  />
                  <div className="text-[14px] leading-[1.55] text-[#1C1A17] md:text-[15px]">
                    {r.hcob}
                  </div>
                </div>
                <div className="col-span-4 flex items-start gap-3 px-5 py-6 md:px-8">
                  <XCircle
                    size={18}
                    weight="fill"
                    className="mt-[3px] shrink-0 text-[#1C1A17]/35"
                  />
                  <div className="text-[13px] leading-[1.55] text-[#1C1A17]/60 md:text-[14px]">
                    {r.leadGen}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Case Study (Inverted) ─────────────────────────────────────── */}
      <section
        id="case-study"
        data-testid="customers-case-study"
        className="relative overflow-hidden"
        style={{ backgroundColor: FOREST, color: BONE }}
      >
        {/* subtle noise/grid overlay */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "radial-gradient(#F5F4F0 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        />

        <div className="relative mx-auto grid max-w-[1400px] grid-cols-1 gap-12 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="md:col-span-7"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#F5F4F0]/60">
              06 · Case study
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              A recycling operation that runs
              <br />
              <span style={{ color: TERRA }}>without the owner on site.</span>
            </h2>

            <div className="mt-8 space-y-5 text-[15px] leading-[1.75] text-[#F5F4F0]/78 md:text-base">
              <p>
                A Baltimore-area recycling operation depended entirely on one
                person being physically on site every day. No tracking, no
                accountability system, no way to scale.
              </p>
              <p>
                HCOB Network replaced that dependency with full{" "}
                <span className="text-[#F5F4F0]">
                  virtual management infrastructure
                </span>
                : a dedicated operations coordinator, a two-shift model that
                doubled daily output capacity, GPS-verified clock-in through the
                HCOB Network app, automated quota tracking, and payroll managed
                entirely on the platform.
              </p>
              <p
                className="rounded-sm border-l-2 py-3 pl-5 pr-4 font-display text-[18px] font-bold leading-snug"
                style={{
                  borderColor: TERRA,
                  color: BONE,
                  backgroundColor: "rgba(245, 244, 240, 0.05)",
                }}
              >
                We don&apos;t just send workers. We install the system.
              </p>
            </div>

            {/* Metrics */}
            <motion.div
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, margin: "-60px" }}
              variants={stagger}
              className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4"
            >
              {CASE_METRICS.map((m) => {
                const Icon = m.icon;
                return (
                  <motion.div
                    key={m.label}
                    data-testid={`case-study-metric-${m.k.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                    variants={fadeUp}
                    className="rounded-sm border border-[#F5F4F0]/15 bg-[#F5F4F0]/5 p-4 backdrop-blur-sm"
                  >
                    <Icon size={20} weight="duotone" style={{ color: TERRA }} />
                    <div className="font-display mt-3 text-3xl font-black leading-none tracking-tighter">
                      {m.k}
                    </div>
                    <div className="mt-2 text-[11px] leading-snug text-[#F5F4F0]/70">
                      {m.label}
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="md:col-span-5 md:sticky md:top-24 md:self-start"
          >
            <div className="relative">
              <img
                src={CASE_IMG}
                alt="Industrial recycling facility — HCOB Network managed operations case study"
                className="w-full rounded-sm object-cover shadow-2xl"
                style={{ aspectRatio: "4/5" }}
                loading="lazy"
              />
              <div
                className="absolute -left-3 top-6 rounded-sm px-3 py-2 text-[#1C1A17] shadow-lg sm:-left-5"
                style={{ backgroundColor: BONE }}
              >
                <div className="font-mono-label text-[9px] tracking-[0.28em] text-[#1C1A17]/60">
                  Baltimore, MD
                </div>
                <div className="mt-0.5 font-display text-[13px] font-bold">
                  Live client
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Services ──────────────────────────────────────────────────── */}
      <section
        id="services"
        data-testid="customers-services"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-28">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
                07 · Services
              </div>
              <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
                13+ Services.
                <br />
                <span style={{ color: TERRA }}>One network.</span>
              </h2>
              <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-[#1C1A17]/70">
                Serving Baltimore and the entire state of Maryland. Property
                managers: ask about multi-unit and recurring service programs.
              </p>
            </div>
            <a
              data-testid="services-call-cta"
              href={PHONE_HREF}
              className="inline-flex h-12 items-center gap-2 rounded-sm border border-[#1C1A17]/30 bg-transparent px-5 text-[13px] font-bold text-[#1C1A17] hover:bg-[#1C1A17] hover:text-[#F5F4F0]"
            >
              <Phone size={14} weight="fill" /> Call to scope a service
            </a>
          </div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-60px" }}
            variants={stagger}
            className="mt-14 grid grid-cols-2 gap-px border border-[#1C1A17]/15 bg-[#1C1A17]/15 sm:grid-cols-3 lg:grid-cols-4"
          >
            {SERVICES.map((s, i) => {
              const I = s.icon;
              return (
                <motion.div
                  key={s.label}
                  data-testid={`service-card-${i}`}
                  variants={fadeUp}
                  className="group relative flex items-start gap-3 bg-[#FBFAF6] p-5 transition-all duration-200 hover:bg-[#F5F4F0]"
                >
                  <div
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-[#1C1A17]/15 bg-[#F5F4F0] transition-all group-hover:scale-110 group-hover:border-[#C84B31]"
                    style={{ color: FOREST }}
                  >
                    <I size={20} weight="duotone" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-[14px] font-black leading-tight tracking-tight">
                      {s.label}
                    </div>
                    <div className="font-mono-label mt-1.5 text-[9px] tracking-[0.24em] text-[#1C1A17]/50 opacity-0 transition-opacity group-hover:opacity-100">
                      Ask about this service →
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>

          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-dashed border-[#1C1A17]/30 bg-[#FBFAF6] px-5 py-4">
            <div className="text-[13px] text-[#1C1A17]/70">
              Don&apos;t see your service?{" "}
              <strong className="text-[#1C1A17]">We probably handle it.</strong>
            </div>
            <a
              href="#quote"
              className="text-[13px] font-bold hover:opacity-75"
              style={{ color: TERRA }}
            >
              Ask us in the quote form →
            </a>
          </div>
        </div>
      </section>

      {/* ── Quote form ────────────────────────────────────────────────── */}
      <section
        id="quote"
        data-testid="customers-quote"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="md:col-span-5"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              08 · Get a quote
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              Send us the basics.
              <br />
              <span style={{ color: TERRA }}>We&apos;ll text you back.</span>
            </h2>
            <p className="mt-6 text-[15px] leading-relaxed text-[#1C1A17]/75">
              Tell us what you need and we&apos;ll line up the right pro. No
              accounts, no logins, no spam — just a quick reply from a real
              person.
            </p>

            <ul className="mt-8 space-y-4">
              {[
                "Reply usually within the hour during business hours",
                "Free estimates · no obligation",
                "One point of contact for every service",
              ].map((t) => (
                <li
                  key={t}
                  className="flex items-start gap-3 text-[14px] text-[#1C1A17]"
                >
                  <span
                    className="mt-[9px] inline-block h-[6px] w-8 shrink-0"
                    style={{ backgroundColor: TERRA }}
                  />
                  {t}
                </li>
              ))}
            </ul>

            <div className="mt-10 rounded-sm border border-[#1C1A17]/15 bg-[#FBFAF6] p-5">
              <div className="flex items-center gap-2">
                <ShieldCheck size={16} weight="fill" style={{ color: FOREST }} />
                <div className="font-mono-label text-[10px] tracking-[0.24em] text-[#1C1A17]/60">
                  We never share your info
                </div>
              </div>
              <div className="mt-2 text-[13px] text-[#1C1A17]/75">
                Or dial{" "}
                <a
                  href={PHONE_HREF}
                  className="font-bold text-[#1C1A17] underline underline-offset-2"
                >
                  {PHONE_DISPLAY}
                </a>{" "}
                and talk to a coordinator directly.
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="md:col-span-7"
          >
            <div className="rounded-sm border border-[#1C1A17]/15 bg-[#FBFAF6] p-4 md:p-6">
              <QuoteRequestForm />
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <section
        data-testid="customers-cta"
        className="relative"
        style={{ backgroundColor: TERRA, color: BONE }}
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 px-5 py-20 md:grid-cols-12 md:px-10 md:py-24">
          <div className="md:col-span-7">
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#F5F4F0]/70">
              Ready when you are
            </div>
            <h2 className="font-display mt-3 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl lg:text-6xl">
              Ready to hand off the headache?
            </h2>
            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-[#F5F4F0]/85 md:text-base">
              Tell us what your property needs. We&apos;ll handle everything else
              — one quote, one team, one finished project.
            </p>
          </div>
          <div className="flex flex-col items-start justify-end gap-3 md:col-span-5 md:items-end">
            <a
              data-testid="footer-quote-cta"
              href="#quote"
              className="inline-flex h-14 items-center gap-2 rounded-sm px-7 text-[14px] font-bold text-[#C84B31] transition-transform hover:scale-[1.02]"
              style={{ backgroundColor: BONE }}
            >
              <PaperPlaneTilt size={16} weight="fill" /> Get Your Free Project Quote
            </a>
            <a
              data-testid="footer-call-cta"
              href={PHONE_HREF}
              className="inline-flex h-14 items-center gap-2 rounded-sm border border-[#F5F4F0]/40 px-6 text-[13px] font-bold text-[#F5F4F0] hover:bg-[#F5F4F0]/10"
            >
              <Phone size={16} weight="fill" /> Call {PHONE_DISPLAY}
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer style={{ backgroundColor: CHAR, color: BONE }}>
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-14 md:grid-cols-12 md:px-10">
          <div className="md:col-span-5">
            <div className="flex items-center gap-3">
              <div
                className="grid h-9 w-9 place-items-center rounded-sm"
                style={{ backgroundColor: TERRA }}
              >
                <span className="font-display text-[15px] font-black leading-none text-[#F5F4F0]">
                  H
                </span>
              </div>
              <div className="font-display text-lg font-black tracking-tight">
                HCOB Network
              </div>
            </div>
            <p className="mt-4 max-w-sm text-[13px] leading-relaxed text-[#F5F4F0]/65">
              A project management company connecting customers with trusted
              service professionals across Baltimore and all of Maryland.
            </p>
            <p
              className="mt-5 font-display text-[13px] font-bold italic"
              style={{ color: TERRA }}
            >
              By the Community. For the Community.
            </p>
          </div>

          <div className="md:col-span-3">
            <div className="font-mono-label mb-4 text-[10px] tracking-[0.28em] text-[#F5F4F0]/50">
              Contact
            </div>
            <a
              href={PHONE_HREF}
              className="block font-display text-2xl font-black hover:opacity-75"
              style={{ color: BONE }}
            >
              {PHONE_DISPLAY}
            </a>
            <div className="mt-3 text-[12px] text-[#F5F4F0]/60">
              Mon–Sat · Baltimore, Maryland
            </div>
            <a
              href="#quote"
              className="mt-5 inline-flex items-center gap-1 text-[13px] font-bold hover:opacity-75"
              style={{ color: TERRA }}
            >
              Request a quote <ArrowRight size={14} />
            </a>
          </div>

          <div className="md:col-span-4">
            <div className="font-mono-label mb-4 text-[10px] tracking-[0.28em] text-[#F5F4F0]/50">
              Also on the network
            </div>
            <div className="flex flex-col gap-3 text-[13px]">
              <a
                data-testid="footer-contractors-link"
                href="/work"
                className="group inline-flex items-center gap-2 text-[#F5F4F0]/85 hover:text-[#F5F4F0]"
              >
                <span
                  className="inline-block h-[6px] w-4"
                  style={{ backgroundColor: TERRA }}
                />
                For contractors — join the crew
                <ArrowUpRight
                  size={12}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </a>
              <a
                href="/vas"
                className="group inline-flex items-center gap-2 text-[#F5F4F0]/85 hover:text-[#F5F4F0]"
              >
                <span
                  className="inline-block h-[6px] w-4"
                  style={{ backgroundColor: TERRA }}
                />
                Refer leads · earn commissions
                <ArrowUpRight
                  size={12}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </a>
            </div>
          </div>
        </div>

        <div className="border-t border-[#F5F4F0]/10">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-5 py-5 text-[11px] text-[#F5F4F0]/55 md:px-10">
            <div>
              © {new Date().getFullYear()} HCOB Network · hcobnetwork.com
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              <a
                href="/privacy.html"
                data-testid="footer-privacy-link"
                className="hover:text-[#F5F4F0]"
              >
                Privacy
              </a>
              <a
                href="/terms.html"
                data-testid="footer-terms-link"
                className="hover:text-[#F5F4F0]"
              >
                Terms
              </a>
              <a
                href="/sms-terms.html"
                data-testid="footer-sms-terms-link"
                className="hover:text-[#F5F4F0]"
              >
                SMS Terms
              </a>
              <a
                href="https://hcobcleaners.com"
                target="_blank"
                rel="noreferrer"
                className="hover:text-[#F5F4F0]"
              >
                HCOB Cleaners
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
