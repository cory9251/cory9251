import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  Lightning,
  Broom,
  Wrench,
  Car,
  ShieldCheck,
  CurrencyDollar,
  Clock,
  CheckCircle,
} from "@phosphor-icons/react";

const work = [
  {
    icon: Broom,
    title: "Cleaning gigs",
    sub: "Deep cleans · Routine · Move-outs · Specialty",
    pay: "$22–35/hr",
  },
  {
    icon: Wrench,
    title: "Labor gigs",
    sub: "Hourly · On-site · Moving · Warehouse",
    pay: "$20–28/hr",
  },
  {
    icon: Car,
    title: "Driver / Rides",
    sub: "Worker transport · Local runs · Crew shuttles",
    pay: "$18–25/hr",
  },
];

const benefits = [
  { icon: Clock, t: "Flexible schedule", d: "Pick the gigs that fit your week." },
  { icon: CurrencyDollar, t: "Get paid fast", d: "Direct payouts after each completed gig." },
  { icon: ShieldCheck, t: "Verified work", d: "Every job is dispatched directly by HCOB." },
];

const marquee = [
  "DEEP CLEAN",
  "MOVE-OUT",
  "HOURLY LABOR",
  "DRIVER",
  "SPECIALTY",
  "ROUTINE",
  "CREW SHUTTLE",
];

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-white text-[#030712]" data-testid="landing-page">
      {/* Top bar */}
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
                The gig network for hcobcleaners.com
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
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
              Join the crew <ArrowRight className="ml-1" size={16} />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-[#E5E7EB]">
        <div className="mx-auto grid max-w-7xl grid-cols-1 lg:grid-cols-12">
          <div className="lg:col-span-7 border-r-0 lg:border-r border-[#E5E7EB] px-6 py-16 lg:py-24">
            <div className="font-mono-label mb-6">
              For HCOB workers · Apply once, get gigs forever
            </div>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter">
              Find gigs from
              <br />
              HCOB Cleaners.
            </h1>
            <p className="mt-6 max-w-xl text-base text-[#4B5563] leading-relaxed">
              HCOB Network is where the HCOB Cleaners crew picks up work. Cleaning,
              labor, and driver gigs — posted by HCOB, claimed by you. Build a
              profile once, then accept jobs in the app whenever they hit your feed.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Button
                data-testid="hero-cta-register"
                onClick={() => nav("/register")}
                className="h-12 rounded-none bg-[#030712] px-6 text-white hover:bg-[#1f2937]"
              >
                Join the crew <ArrowRight className="ml-2" size={18} />
              </Button>
              <Button
                data-testid="hero-cta-login"
                variant="outline"
                onClick={() => nav("/login")}
                className="h-12 rounded-none border-[#030712] px-6"
              >
                I'm already on the crew
              </Button>
            </div>
            <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {benefits.map((b) => (
                <div key={b.t} className="flex items-start gap-3 text-xs">
                  <div className="grid h-7 w-7 shrink-0 place-items-center bg-[#0044FF] text-white">
                    <b.icon size={14} weight="duotone" />
                  </div>
                  <div>
                    <div className="font-display text-sm font-bold">{b.t}</div>
                    <div className="text-[#4B5563]">{b.d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-5 relative bg-[#F9FAFB] px-6 py-12 lg:py-20">
            <div className="font-mono-label mb-3">Work we dispatch</div>
            <div className="space-y-4">
              {work.map((c) => (
                <div
                  key={c.title}
                  className="flex items-start justify-between gap-3 border border-[#E5E7EB] bg-white p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="grid h-10 w-10 shrink-0 place-items-center bg-[#030712] text-white">
                      <c.icon size={20} weight="duotone" />
                    </div>
                    <div>
                      <div className="font-display text-lg font-bold leading-tight">
                        {c.title}
                      </div>
                      <div className="mt-1 text-xs text-[#4B5563]">{c.sub}</div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-mono-label text-[9px]">Typical</div>
                    <div className="font-display text-sm font-bold text-[#0044FF]">
                      {c.pay}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Marquee */}
      <section className="overflow-hidden border-b border-[#E5E7EB] bg-[#030712] py-5">
        <div className="gb-marquee flex w-max gap-12 whitespace-nowrap font-display text-2xl font-black tracking-tight text-white">
          {[...marquee, ...marquee, ...marquee].map((m, i) => (
            <span key={i} className="flex items-center gap-12">
              {m}
              <span className="text-[#0044FF]">●</span>
            </span>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="font-mono-label mb-2">How it works</div>
        <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
          Three steps to your next gig.
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-0 md:grid-cols-3 border border-[#E5E7EB]">
          {[
            {
              n: "01",
              t: "Sign up",
              d: "Create a worker profile and upload a photo of your ID. Takes 2 minutes.",
            },
            {
              n: "02",
              t: "Watch your feed",
              d: "When HCOB posts a gig, you'll see it in-app — and get an email or text if you want.",
            },
            {
              n: "03",
              t: "Tap accept",
              d: "Claim a slot in one tap. Show up, get the work done, get paid.",
            },
          ].map((s, i) => (
            <div
              key={s.n}
              className={`p-8 ${
                i !== 2 ? "md:border-r border-[#E5E7EB]" : ""
              } ${i !== 0 ? "border-t md:border-t-0 border-[#E5E7EB]" : ""}`}
            >
              <div className="font-display text-5xl font-black text-[#0044FF]">{s.n}</div>
              <div className="mt-6 font-display text-xl font-bold">{s.t}</div>
              <div className="mt-2 text-sm text-[#4B5563]">{s.d}</div>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-start gap-4 border border-[#030712] bg-[#030712] p-8 text-white sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-mono-label text-white/70">Ready when you are</div>
            <div className="mt-2 font-display text-2xl sm:text-3xl font-black">
              Start picking up HCOB gigs today.
            </div>
          </div>
          <Button
            data-testid="bottom-cta-register"
            onClick={() => nav("/register")}
            className="h-12 rounded-none bg-[#0044FF] px-6 text-white hover:bg-[#0036cc]"
          >
            Join the crew <ArrowRight className="ml-2" size={18} />
          </Button>
        </div>

        <div className="mt-12 flex items-center gap-3 text-xs text-[#4B5563]">
          <CheckCircle size={16} weight="duotone" className="text-[#10B981]" />
          <span>Verified IDs · Direct dispatch from HCOB · Track every gig in app</span>
        </div>
      </section>

      <footer className="border-t border-[#E5E7EB] px-6 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="font-mono-label">
            © HCOB Network · A service for{" "}
            <a
              href="https://hcobcleaners.com"
              target="_blank"
              rel="noreferrer"
              className="text-[#0044FF] hover:underline"
              data-testid="hcobcleaners-link"
            >
              hcobcleaners.com
            </a>
          </div>
          <div className="flex gap-6 text-xs text-[#4B5563]">
            <Link to="/login">Sign in</Link>
            <Link to="/register">Join the crew</Link>
            <a href="https://hcobcleaners.com" target="_blank" rel="noreferrer">
              HCOB main site
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
