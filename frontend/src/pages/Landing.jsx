import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkle, Lightning, Broom, Wrench, Car, ShieldCheck } from "@phosphor-icons/react";

const categories = [
  {
    icon: Broom,
    title: "Cleaning",
    sub: "Deep · Routine · Move-outs · Specialty",
  },
  { icon: Wrench, title: "Labor", sub: "Hourly · On-site · Project work" },
  { icon: Car, title: "Driver / Ride", sub: "Worker transport · Logistics" },
];

const marquee = ["DEEP CLEAN", "MOVE-OUT", "HOURLY LABOR", "DRIVER", "SPECIALTY", "ROUTINE", "RIDE-SHARE"];

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
            <div className="font-display text-xl font-black tracking-tight">GigBlast</div>
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
              Get Started <ArrowRight className="ml-1" size={16} />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-[#E5E7EB]">
        <div className="mx-auto grid max-w-7xl grid-cols-1 lg:grid-cols-12">
          <div className="lg:col-span-7 border-r-0 lg:border-r border-[#E5E7EB] px-6 py-16 lg:py-24">
            <div className="font-mono-label mb-6">
              Operations · Workforce · Dispatch
            </div>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-black leading-[0.95] tracking-tighter">
              Blast every gig.
              <br />
              Fill every slot.
            </h1>
            <p className="mt-6 max-w-xl text-base text-[#4B5563] leading-relaxed">
              The operator-grade platform to manage your cleaning, labor, and
              driver gigs — and notify your crew in seconds across in-app,
              email, and SMS.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Button
                data-testid="hero-cta-register"
                onClick={() => nav("/register")}
                className="h-12 rounded-none bg-[#030712] px-6 text-white hover:bg-[#1f2937]"
              >
                Create an account <ArrowRight className="ml-2" size={18} />
              </Button>
              <Button
                data-testid="hero-cta-login"
                variant="outline"
                onClick={() => nav("/login")}
                className="h-12 rounded-none border-[#030712] px-6"
              >
                I already have an account
              </Button>
            </div>
            <div className="mt-12 flex items-center gap-3 text-xs text-[#4B5563]">
              <ShieldCheck size={16} weight="duotone" />
              <span>Verified IDs · Track acceptances · Audit blasts</span>
            </div>
          </div>
          <div className="lg:col-span-5 relative bg-[#F9FAFB] px-6 py-12 lg:py-20">
            <div className="font-mono-label mb-3">Categories you can dispatch</div>
            <div className="space-y-4">
              {categories.map((c) => (
                <div
                  key={c.title}
                  className="flex items-center justify-between border border-[#E5E7EB] bg-white p-5"
                >
                  <div className="flex items-center gap-4">
                    <div className="grid h-10 w-10 place-items-center bg-[#030712] text-white">
                      <c.icon size={20} weight="duotone" />
                    </div>
                    <div>
                      <div className="font-display text-lg font-bold">{c.title}</div>
                      <div className="text-xs text-[#4B5563]">{c.sub}</div>
                    </div>
                  </div>
                  <Sparkle size={18} className="text-[#0044FF]" weight="fill" />
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
          Three steps. Workers in the field.
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-0 md:grid-cols-3 border border-[#E5E7EB]">
          {[
            {
              n: "01",
              t: "Build your roster",
              d: "Workers register, upload an ID, and complete a profile.",
            },
            {
              n: "02",
              t: "Post a gig",
              d: "Cleaning, labor, or driver — set pay, slots, and timing.",
            },
            {
              n: "03",
              t: "Blast it out",
              d: "Push to in-app, email, SMS — track who accepts in real time.",
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
      </section>

      <footer className="border-t border-[#E5E7EB] px-6 py-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="font-mono-label">© GigBlast Operations</div>
          <div className="flex gap-6 text-xs text-[#4B5563]">
            <Link to="/login">Sign in</Link>
            <Link to="/register">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
