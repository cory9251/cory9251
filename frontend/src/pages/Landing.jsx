import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { BACKEND_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  Lightning,
  ShieldCheck,
  CurrencyDollar,
  Clock,
  CheckCircle,
  MapPin,
  Buildings,
  Users,
  ChartLineUp,
  Quotes,
  IdentificationCard,
  Compass,
} from "@phosphor-icons/react";
import { TAG_CONFIG, getTagBorderClass, getOrderedTags } from "@/lib/gigTags";
import { formatGigShort } from "@/lib/gigDate";

// What the network does (positions HCOB as a project manager / coordinator
// — not a gig app). Each block is a service line we coordinate across our
// contractor network on behalf of a single customer.
const SERVICE_LINES = [
  {
    icon: Buildings,
    title: "Commercial cleaning programs",
    sub: "Multi-site routine + emergency response. We manage scope, staff, and QC.",
  },
  {
    icon: Users,
    title: "Project staffing & labor",
    sub: "Move-outs, post-construction, warehouse, event teardown — coordinated end-to-end.",
  },
  {
    icon: Compass,
    title: "Multi-service projects",
    sub: "When a customer needs cleaning + labor + driving in one project, we connect the dots.",
  },
  {
    icon: Lightning,
    title: "Same-day assignments",
    sub: "Rush work still happens — and the network gets first crack at it.",
  },
];

const WHY_JOIN = [
  {
    icon: Users,
    t: "You're on a team, not in a queue",
    d: "Network members get onboarded, briefed, and supported on every project. Not just an app notification.",
  },
  {
    icon: ChartLineUp,
    t: "Larger scope = larger checks",
    d: "Multi-day projects, recurring contracts, named roles. Same-day work is the floor, not the ceiling.",
  },
  {
    icon: ShieldCheck,
    t: "Real project management",
    d: "Cory and the ops team handle the customer, the scope, the schedule, and the disputes. You handle the work.",
  },
  {
    icon: CurrencyDollar,
    t: "Paid right after the work",
    d: "Direct payouts via Zelle, Apple Cash, or Chime — your call.",
  },
];

const MARQUEE = [
  "COMMERCIAL CLEANING",
  "POST-CONSTRUCTION",
  "MOVE-OUTS",
  "PROJECT STAFFING",
  "WAREHOUSE",
  "MULTI-SERVICE",
  "RUSH RESPONSE",
];

export default function Landing() {
  const nav = useNavigate();
  const [liveGigs, setLiveGigs] = useState([]);
  const [gigsLoading, setGigsLoading] = useState(true);

  useEffect(() => {
    const apiBase = BACKEND_URL;
    axios
      .get(`${apiBase}/api/public/gigs?limit=3`)
      .then((r) => setLiveGigs(r.data || []))
      .catch(() => setLiveGigs([]))
      .finally(() => setGigsLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-white text-[#030712]" data-testid="landing-page">
      {/* Top bar — contractor-focused (customer-facing CTA lives on /customers) */}
      <header className="border-b border-[#E5E7EB]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
              <Lightning weight="fill" size={18} />
            </div>
            <div>
              <div className="font-display text-xl font-black tracking-tight leading-none">
                HCOB Network
              </div>
              <div className="font-mono-label text-[9px]">
                Project management · Baltimore, MD
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              data-testid="nav-customers-link"
              href="/customers"
              className="hidden md:inline-flex items-center gap-1 px-3 py-2 text-sm font-semibold text-[#030712] hover:text-[#0044FF]"
            >
              Need a project done? <ArrowRight size={14} />
            </a>
            <Link
              data-testid="nav-vas-link"
              to="/vas"
              className="hidden md:inline-flex items-center gap-1 px-3 py-2 text-sm font-semibold text-[#030712] hover:text-[#0044FF]"
            >
              Refer leads · earn <ArrowRight size={14} />
            </Link>
            <Button
              data-testid="nav-login-btn"
              variant="ghost"
              className="rounded-none"
              onClick={() => nav("/login")}
            >
              Sign in
            </Button>
            <Button
              data-testid="nav-register-btn"
              className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              onClick={() => nav("/register")}
            >
              Apply to join <ArrowRight className="ml-1" size={16} />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero — repositioned: this is a contractor NETWORK, not a gig app */}
      <section className="border-b border-[#E5E7EB] bg-white">
        <div className="mx-auto grid max-w-7xl grid-cols-1 lg:grid-cols-12">
          <div className="lg:col-span-7 border-r-0 lg:border-r border-[#E5E7EB] px-6 py-16 lg:py-24">
            <div className="font-mono-label mb-6 flex items-center gap-2">
              <span className="grid h-5 w-5 place-items-center bg-[#0044FF] text-white text-[10px]">
                HCOB
              </span>
              For contractors in Baltimore, MD · Application required
            </div>
            <h1
              data-testid="hero-headline"
              className="font-display text-5xl sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter"
            >
              A structured team
              <br />
              for any scope.
              <br />
              <span className="text-[#0044FF]">Led by Cory Clarke.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base text-[#4B5563] leading-relaxed">
              HCOB Network isn&apos;t a gig app. It&apos;s a managed contractor
              network — where{" "}
              <strong className="text-[#030712]">vetted professionals</strong>{" "}
              get plugged into real projects, not just same-day work.
              We bring the customer, the scope, the schedule, and the
              accountability. You bring the work. Everyone gets paid.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Button
                data-testid="hero-cta-register"
                onClick={() => nav("/register")}
                className="h-12 rounded-none bg-[#030712] px-6 text-white hover:bg-[#1f2937]"
              >
                Apply to join the network <ArrowRight className="ml-2" size={18} />
              </Button>
              <Button
                data-testid="hero-cta-login"
                variant="outline"
                onClick={() => nav("/login")}
                className="h-12 rounded-none border-[#030712] px-6"
              >
                I&apos;m already in the network
              </Button>
            </div>

            <Link
              to="/vas"
              data-testid="hero-vas-callout"
              className="mt-5 inline-flex items-center gap-2 border-l-2 border-[#0044FF] bg-[#F0F4FF] px-4 py-2.5 text-xs font-semibold text-[#030712] hover:bg-[#E0E9FF]"
            >
              <CurrencyDollar size={14} weight="fill" className="text-[#0044FF]" />
              Prefer to refer customers instead of doing the work?
              <span className="text-[#0044FF]">Earn commissions via our VA program →</span>
            </Link>

            <div
              data-testid="hero-founder-credit"
              className="mt-10 flex items-start gap-3 border-l-2 border-[#030712] bg-[#F9FAFB] px-5 py-4"
            >
              <Quotes weight="fill" size={20} className="mt-0.5 text-[#0044FF] shrink-0" />
              <div>
                <div className="font-display text-sm font-bold leading-snug">
                  This is more than a side hustle. It&apos;s a structured
                  professional network.
                </div>
                <div className="mt-1 text-xs text-[#4B5563]">
                  — <strong className="text-[#030712]">Cory Clarke</strong>,
                  Owner · Founder · Project Manager
                </div>
              </div>
            </div>
          </div>

          {/* Right column — what we actually deliver */}
          <div className="lg:col-span-5 relative bg-[#F9FAFB] px-6 py-12 lg:py-20">
            <div className="font-mono-label mb-3">What the network delivers</div>
            <div className="space-y-3">
              {SERVICE_LINES.map((c) => (
                <div
                  key={c.title}
                  className="flex items-start gap-4 border border-[#E5E7EB] bg-white p-5"
                >
                  <div className="grid h-10 w-10 shrink-0 place-items-center bg-[#030712] text-white">
                    <c.icon size={20} weight="duotone" />
                  </div>
                  <div>
                    <div className="font-display text-base font-bold leading-tight">
                      {c.title}
                    </div>
                    <div className="mt-1 text-xs text-[#4B5563]">{c.sub}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Marquee — repositioned to multi-service capability, not gig categories */}
      <section className="overflow-hidden border-b border-[#E5E7EB] bg-[#030712] py-5">
        <div className="gb-marquee flex w-max gap-12 whitespace-nowrap font-display text-2xl font-black tracking-tight text-white">
          {[...MARQUEE, ...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i} className="flex items-center gap-12">
              {m}
              <span className="text-[#0044FF]">●</span>
            </span>
          ))}
        </div>
      </section>

      {/* Why join the network */}
      <section
        data-testid="why-join-section"
        className="border-b border-[#E5E7EB] bg-white"
      >
        <div className="mx-auto max-w-7xl px-6 py-16 lg:py-20">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="font-mono-label mb-2">Why contractors join</div>
              <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
                You&apos;re joining a team.
                <br />
                Not downloading another gig app.
              </h2>
            </div>
            <div className="max-w-md text-sm text-[#4B5563]">
              Most platforms treat workers as interchangeable. We don&apos;t.
              Network members get briefed, supported, and re-booked — because
              every project we run depends on people we trust.
            </div>
          </div>
          <div className="mt-10 grid grid-cols-1 gap-px bg-[#E5E7EB] sm:grid-cols-2 lg:grid-cols-4">
            {WHY_JOIN.map((b) => (
              <div
                key={b.t}
                className="bg-white p-6"
                data-testid={`why-join-${b.t.replace(/\s+/g, "-").toLowerCase()}`}
              >
                <div className="grid h-9 w-9 place-items-center bg-[#0044FF] text-white">
                  <b.icon size={18} weight="duotone" />
                </div>
                <div className="mt-4 font-display text-base font-bold leading-snug">
                  {b.t}
                </div>
                <div className="mt-2 text-xs text-[#4B5563] leading-relaxed">{b.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live assignments — kept, but reframed (network feed) */}
      <section data-testid="landing-live-gigs" className="border-b border-[#E5E7EB] bg-[#F9FAFB]">
        <div className="mx-auto max-w-7xl px-6 py-16 lg:py-20">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="font-mono-label mb-2 flex items-center gap-2">
                <span className="relative grid h-2 w-2 place-items-center">
                  <span className="absolute h-2 w-2 animate-ping rounded-full bg-[#10B981]" />
                  <span className="h-2 w-2 rounded-full bg-[#10B981]" />
                </span>
                Live · current assignments routed through the network
              </div>
              <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
                What the network is working on right now.
              </h2>
              <p className="mt-2 max-w-xl text-sm text-[#4B5563]">
                A snapshot of what&apos;s on the board this week. Network
                members see the full project — scope, customer, schedule, pay
                — once they sign in.
              </p>
            </div>
            <Button
              data-testid="live-gigs-cta-register"
              onClick={() => nav("/register")}
              className="h-11 rounded-none bg-[#030712] px-5 text-white hover:bg-[#1f2937]"
            >
              Apply to see them all <ArrowRight className="ml-2" size={16} />
            </Button>
          </div>

          <div className="mt-8">
            {gigsLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-44 animate-pulse border border-[#E5E7EB] bg-white"
                  />
                ))}
              </div>
            ) : liveGigs.length === 0 ? (
              <div
                data-testid="live-gigs-empty"
                className="flex flex-col items-start gap-3 border border-dashed border-[#E5E7EB] bg-white p-10 text-sm text-[#4B5563]"
              >
                <div className="font-display text-lg font-bold text-[#030712]">
                  Nothing in the public window at this exact moment.
                </div>
                <div>
                  We route new projects through the network all week.
                  Apply now so you&apos;re in the room when the next one lands.
                </div>
                <Button
                  data-testid="live-gigs-empty-cta"
                  onClick={() => nav("/register")}
                  className="mt-2 h-10 rounded-none bg-[#0044FF] px-5 text-white hover:bg-[#0036cc]"
                >
                  Apply to join <ArrowRight className="ml-2" size={16} />
                </Button>
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
                      onClick={() => nav(`/register?next=/crew/assignments/${g.gig_id}`)}
                      className={`group relative flex flex-col gap-3 bg-white p-5 text-left transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.18)] ${
                        tagBorder || "border border-[#E5E7EB]"
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
                            <span className="inline-flex items-center gap-1 rounded-full bg-[#030712] px-2.5 py-1 text-[9px] font-black tracking-[0.2em] text-white">
                              UPCOMING
                            </span>
                          )}
                        </div>
                      )}
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-mono-label flex items-center gap-1.5 text-[10px]">
                          {g.category} · {g.subcategory || "general"}
                        </div>
                        {slotsLeft > 0 && (
                          <span className="font-mono-label text-[9px] text-[#10B981]">
                            {slotsLeft} slot{slotsLeft === 1 ? "" : "s"} left
                          </span>
                        )}
                      </div>
                      <div className="font-display text-lg font-bold leading-snug">
                        {g.title}
                      </div>
                      <div className="mt-auto flex items-end justify-between gap-2 border-t border-[#E5E7EB] pt-3">
                        <div className="space-y-1 text-xs text-[#4B5563]">
                          <div className="flex items-center gap-1.5">
                            <MapPin size={12} weight="duotone" />
                            <span className="font-semibold text-[#030712]">
                              {g.location || "Baltimore area"}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Clock size={12} weight="duotone" />
                            <span>{formatGigShort(g)}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono-label text-[9px]">Pay</div>
                          <div className="font-display text-base font-black text-[#0044FF]">
                            ${Number(g.pay_rate).toFixed(0)}
                            {g.pay_type === "hourly" ? "/hr" : ""}
                          </div>
                        </div>
                      </div>
                      <div className="font-mono-label mt-1 text-[10px] text-[#0044FF] opacity-0 transition-opacity group-hover:opacity-100">
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

      {/* How joining works */}
      <section className="mx-auto max-w-7xl px-6 py-20" data-testid="how-it-works">
        <div className="font-mono-label mb-2">Joining the network</div>
        <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
          Three steps. We don&apos;t let anyone in we wouldn&apos;t send to a real customer.
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-0 md:grid-cols-3 border border-[#E5E7EB]">
          {[
            {
              n: "01",
              t: "Apply",
              icon: IdentificationCard,
              d: "Create your profile, upload a photo of your ID, tell us your skills and availability. Takes ~3 minutes.",
            },
            {
              n: "02",
              t: "Get vetted",
              icon: ShieldCheck,
              d: "Cory and the ops team review every applicant. Approved contractors are briefed on how the network runs.",
            },
            {
              n: "03",
              t: "Get assignments",
              icon: ChartLineUp,
              d: "Once you're in, projects route to your feed. Accept what fits — one-off or recurring, same-day or scheduled.",
            },
          ].map((s, i) => {
            const Icon = s.icon;
            return (
              <div
                key={s.n}
                className={`p-8 ${
                  i !== 2 ? "md:border-r border-[#E5E7EB]" : ""
                } ${i !== 0 ? "border-t md:border-t-0 border-[#E5E7EB]" : ""}`}
              >
                <div className="flex items-start justify-between">
                  <div className="font-display text-5xl font-black text-[#0044FF]">
                    {s.n}
                  </div>
                  <Icon size={32} weight="duotone" className="text-[#030712]" />
                </div>
                <div className="mt-6 font-display text-xl font-bold">{s.t}</div>
                <div className="mt-2 text-sm text-[#4B5563]">{s.d}</div>
              </div>
            );
          })}
        </div>

        <div className="mt-12 flex flex-col items-start gap-4 border border-[#030712] bg-[#030712] p-8 text-white sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-mono-label text-white/70">Ready when you are</div>
            <div className="mt-2 font-display text-2xl sm:text-3xl font-black">
              Apply to the HCOB Network today.
            </div>
          </div>
          <Button
            data-testid="bottom-cta-register"
            onClick={() => nav("/register")}
            className="h-12 rounded-none bg-[#0044FF] px-6 text-white hover:bg-[#0036cc]"
          >
            Apply to join <ArrowRight className="ml-2" size={18} />
          </Button>
        </div>

        <div className="mt-12 flex items-center gap-3 text-xs text-[#4B5563]">
          <CheckCircle size={16} weight="duotone" className="text-[#10B981]" />
          <span>Vetted contractors · Project management by Cory Clarke · Every assignment tracked in-app</span>
        </div>
      </section>

      <footer className="border-t border-[#E5E7EB] px-6 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="font-mono-label">
            © HCOB Network · Founded by Cory Clarke · Project management for{" "}
            <a
              href="https://hcobcleaners.com"
              target="_blank"
              rel="noreferrer"
              className="text-[#0044FF] hover:underline"
              data-testid="hcobcleaners-link"
            >
              hcobcleaners.com
            </a>{" "}
            + the broader network.
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-[#4B5563]">
            <Link to="/login">Sign in</Link>
            <Link to="/register">Apply to join</Link>
            <a href="/customers">For customers</a>
            <a href="https://hcobcleaners.com" target="_blank" rel="noreferrer">
              HCOB main site
            </a>
            <Link to="/privacy" data-testid="footer-privacy-link">Privacy</Link>
            <Link to="/terms" data-testid="footer-terms-link">Terms</Link>
            <Link to="/sms-terms" data-testid="footer-sms-terms-link">SMS Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
