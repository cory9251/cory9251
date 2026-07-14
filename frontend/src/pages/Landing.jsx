import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { motion } from "framer-motion";
import { BACKEND_URL } from "@/lib/api";
import {
  ArrowRight,
  ArrowUpRight,
  Phone,
  MapPin,
  Clock,
  CheckCircle,
  Broadcast,
  Timer,
  MapPinLine,
  CurrencyDollar,
  Users,
  Handshake,
  IdentificationBadge,
  Repeat,
  Quotes,
} from "@phosphor-icons/react";
import { TAG_CONFIG, getTagBorderClass, getOrderedTags } from "@/lib/gigTags";
import { formatGigShort } from "@/lib/gigDate";

// ── Palette (matches customer page for brand cohesion) ─────────────────────
const BONE = "#F5F4F0";
const CHAR = "#1C1A17";
const FOREST = "#1B2A22";
const TERRA = "#C84B31";
const TERRA_DARK = "#A03A24";

const PHONE_DISPLAY = "410-701-0570";
const PHONE_HREF = "tel:+14107010570";

const CORY_IMG =
  "https://customer-assets.emergentagent.com/job_work-connect-147/artifacts/kg9ewgqo_IMG-20260713-WA0009.jpg";

// ── Division of labor ──────────────────────────────────────────────────────
const DIVISION = [
  { we: "Finding and winning the customers", you: "Being excellent at your specialty" },
  { we: "Scoping and quoting every project", you: "Showing up on time, ready to work" },
  { we: "Scheduling and dispatch through the app", you: "Working the custom checklist for the job" },
  { we: "Collecting payment from the customer", you: "Delivering quality that earns the next call" },
  {
    we: "Coordinating other trades on multi-trade projects",
    you: "Project management and customer communication",
  },
];

// ── Platform features ──────────────────────────────────────────────────────
const PLATFORM = [
  {
    icon: Broadcast,
    title: "Opportunity Blasts",
    body:
      "New projects in your trade and area hit your phone through the HCOB Network app. See the scope, the location area, and the payout — then claim it.",
  },
  {
    icon: Timer,
    title: "Shift Pickup",
    body:
      "Open shifts on active contracts are posted in the app. Fill gaps in your week on your schedule, not someone else's.",
  },
  {
    icon: MapPinLine,
    title: "GPS Clock-In / Clock-Out",
    body:
      "Clock in on site through the app. Your hours are tracked automatically — protected for you, verified for the customer.",
  },
  {
    icon: CurrencyDollar,
    title: "Payroll on the Platform",
    body:
      "Payouts are tracked and managed inside the network. You always know what you've earned and when it's coming.",
  },
];

// ── Motion helpers ─────────────────────────────────────────────────────────
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

export default function Landing() {
  const nav = useNavigate();
  const [liveGigs, setLiveGigs] = useState([]);
  const [gigsLoading, setGigsLoading] = useState(true);

  // SEO
  useEffect(() => {
    const prevTitle = document.title;
    const desc = document.querySelector('meta[name="description"]');
    const prevDesc = desc?.getAttribute("content");
    document.title = "Join the HCOB Network | Contractor Jobs in Maryland";
    if (desc) {
      desc.setAttribute(
        "content",
        "Skilled in a trade? Join a network of specialists in Baltimore. We bring the customers, quotes & payments — you do the work you're great at. Apply today."
      );
    }
    return () => {
      document.title = prevTitle;
      if (desc && prevDesc) desc.setAttribute("content", prevDesc);
    };
  }, []);

  useEffect(() => {
    axios
      .get(`${BACKEND_URL}/api/public/gigs?limit=3`)
      .then((r) => setLiveGigs(r.data || []))
      .catch(() => setLiveGigs([]))
      .finally(() => setGigsLoading(false));
  }, []);

  return (
    <div
      data-testid="landing-page"
      className="min-h-screen antialiased"
      style={{ backgroundColor: BONE, color: CHAR }}
    >
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-[#1C1A17]/12 bg-[#F5F4F0]/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-3 px-5 py-4 md:px-10">
          <Link
            to="/work"
            data-testid="nav-brand-lockup"
            className="group flex items-center gap-3"
          >
            <div
              className="grid h-9 w-9 place-items-center rounded-sm text-[#F5F4F0]"
              style={{ backgroundColor: FOREST }}
            >
              <span className="font-display text-[15px] font-black leading-none">H</span>
            </div>
            <div className="leading-none">
              <div className="font-display text-[18px] font-black tracking-tight">
                HCOB Network
              </div>
              <div className="font-mono-label mt-1 text-[9px] tracking-[0.24em] text-[#1C1A17]/60">
                Contractor network · Baltimore, MD
              </div>
            </div>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            <a
              href="#the-network"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              The network
            </a>
            <a
              href="#platform"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Platform
            </a>
            <a
              href="#live"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Live projects
            </a>
            <a
              data-testid="nav-customers-link"
              href="/"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              For customers
            </a>
            <Link
              data-testid="nav-vas-link"
              to="/vas"
              className="text-[13px] font-semibold text-[#1C1A17]/70 hover:text-[#1C1A17]"
            >
              Refer &amp; earn
            </Link>
          </nav>

          <div className="flex items-center gap-2">
            <button
              data-testid="nav-login-btn"
              onClick={() => nav("/login")}
              className="hidden sm:inline-flex items-center rounded-sm px-3 py-2 text-[13px] font-semibold text-[#1C1A17]/75 hover:text-[#1C1A17]"
            >
              Sign in
            </button>
            <button
              data-testid="nav-register-btn"
              onClick={() => nav("/register")}
              className="inline-flex items-center gap-2 rounded-sm px-4 py-2.5 text-[13px] font-bold text-[#F5F4F0] transition-all hover:scale-[1.02]"
              style={{ backgroundColor: TERRA }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = TERRA_DARK)}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = TERRA)}
            >
              Apply <ArrowRight size={14} weight="bold" />
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="border-b border-[#1C1A17]/12">
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 lg:grid-cols-12">
          {/* Left: Forest panel with copy */}
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
              For skilled trades in Maryland · Application required
            </motion.div>

            <motion.h1
              data-testid="hero-headline"
              variants={fadeUp}
              className="font-display mt-8 text-[44px] font-black leading-[0.94] tracking-tighter sm:text-6xl lg:text-[72px]"
            >
              Do the work
              <br />
              you&rsquo;re great at.
              <br />
              <span style={{ color: TERRA }}>We&rsquo;ll handle the rest.</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mt-7 max-w-[560px] text-[15px] leading-[1.65] text-[#F5F4F0]/80 md:text-base"
            >
              You didn&rsquo;t get into your trade to chase leads, quote jobs for
              free, and hunt down payments. The HCOB Network is a{" "}
              <span className="text-[#F5F4F0]">collaboration of specialists</span>{" "}
              — cleaners, painters, junk removal pros, landscapers, handymen and
              more — where we bring the projects and you bring the skill.
            </motion.p>

            <motion.div
              variants={fadeUp}
              className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
            >
              <button
                data-testid="hero-cta-register"
                onClick={() => nav("/register")}
                className="group inline-flex h-14 items-center justify-center gap-2 rounded-sm px-7 text-[14px] font-bold text-[#F5F4F0] transition-all"
                style={{ backgroundColor: TERRA }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = TERRA_DARK)}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = TERRA)}
              >
                Apply to Join the Network
                <ArrowRight
                  size={16}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-1"
                />
              </button>
              <button
                data-testid="hero-cta-login"
                onClick={() => nav("/login")}
                className="inline-flex h-14 items-center justify-center gap-2 rounded-sm border border-[#F5F4F0]/25 px-6 text-[13px] font-semibold text-[#F5F4F0] hover:bg-[#F5F4F0]/8"
              >
                I&rsquo;m already in the network
              </button>
            </motion.div>

            <motion.div
              variants={fadeUp}
              className="mt-5 flex items-center gap-2 text-[12px] text-[#F5F4F0]/60"
            >
              <Phone size={12} weight="fill" />
              Questions first? Call{" "}
              <a
                href={PHONE_HREF}
                className="font-bold text-[#F5F4F0] underline underline-offset-2"
              >
                {PHONE_DISPLAY}
              </a>{" "}
              and talk to our operations team.
            </motion.div>

            {/* VAs cross-link */}
            <motion.div variants={fadeUp}>
              <Link
                to="/vas"
                data-testid="hero-vas-callout"
                className="mt-10 inline-flex items-center gap-2 rounded-sm border-l-2 bg-[#F5F4F0]/6 px-4 py-2.5 text-[12px] font-semibold text-[#F5F4F0]/85 hover:bg-[#F5F4F0]/10"
                style={{ borderLeftColor: TERRA }}
              >
                <CurrencyDollar size={13} weight="fill" style={{ color: TERRA }} />
                Prefer to refer customers instead of doing the work?
                <span style={{ color: TERRA }}>Earn commissions →</span>
              </Link>
            </motion.div>
          </motion.div>

          {/* Right: Cory portrait + quote */}
          <div className="relative min-h-[440px] lg:col-span-5 lg:min-h-0">
            <img
              src={CORY_IMG}
              alt="Cory Clarke — Founder & Lead Project Manager, HCOB Network"
              className="absolute inset-0 h-full w-full object-cover"
              loading="eager"
            />
            {/* Founder credential ribbon */}
            <div
              className="absolute right-6 top-6 rounded-sm px-3 py-2 shadow-lg"
              style={{ backgroundColor: TERRA, color: BONE }}
            >
              <div className="font-mono-label text-[9px] tracking-[0.28em] text-[#F5F4F0]/85">
                Founder
              </div>
              <div className="mt-0.5 font-display text-[13px] font-black leading-none">
                Cory Clarke
              </div>
            </div>
            {/* Founder quote card */}
            <div className="absolute bottom-6 left-6 right-6 md:right-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.4 }}
                className="rounded-sm p-5 shadow-2xl md:p-6"
                style={{ backgroundColor: BONE }}
              >
                <Quotes
                  size={22}
                  weight="fill"
                  style={{ color: TERRA }}
                  className="mb-2"
                />
                <div className="font-display text-[17px] font-black leading-[1.25] tracking-tight text-[#1C1A17] md:text-[19px]">
                  We structure the unstructured. That is the true essence of the
                  HCOB Network.
                </div>
                <div className="mt-4 flex items-center gap-3 border-t border-[#1C1A17]/10 pt-3">
                  <div
                    className="h-6 w-1"
                    style={{ backgroundColor: TERRA }}
                    aria-hidden
                  />
                  <div>
                    <div className="font-display text-[13px] font-bold leading-none text-[#1C1A17]">
                      Cory Clarke
                    </div>
                    <div className="font-mono-label mt-1 text-[9px] tracking-[0.24em] text-[#1C1A17]/60">
                      Owner · Founder · Lead Project Manager
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* ── The Network (What This Is And Isn't) ──────────────────────── */}
      <section
        id="the-network"
        data-testid="section-network"
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
              02 · What this is
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              A network of
              <br />
              specialists —
              <br />
              <span style={{ color: TERRA }}>not a subbing mill.</span>
            </h2>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="md:col-span-7"
          >
            <p className="font-display text-[22px] leading-[1.5] tracking-tight text-[#1C1A17] md:text-[26px]">
              <span
                className="float-left mr-3 mt-1 font-display text-[72px] font-black leading-[0.8]"
                style={{ color: TERRA }}
                aria-hidden
              >
                &ldquo;
              </span>
              You&rsquo;ve seen how the other platforms work. Lead-gen sites
              charge you for contacts that five other contractors already bought.
            </p>

            <div className="mt-6 space-y-5 text-[15px] leading-[1.75] text-[#1C1A17]/78 md:text-base">
              <p>
                GCs call it &ldquo;partnership&rdquo; and treat you like a number.
                Every job is a gamble, and you carry all the risk.
              </p>
              <p>
                We built the HCOB Network differently. Every professional here
                specializes in something. When a project comes in — a single deep
                clean or a full multi-trade renovation — the right specialists
                collaborate on it, coordinated by our project management team.{" "}
                <span className="font-semibold text-[#1C1A17]">
                  The customer gets a better result. You get to focus on your
                  craft.
                </span>
              </p>
              <p className="font-display text-lg font-bold text-[#1C1A17]">
                We&rsquo;re not looking to sub work out and disappear. We&rsquo;re
                looking for pros we can work with over and over again.
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Division of Labor ─────────────────────────────────────────── */}
      <section
        data-testid="section-division"
        className="border-b border-[#1C1A17]/12 bg-[#FBFAF6]"
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
              03 · The collaboration, in plain terms
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              You do the craft.
              <br />
              <span style={{ color: TERRA }}>We do the rest.</span>
            </h2>
          </motion.div>

          {/* Ledger */}
          <div className="mt-12 overflow-hidden rounded-sm border border-[#1C1A17]/15 bg-[#F5F4F0]">
            {/* Header row */}
            <div className="grid grid-cols-1 md:grid-cols-12">
              <div
                className="border-b border-[#1C1A17]/15 px-5 py-4 md:col-span-6 md:border-b-0 md:border-r md:px-8"
                style={{ backgroundColor: FOREST, color: BONE }}
              >
                <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#F5F4F0]/70">
                  WE HANDLE
                </div>
                <div className="mt-0.5 font-display text-[15px] font-black">
                  Operations, coordination &amp; billing
                </div>
              </div>
              <div
                className="border-b border-[#1C1A17]/15 px-5 py-4 md:col-span-6 md:border-b-0 md:px-8"
                style={{ backgroundColor: BONE }}
              >
                <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/60">
                  YOU HANDLE
                </div>
                <div className="mt-0.5 font-display text-[15px] font-black text-[#1C1A17]">
                  The craft the customer hired us for
                </div>
              </div>
            </div>

            {DIVISION.map((r, i) => (
              <motion.div
                key={r.we}
                data-testid={`division-row-${i}`}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className={`grid grid-cols-1 md:grid-cols-12 ${
                  i !== DIVISION.length - 1 ? "border-b border-[#1C1A17]/10" : ""
                }`}
              >
                <div
                  className="flex items-start gap-3 border-b border-[#1C1A17]/10 px-5 py-5 md:col-span-6 md:border-b-0 md:border-r md:px-8"
                  style={{ backgroundColor: "rgba(27, 42, 34, 0.06)" }}
                >
                  <CheckCircle
                    size={18}
                    weight="fill"
                    className="mt-[3px] shrink-0"
                    style={{ color: FOREST }}
                  />
                  <div className="text-[14px] leading-[1.55] text-[#1C1A17] md:text-[15px]">
                    {r.we}
                  </div>
                </div>
                <div className="flex items-start gap-3 px-5 py-5 md:col-span-6 md:px-8">
                  <span
                    className="mt-[8px] inline-block h-[6px] w-4 shrink-0"
                    style={{ backgroundColor: TERRA }}
                  />
                  <div className="text-[14px] leading-[1.55] text-[#1C1A17] md:text-[15px]">
                    {r.you}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="mt-8 max-w-3xl text-[14px] leading-relaxed text-[#1C1A17]/75 md:text-[15px]"
          >
            Every job comes with a clear payout stated upfront and a custom
            checklist that defines exactly what&rsquo;s expected.{" "}
            <span className="font-semibold text-[#1C1A17]">
              No scope creep, no surprises, no chasing checks
            </span>{" "}
            — payment is handled electronically through the network.
          </motion.p>
        </div>
      </section>

      {/* ── How Jobs Reach You (Platform features) ────────────────────── */}
      <section
        id="platform"
        data-testid="section-platform"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-28">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
                04 · How jobs reach you
              </div>
              <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
                Real jobs, delivered
                <br />
                through a{" "}
                <span style={{ color: TERRA }}>real platform.</span>
              </h2>
            </div>
            <button
              onClick={() => nav("/register")}
              className="hidden md:inline-flex items-center gap-2 rounded-sm px-5 py-3 text-[13px] font-bold text-[#F5F4F0]"
              style={{ backgroundColor: FOREST }}
            >
              Apply to join <ArrowRight size={14} weight="bold" />
            </button>
          </div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger}
            className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2"
          >
            {PLATFORM.map((p, i) => {
              const Icon = p.icon;
              return (
                <motion.div
                  key={p.title}
                  data-testid={`platform-card-${i}`}
                  variants={fadeUp}
                  className="group relative flex gap-5 rounded-sm border border-[#1C1A17]/15 bg-[#FBFAF6] p-7 transition-all hover:border-[#1C1A17]/40 hover:-translate-y-1"
                >
                  <div
                    className="grid h-12 w-12 shrink-0 place-items-center rounded-sm"
                    style={{ backgroundColor: FOREST, color: BONE }}
                  >
                    <Icon size={22} weight="duotone" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-lg font-black tracking-tight">
                      {p.title}
                    </div>
                    <p className="mt-2 text-[14px] leading-[1.65] text-[#1C1A17]/75">
                      {p.body}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ── Live Projects Feed ────────────────────────────────────────── */}
      <section
        id="live"
        data-testid="landing-live-gigs"
        className="border-b border-[#1C1A17]/12 bg-[#FBFAF6]"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-28">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="font-mono-label mb-3 flex items-center gap-2 text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
                <span className="relative grid h-2 w-2 place-items-center">
                  <span
                    className="absolute h-2 w-2 animate-ping rounded-full"
                    style={{ backgroundColor: TERRA }}
                  />
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: TERRA }}
                  />
                </span>
                Live · projects moving through the network
              </div>
              <h2 className="font-display text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
                A snapshot of the board
                <br />
                <span style={{ color: TERRA }}>this week.</span>
              </h2>
              <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-[#1C1A17]/70">
                Network members see the full project scope, location, and
                payout once they sign in.
              </p>
            </div>
            <button
              data-testid="live-gigs-cta-register"
              onClick={() => nav("/register")}
              className="hidden md:inline-flex h-12 items-center gap-2 rounded-sm px-5 text-[13px] font-bold text-[#F5F4F0]"
              style={{ backgroundColor: TERRA }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = TERRA_DARK)}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = TERRA)}
            >
              Apply to see them all <ArrowRight size={14} weight="bold" />
            </button>
          </div>

          <div className="mt-10">
            {gigsLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-44 animate-pulse rounded-sm border border-[#1C1A17]/10 bg-[#F5F4F0]"
                  />
                ))}
              </div>
            ) : liveGigs.length === 0 ? (
              <div
                data-testid="live-gigs-empty"
                className="flex flex-col items-start gap-4 rounded-sm border border-dashed border-[#1C1A17]/25 bg-[#F5F4F0] p-10 text-sm text-[#1C1A17]/70"
              >
                <div className="font-display text-lg font-bold text-[#1C1A17]">
                  Nothing in the public window at this exact moment.
                </div>
                <div>
                  We route new projects through the network all week. Apply now
                  so you&rsquo;re in the room when the next one lands.
                </div>
                <button
                  data-testid="live-gigs-empty-cta"
                  onClick={() => nav("/register")}
                  className="mt-2 inline-flex h-10 items-center gap-2 rounded-sm px-5 text-[13px] font-bold text-[#F5F4F0]"
                  style={{ backgroundColor: TERRA }}
                >
                  Apply to join <ArrowRight size={14} weight="bold" />
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {liveGigs.map((g) => {
                  const slotsLeft = Math.max(
                    0,
                    Number(g.slots || 0) - Number(g.slots_filled || 0)
                  );
                  const isComingSoon = g.status === "coming_soon";
                  const activeTags = getOrderedTags(g.tags);
                  const tagBorder = getTagBorderClass(g.tags);
                  return (
                    <button
                      key={g.gig_id}
                      data-testid={`landing-gig-${g.gig_id}`}
                      onClick={() =>
                        nav(`/register?next=/crew/assignments/${g.gig_id}`)
                      }
                      className={`group relative flex flex-col gap-3 rounded-sm bg-[#F5F4F0] p-5 text-left transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.18)] ${
                        tagBorder || "border border-[#1C1A17]/15"
                      }`}
                    >
                      {(activeTags.length > 0 || isComingSoon) && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {activeTags.map((t) => {
                            const cfg = TAG_CONFIG[t];
                            const I = cfg.icon;
                            return (
                              <span
                                key={t}
                                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[9px] font-black tracking-[0.2em] ${cfg.pillClass}`}
                              >
                                <I
                                  size={11}
                                  weight="fill"
                                  className={cfg.pulse ? "animate-pulse" : ""}
                                />
                                {cfg.label}
                              </span>
                            );
                          })}
                          {isComingSoon && (
                            <span
                              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[9px] font-black tracking-[0.2em]"
                              style={{ backgroundColor: FOREST, color: BONE }}
                            >
                              UPCOMING
                            </span>
                          )}
                        </div>
                      )}
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-mono-label flex items-center gap-1.5 text-[10px] tracking-[0.24em] text-[#1C1A17]/60">
                          {g.category} · {g.subcategory || "general"}
                        </div>
                        {slotsLeft > 0 && (
                          <span
                            className="font-mono-label text-[9px] tracking-[0.24em]"
                            style={{ color: TERRA }}
                          >
                            {slotsLeft} slot{slotsLeft === 1 ? "" : "s"} open
                          </span>
                        )}
                      </div>
                      <div className="font-display text-lg font-bold leading-snug text-[#1C1A17]">
                        {g.title}
                      </div>
                      <div className="mt-auto flex items-end justify-between gap-2 border-t border-[#1C1A17]/12 pt-3">
                        <div className="space-y-1 text-xs text-[#1C1A17]/70">
                          <div className="flex items-center gap-1.5">
                            <MapPin size={12} weight="duotone" />
                            <span className="font-semibold text-[#1C1A17]">
                              {g.location || "Baltimore area"}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Clock size={12} weight="duotone" />
                            <span>{formatGigShort(g)}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono-label text-[9px] tracking-[0.24em] text-[#1C1A17]/60">
                            Payout
                          </div>
                          <div
                            className="text-[12px] font-bold leading-snug"
                            style={{ color: TERRA }}
                          >
                            See in app
                          </div>
                        </div>
                      </div>
                      <div
                        className="font-mono-label mt-1 text-[10px] tracking-[0.24em] opacity-0 transition-opacity group-hover:opacity-100"
                        style={{ color: TERRA }}
                      >
                        Apply to claim →
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Repeat-Work Promise ───────────────────────────────────────── */}
      <section
        data-testid="section-repeat"
        className="relative overflow-hidden"
        style={{ backgroundColor: FOREST, color: BONE }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage: "radial-gradient(#F5F4F0 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        />
        <div className="relative mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="md:col-span-8"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#F5F4F0]/60">
              05 · The repeat-work promise
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              Deliver quality once.
              <br />
              <span style={{ color: TERRA }}>Become our first call.</span>
            </h2>

            <div className="mt-8 space-y-5 text-[15px] leading-[1.75] text-[#F5F4F0]/78 md:text-base">
              <p>
                On lead-gen sites, every job is a new gamble — new customer, new
                negotiation, new risk.
              </p>
              <p>
                In the HCOB Network,{" "}
                <span className="text-[#F5F4F0]">
                  quality gets rewarded with consistency
                </span>
                . When you deliver, you become our go-to specialist for your
                trade: first call on new projects, repeat dispatches on
                recurring accounts, and a growing track record inside a network
                that already has the customers.
              </p>
              <p
                className="rounded-sm border-l-2 py-3 pl-5 pr-4 font-display text-[18px] font-bold leading-snug"
                style={{
                  borderColor: TERRA,
                  color: BONE,
                  backgroundColor: "rgba(245, 244, 240, 0.05)",
                }}
              >
                You&rsquo;ve spent years getting good at this. That should count
                for something. Here, it does.
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="md:col-span-4"
          >
            <div className="grid grid-cols-1 gap-4">
              {[
                { icon: Repeat, k: "Repeat", l: "Dispatches on recurring accounts" },
                { icon: IdentificationBadge, k: "First-call", l: "Go-to specialist on new projects" },
                { icon: Handshake, k: "Track record", l: "Grows inside a real network" },
              ].map((m) => {
                const Icon = m.icon;
                return (
                  <div
                    key={m.k}
                    className="rounded-sm border border-[#F5F4F0]/15 bg-[#F5F4F0]/5 p-5 backdrop-blur-sm"
                  >
                    <Icon size={20} weight="duotone" style={{ color: TERRA }} />
                    <div className="font-display mt-3 text-2xl font-black tracking-tight">
                      {m.k}
                    </div>
                    <div className="mt-2 text-[12px] leading-snug text-[#F5F4F0]/70">
                      {m.l}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Referral / Grow the Network ───────────────────────────────── */}
      <section
        data-testid="section-referral"
        className="border-b border-[#1C1A17]/12"
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-10 px-5 py-20 md:grid-cols-12 md:px-10 md:py-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="md:col-span-7"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              06 · Grow the network, get paid
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl">
              Know another pro?
              <br />
              <span style={{ color: TERRA }}>That&rsquo;s worth money.</span>
            </h2>
            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-[#1C1A17]/75 md:text-base">
              Good professionals know other good professionals. Refer a client
              lead to the network and earn a{" "}
              <span className="font-semibold text-[#1C1A17]">
                10% referral commission
              </span>{" "}
              when the job closes. Your network becomes part of your income.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="md:col-span-5"
          >
            <div
              className="relative overflow-hidden rounded-sm p-8"
              style={{ backgroundColor: TERRA, color: BONE }}
            >
              <Users
                size={40}
                weight="duotone"
                className="text-[#F5F4F0]/85"
              />
              <div className="mt-6 flex items-baseline gap-2">
                <div className="font-display text-7xl font-black leading-none tracking-tighter">
                  10%
                </div>
                <div className="font-mono-label text-[11px] tracking-[0.28em] text-[#F5F4F0]/85">
                  referral
                </div>
              </div>
              <div className="mt-3 max-w-[240px] font-display text-[14px] font-bold leading-snug">
                Paid when the job closes. Compounds every time you send someone
                good.
              </div>
              <Link
                to="/vas"
                className="mt-6 inline-flex items-center gap-2 rounded-sm bg-[#F5F4F0] px-4 py-2.5 text-[13px] font-bold"
                style={{ color: TERRA }}
              >
                Learn about the VP program{" "}
                <ArrowUpRight size={13} weight="bold" />
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Community Close ───────────────────────────────────────────── */}
      <section
        data-testid="section-community"
        className="border-b border-[#1C1A17]/12 bg-[#FBFAF6]"
      >
        <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10 md:py-24">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55 }}
            className="mx-auto max-w-4xl text-center"
          >
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#1C1A17]/55">
              07 · Baltimore, by us
            </div>
            <h2 className="font-display mt-4 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl md:text-6xl">
              By the community.
              <br />
              <span style={{ color: TERRA }}>For the community.</span>
            </h2>
            <p className="mx-auto mt-8 max-w-2xl text-[15px] leading-[1.75] text-[#1C1A17]/78 md:text-base">
              The HCOB Network is built in Baltimore, by people from here,
              putting money in the pockets of{" "}
              <span className="font-semibold text-[#1C1A17]">local specialists</span>{" "}
              instead of national platforms. When the network wins a project,
              local pros do the work and local pros get paid.
            </p>
            <p className="mx-auto mt-5 max-w-2xl text-[15px] leading-[1.75] text-[#1C1A17]/78 md:text-base">
              This is a community you grow with — as a specialist, as a
              professional, and as a name people in this network trust.
            </p>
          </motion.div>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <section
        data-testid="section-final-cta"
        style={{ backgroundColor: TERRA, color: BONE }}
      >
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 px-5 py-20 md:grid-cols-12 md:px-10 md:py-24">
          <div className="md:col-span-7">
            <div className="font-mono-label text-[10px] tracking-[0.28em] text-[#F5F4F0]/70">
              Ready when you are
            </div>
            <h2 className="font-display mt-3 text-4xl font-black leading-[1.02] tracking-tighter sm:text-5xl lg:text-6xl">
              Bring your skill.
              <br />
              We&rsquo;ll bring the work.
            </h2>
            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-[#F5F4F0]/85 md:text-base">
              Tell us your trade, your service area, and your availability. Our
              operations team reviews every application and reaches out to
              qualified pros directly.
            </p>
          </div>
          <div className="flex flex-col items-start justify-end gap-3 md:col-span-5 md:items-end">
            <button
              data-testid="bottom-cta-register"
              onClick={() => nav("/register")}
              className="inline-flex h-14 items-center gap-2 rounded-sm px-7 text-[14px] font-bold transition-transform hover:scale-[1.02]"
              style={{ backgroundColor: BONE, color: TERRA }}
            >
              Apply to Join the Network
              <ArrowRight size={16} weight="bold" />
            </button>
            <a
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
              A collaboration of local specialists in Baltimore &amp; all of
              Maryland — coordinated by one project management team.
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
              Mon–Sat · Operations team
            </div>
            <button
              onClick={() => nav("/register")}
              className="mt-5 inline-flex items-center gap-1 text-[13px] font-bold hover:opacity-75"
              style={{ color: TERRA }}
            >
              Apply to join <ArrowRight size={14} weight="bold" />
            </button>
          </div>

          <div className="md:col-span-4">
            <div className="font-mono-label mb-4 text-[10px] tracking-[0.28em] text-[#F5F4F0]/50">
              Also on the network
            </div>
            <div className="flex flex-col gap-3 text-[13px]">
              <a
                href="/"
                className="group inline-flex items-center gap-2 text-[#F5F4F0]/85 hover:text-[#F5F4F0]"
              >
                <span
                  className="inline-block h-[6px] w-4"
                  style={{ backgroundColor: TERRA }}
                />
                For customers — request a project
                <ArrowUpRight
                  size={12}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </a>
              <Link
                to="/vas"
                className="group inline-flex items-center gap-2 text-[#F5F4F0]/85 hover:text-[#F5F4F0]"
              >
                <span
                  className="inline-block h-[6px] w-4"
                  style={{ backgroundColor: TERRA }}
                />
                Refer leads · earn 10% commissions
                <ArrowUpRight
                  size={12}
                  weight="bold"
                  className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                />
              </Link>
              <a
                href="https://hcobcleaners.com"
                target="_blank"
                rel="noreferrer"
                className="group inline-flex items-center gap-2 text-[#F5F4F0]/85 hover:text-[#F5F4F0]"
              >
                <span
                  className="inline-block h-[6px] w-4"
                  style={{ backgroundColor: TERRA }}
                />
                HCOB Cleaners main site
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
              © {new Date().getFullYear()} HCOB Network · Founded by Cory Clarke
              · Baltimore, MD
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              <Link
                to="/login"
                data-testid="footer-login-link"
                className="hover:text-[#F5F4F0]"
              >
                Sign in
              </Link>
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
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
