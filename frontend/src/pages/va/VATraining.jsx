import React from "react";
import { Link } from "react-router-dom";
import {
  BookOpenText,
  CheckCircle,
  XCircle,
  Target,
  ListChecks,
  GraduationCap,
  Megaphone,
  WarningCircle,
  Trophy,
  Coins,
  UsersThree,
  Laptop,
  Handshake,
  Info,
  Prohibit,
  ChatCircleText,
  Question,
} from "@phosphor-icons/react";

/**
 * VA Training & Playbook — aligned with Fixed Pool Model v2.0
 * (HCOB_Commission_Structure_v2) and the VP Recruiting landing page.
 * Content is intentionally hard-coded here for easy editorial control;
 * a DB-backed CMS is a future enhancement.
 */
export default function VATraining() {
  return (
    <div className="p-6 md:p-10 max-w-4xl" data-testid="va-training">
      {/* ---- Hero ---------------------------------------------------------- */}
      <div className="mb-10">
        <div className="font-mono-label">VP Portal · Playbook</div>
        <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight flex items-center gap-3 leading-tight">
          <BookOpenText size={36} weight="duotone" /> Training &amp; Playbook
        </h1>
        <p className="mt-3 text-base text-[#374151] max-w-2xl">
          Everything you need to earn on the HCOB Network. Read it end-to-end on Day 1,
          revisit it every Monday, and share it with your team lead if anything feels unclear.
        </p>
        <div className="mt-4 inline-flex items-start gap-2 border border-[#E5E7EB] bg-[#F9FAFB] px-4 py-2 text-xs text-[#4B5563]">
          <Info size={14} weight="duotone" className="mt-0.5 shrink-0" />
          <span>
            <strong>No income level is guaranteed.</strong> Earnings depend entirely on the leads you close
            and the jobs you complete. This is independent contractor work — not salaried employment.
          </span>
        </div>
      </div>

      {/* ---- 3 Golden Rules (NEW) ----------------------------------------- */}
      <Section
        icon={WarningCircle}
        title="The 3 Golden Rules"
        subtitle="Break one of these and you lose the commission. Read them twice."
        accent="border-[#DC2626] bg-gradient-to-br from-[#FEF2F2] to-white"
        testid="section-golden-rules"
      >
        <div className="grid grid-cols-1 gap-3">
          <GoldenRule
            n="1"
            title="Leads that don't answer, don't count."
            body="If we can't reach the prospect after your handoff, the lead is dead. Confirm they're expecting our call, get the best time to reach them, and set the right expectation in your outreach. A phone number with a silent voicemail earns you $0."
          />
          <GoldenRule
            n="2"
            title="Miscategorized leads may void your commission."
            body="Category determines the pool. Submitting a Deep Clean as a Routine, or a Commercial as a residential, misprices the job and can wipe your payout entirely. If you're not sure, ASK before you submit."
          />
          <GoldenRule
            n="3"
            title="Be as detailed as possible — detail converts."
            body="Booked jobs pay you. Vague leads don't book. Every extra note (square footage, pets, access instructions, urgency, competitor quotes, why they're switching) increases the odds we close them — and increases the pool base you're earning off."
          />
        </div>
      </Section>

      {/* ---- Three earning streams (NEW) ---------------------------------- */}
      <Section
        icon={Handshake}
        title="Three ways to earn on the network"
        subtitle="Pick one, pick all three. Every stream feeds the same weekly payout."
        testid="section-streams"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <StreamCard
            icon={Coins}
            label="Commission Agent"
            body="Refer real leads for cleaning, trades, or commercial. You get 75% of the pool when the job closes and pays. This is the bread and butter."
          />
          <StreamCard
            icon={Laptop}
            label="Virtual Gig Work"
            body="Do the work yourself — content, admin, design, scheduling, marketing tasks posted to the VP Jobs board. Fixed price or hourly. Approved by admin then paid weekly."
            to="/va/jobs"
            cta="Open the Jobs board →"
          />
          <StreamCard
            icon={UsersThree}
            label="Team Lead Path"
            body="Reach Senior tier + strong monthly production, and you can lead a small team of your own. Team leads earn additional commission on top of their own work — mentor, coach, and get rewarded for it."
          />
        </div>
      </Section>

      {/* ---- The 5 required fields ---------------------------------------- */}
      <Section
        icon={CheckCircle}
        title="The 5 required fields — with detail tips"
        subtitle="Collect these on every qualified prospect. No submission = no commission."
        accent="border-[#030712] bg-[#FEF3C7]"
        testid="section-required-fields"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldTip
            n="1"
            label="Full name"
            tip="First AND last. First-name-only leads often don't answer — see Golden Rule #1."
          />
          <FieldTip
            n="2"
            label="Phone number"
            tip="Confirm it's their cell. Ask 'best time to reach you?' and put it in the notes."
          />
          <FieldTip
            n="3"
            label="Service type + category"
            tip="Routine, Deep, Move-out, Handyman, Commercial, etc. See the category rates below. If unsure — ASK before you submit (Rule #2)."
          />
          <FieldTip
            n="4"
            label="Property size"
            tip="Bedrooms + baths + approximate square footage. For commercial: sqft + occupancy type."
          />
          <FieldTip
            n="5"
            label="Preferred date / timeframe"
            tip="'ASAP', 'this Friday', 'next month' all work — as long as it's real. Include urgency signals: 'moving out Nov 30', 'inspection Tuesday'."
          />
        </div>
        <div className="mt-4 border-t border-[#F59E0B]/40 pt-3 text-xs text-[#92400E]">
          <strong>Bonus context that boosts conversion (put in notes):</strong> pets, allergies, access
          instructions, key/lockbox, gate code, why they&apos;re switching providers, competitor quote they got,
          budget range, decision-maker vs occupant, best contact method.
        </div>
      </Section>

      {/* ---- Fixed Pool Model (simplified) -------------------------------- */}
      <Section
        icon={Coins}
        title="How you get paid"
        subtitle="Every closed job creates a commission — the more you close, the more you earn."
        testid="section-pool"
      >
        <p className="text-sm text-[#374151] leading-relaxed">
          When a job closes and the client pays, HCOB calculates your commission using two things:
          the <strong>category</strong> of the job and your current <strong>agent tier</strong>. The
          exact percentages are laid out in the rate table below — see them any time on your{" "}
          <Link to="/va" className="font-bold text-[#0044FF] underline decoration-dotted">Dashboard</Link>
          {" "}and{" "}
          <Link to="/va/earnings" className="font-bold text-[#0044FF] underline decoration-dotted">Earnings page</Link>.
        </p>
        <div className="mt-4 border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-xs text-[#4B5563]">
          <strong className="text-[#030712]">Pool base:</strong>{" "}
          <span className="font-mono">Categories A–D and F</span> use <em>job profit</em>.{" "}
          <span className="font-mono">Categories E and G</span> use <em>monthly collected revenue</em>{" "}
          (paid every month the account or retainer is active).
        </div>
      </Section>

      {/* ---- Your Team Lead (mentorship framing) -------------------------- */}
      <Section
        icon={UsersThree}
        title="Your team lead — your mentor on the network"
        subtitle="Nobody wins alone. Your upline is here to help you level up."
        accent="border-[#0044FF] bg-[#EFF6FF]"
        testid="section-team-lead"
      >
        <p className="text-sm text-[#374151] leading-relaxed">
          Every VP on the HCOB Network is placed under a team lead — a senior teammate who is
          personally committed to seeing you succeed. Your team lead is <strong>not a boss</strong>.
          They&apos;re a mentor, a strategist, and your go-to when things get hard.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
          <div className="border border-[#E5E7EB] bg-white p-3">
            <div className="font-mono-label text-[#0044FF]">WHAT YOUR TEAM LEAD DOES</div>
            <ul className="mt-1 list-disc pl-5 space-y-1">
              <li>Keeps you motivated when the pipeline feels slow</li>
              <li>Reviews your outreach and helps you sharpen your pitch</li>
              <li>Guides you through category decisions so you don&apos;t miscategorize</li>
              <li>Shares what&apos;s working for them — templates, scripts, DM openers</li>
              <li>Aligns you with the network so you grow faster</li>
            </ul>
          </div>
          <div className="border border-[#E5E7EB] bg-white p-3">
            <div className="font-mono-label text-[#10B981]">WHAT YOU GAIN</div>
            <ul className="mt-1 list-disc pl-5 space-y-1">
              <li>A powerful, transferable skill — lead generation &amp; digital sales</li>
              <li>Real-time coaching from someone already earning on the network</li>
              <li>Faster tier progression (Agent → Senior → Elite)</li>
              <li>A support system that celebrates your wins</li>
              <li>A clear path toward becoming a team lead yourself</li>
            </ul>
          </div>
        </div>
        <p className="mt-3 text-xs text-[#4B5563] italic">
          This is not just a gig — it&apos;s an opportunity to learn a skill you can use for the
          rest of your career, with a mentor at your disposal from day one.
        </p>
      </Section>

      {/* ---- Agent tiers -------------------------------------------------- */}
      <Section
        icon={Trophy}
        title="Agent tiers — your rate goes up as you close more"
        subtitle="Tier is set by cumulative paid leads. Tiers never move backward."
        testid="section-tiers"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <TierCard
            tier="AGENT"
            title="Starting tier"
            criteria="0–24 paid leads"
            example="Category A · 10%  ·  Cat B/C/F · 12%"
          />
          <TierCard
            tier="SENIOR"
            title="Unlocked at 25 paid"
            criteria="25–59 cumulative paid leads"
            example="Category A · 12.5%  ·  Cat B/C/F · 15%"
            accent="border-[#0044FF]"
          />
          <TierCard
            tier="ELITE"
            title="Unlocked at 60 paid"
            criteria="60+ cumulative paid leads"
            example="Category A · 15%  ·  Cat B/C/F · 18%"
            accent="border-[#10B981]"
          />
        </div>
        <p className="mt-4 text-xs text-[#4B5563]">
          A lead counts toward your tier the moment Ownership marks the commission{" "}
          <strong>PAID</strong>. Refunds, chargebacks, and voided commissions do not count.
        </p>
      </Section>

      {/* ---- Category rate table ------------------------------------------ */}
      <Section
        icon={ListChecks}
        title="Category rate table"
        subtitle="Your rate depends on the category AND your current tier."
        testid="section-categories"
      >
        <div className="overflow-x-auto border border-[#E5E7EB] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#F9FAFB] font-mono-label text-xs">
              <tr>
                <th className="p-2 text-left">Cat</th>
                <th className="p-2 text-left">Type</th>
                <th className="p-2 text-left">Base</th>
                <th className="p-2 text-right">Agent</th>
                <th className="p-2 text-right">Senior</th>
                <th className="p-2 text-right">Elite</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              <CatRow cat="A" type="Standard Cleaning (routine)" base="Job profit" a="10%" s="12.5%" e="15%" />
              <CatRow cat="B" type="Premium Cleans (deep / move-out / specialty)" base="Job profit" a="12%" s="15%" e="18%" />
              <CatRow cat="C" type="Trades &amp; Projects (handyman, painting, junk, pressure, landscaping)" base="Job profit" a="12%" s="15%" e="18%" />
              <CatRow cat="D" type="Recurring Accounts (visit 1–3 / 4–12 / 13+)" base="Job profit each visit" a="15% / 10% / 5%" s="15% / 10% / 5%" e="15% / 10% / 5%" muted />
              <CatRow cat="E" type="Commercial Accounts" base="Monthly revenue" a="5%" s="5%" e="5%" muted />
              <CatRow cat="F" type="Virtual Projects (one-time)" base="Job profit" a="12%" s="15%" e="18%" />
              <CatRow cat="G" type="Virtual Retainers (recurring)" base="Monthly revenue" a="5%" s="5%" e="5%" muted />
            </tbody>
          </table>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-[#4B5563] sm:grid-cols-2">
          <div className="border border-[#E5E7EB] bg-white p-2">
            <strong>Category D tail:</strong> pays every visit indefinitely — unless the client goes
            inactive for 90+ days, then the chain ends permanently.
          </div>
          <div className="border border-[#E5E7EB] bg-white p-2">
            <strong>Categories E &amp; G:</strong> pay every month the account is active, for the
            lifetime of the account. No caps.
          </div>
        </div>
      </Section>

      {/* ---- Month 1 Brand Ambassador rules (KEPT) ------------------------ */}
      <Section
        icon={Prohibit}
        title="Month 1 — Brand Ambassador rules"
        subtitle="Strict for the first 30 days. Violations = withheld commissions."
        accent="border-[#DC2626] bg-[#FEF2F2]"
        testid="section-brand-rules"
      >
        <p className="text-sm">During your first full calendar month you must <strong>NEVER</strong>:</p>
        <ul className="mt-2 list-disc pl-5 text-sm space-y-1">
          <li>Mention the company name in any outreach</li>
          <li>Share the company phone number, website, or any social handle</li>
          <li>Use the company logo, photos, or any brand asset</li>
          <li>Create a Facebook page, Instagram, or business listing using brand assets</li>
        </ul>
        <p className="mt-3 text-sm">Instead, position yourself as:</p>
        <blockquote className="mt-1 border-l-4 border-[#0044FF] bg-white p-3 text-sm italic">
          &ldquo;I coordinate for a local Maryland property services team.&rdquo;
        </blockquote>
        <p className="mt-3 text-xs uppercase tracking-widest text-[#DC2626]">
          You are a scheduling coordinator — nothing more, nothing less.
        </p>
      </Section>

      {/* ---- Do / Do Not (updated) ---------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Section
          icon={CheckCircle}
          title="Do"
          accent="border-[#10B981] bg-[#F0FDF4]"
          compact
          testid="section-do"
        >
          <ul className="list-disc pl-5 text-sm space-y-1">
            <li>Send <strong>20–30 outreach messages/day</strong> across your platforms</li>
            <li>Maintain <strong>5–10 active conversations</strong> at all times</li>
            <li>Personalize every opening message — never copy-paste</li>
            <li>Qualify prospects naturally — collect all 5 fields conversationally</li>
            <li><strong>Confirm the prospect will answer</strong> before you submit (Rule #1)</li>
            <li><strong>Pick the right category</strong> or ASK first (Rule #2)</li>
            <li><strong>Over-share detail in the notes</strong> — every line boosts conversion (Rule #3)</li>
            <li>Submit every qualified lead <strong>immediately</strong> through the intake form</li>
            <li>Follow up with non-responders (up to 2 follow-ups per prospect)</li>
            <li>Prioritize commercial + recurring — those pay you every month forever</li>
            <li>Participate in your weekly check-in with Mechie</li>
          </ul>
        </Section>
        <Section
          icon={XCircle}
          title="Do NOT"
          accent="border-[#DC2626] bg-[#FEF2F2]"
          compact
          testid="section-donot"
        >
          <ul className="list-disc pl-5 text-sm space-y-1">
            <li>Submit unresponsive contacts to inflate your lead count — they void</li>
            <li>Guess the category — miscategorization can wipe the entire commission</li>
            <li>Submit vague notes (&ldquo;wants a clean&rdquo;) — vague leads don&apos;t book</li>
            <li>Contact the Owner directly about day-to-day matters</li>
            <li>Contact cleaners or field contractors</li>
            <li>Hold leads — submit them immediately</li>
            <li>Submit a lead without all 5 fields</li>
            <li>Quote prices, confirm dates, or promise availability</li>
            <li>Try to close, schedule, or handle customer service / disputes</li>
            <li>Direct other VPs (no management responsibilities unless you&apos;re a Team Lead)</li>
            <li>Bulk-message the same copy to 50 strangers</li>
          </ul>
        </Section>
      </div>

      {/* ---- Daily closing checklist (updated) ---------------------------- */}
      <Section
        icon={ListChecks}
        title="Daily closing checklist"
        subtitle="Run through this before you log off every day."
        testid="section-checklist"
      >
        <ul className="space-y-2 text-sm">
          {[
            "Did I send at least 20–30 outreach messages across my platforms today?",
            "Do I have at least 5–10 active conversations going?",
            "Did I collect all 5 required fields on every qualified prospect?",
            "Did I confirm each prospect will actually answer their phone?",
            "Did I pick the right category for every submitted lead? (asked if unsure)",
            "Did I write detailed notes on every lead — not just the minimum?",
            "Did I submit every qualified lead through the intake form?",
            "Did I avoid mentioning the company name, phone, website, or any brand assets?",
            "Did I avoid discussing pricing, timelines, or service guarantees?",
            "Did I follow up with any prospects who went quiet in the last 24–48 hours?",
          ].map((q, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle size={14} weight="duotone" className="mt-0.5 shrink-0 text-[#10B981]" />
              <span>{q}</span>
            </li>
          ))}
        </ul>
      </Section>

      {/* ---- Virtual Gig Work (NEW) --------------------------------------- */}
      <Section
        icon={Laptop}
        title="Virtual Gig Work — do the work, get paid"
        subtitle="Not every VP wants to prospect. Some prefer to do tasks. Both earn."
        accent="border-[#0044FF] bg-[#EFF6FF]"
        testid="section-virtual-work"
      >
        <p className="text-sm">
          The <Link to="/va/jobs" className="font-bold text-[#0044FF] underline decoration-dotted">VP Jobs board</Link>{" "}
          posts one-off and recurring digital tasks — content writing, graphic design,
          scheduling, social outreach, CRM cleanup, spreadsheet work, and more. Every job
          shows the payout up front (fixed or hourly rate).
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
          <div className="border border-[#E5E7EB] bg-white p-3">
            <div className="font-mono-label text-[#10B981]">HOW IT WORKS</div>
            <ol className="mt-1 list-decimal pl-5 space-y-1">
              <li>Browse open jobs on the board</li>
              <li>Tap Claim → the job locks to you</li>
              <li>Tap Start when you begin</li>
              <li>Deliver the work + tap Submit (add note, hours if hourly)</li>
              <li>Admin reviews → Approve → payout enters the weekly queue</li>
            </ol>
          </div>
          <div className="border border-[#E5E7EB] bg-white p-3">
            <div className="font-mono-label text-[#DC2626]">DO NOT</div>
            <ul className="mt-1 list-disc pl-5 space-y-1">
              <li>Claim more jobs than you can finish this week</li>
              <li>Submit incomplete deliverables to &ldquo;test&rdquo; if we&apos;ll pay</li>
              <li>Log hourly time on a fixed-price job</li>
              <li>Deliver work outside the platform (loses the paper trail — voids payout)</li>
              <li>Ghost after claiming — admin can reassign the job</li>
            </ul>
          </div>
        </div>
        <div className="mt-3 text-xs text-[#4B5563]">
          Virtual Gig payouts flow through the same weekly commission queue as leads — so both
          streams show up on your <Link to="/va/earnings" className="underline">Earnings page</Link>.
        </div>
      </Section>

      {/* ---- Marketing outlets (kept) ------------------------------------- */}
      <Section
        icon={Megaphone}
        title="Marketing outlets — where to find leads"
        subtitle="Each platform has rules. Break them and you'll get banned."
        testid="section-outlets"
      >
        <div className="space-y-3 text-sm">
          {OUTLETS.map((o) => (
            <details key={o.name} className="border border-[#E5E7EB] bg-white p-3">
              <summary className="cursor-pointer font-bold">{o.name} · <span className="font-normal text-xs text-[#4B5563]">{o.category}</span></summary>
              <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <div className="font-mono-label text-[#10B981]">DO</div>
                  <ul className="mt-1 list-disc pl-5 text-xs space-y-0.5">
                    {o.do.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
                <div>
                  <div className="font-mono-label text-[#DC2626]">DO NOT</div>
                  <ul className="mt-1 list-disc pl-5 text-xs space-y-0.5">
                    {o.dont.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
              </div>
            </details>
          ))}
        </div>
      </Section>

      {/* ---- Common questions --------------------------------------------- */}
      <Section
        icon={Question}
        title="Common questions"
        subtitle="If your question isn't here, DM Mechie in the messenger."
        testid="section-faq"
      >
        <div className="space-y-2 text-sm">
          <FAQ
            q="When do I actually get paid?"
            a="Weekly. Every Friday the Owner signs off on the approved commission queue, and payouts go out via your chosen method (Zelle, PayPal, Cash App, ACH). You'll see the exact status on your Earnings page."
          />
          <FAQ
            q="How do I know what tier I'm on right now?"
            a="Your VP Dashboard shows your current tier + how many paid leads to the next tier. It's live — every time a commission moves to PAID, your count updates."
          />
          <FAQ
            q="What happens if a prospect books but then cancels?"
            a="If the job was already marked Paid before the refund, the commission may be reversed. If it hadn't been paid yet, it moves to Rejected. Either way, it does NOT count toward your tier."
          />
          <FAQ
            q="Can I refer other VPs to the network?"
            a="Yes — via the VP Recruiting landing page. Once you hit Senior tier and maintain steady production, you can unlock the Team Lead track, mentor your own recruits, and earn additional commission on the work they close."
          />
          <FAQ
            q="I'm not sure if my lead is Category A, B, or C. What do I do?"
            a="ASK. Post in the messenger, tag Mechie, and wait for confirmation before submitting. Miscategorization can void the commission (Golden Rule #2)."
          />
        </div>
      </Section>

      {/* ---- Quick links --------------------------------------------------- */}
      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-4">
        <QuickLink to="/va/templates" icon={GraduationCap} label="Pitch templates" sub="80+ ready-to-copy scripts" />
        <QuickLink to="/va/submit" icon={Target} label="Submit a lead" sub="The 5 required fields" />
        <QuickLink to="/va/jobs" icon={Laptop} label="Jobs board" sub="Virtual gig work" />
        <QuickLink to="/va/earnings" icon={Coins} label="My earnings" sub="Tier + payouts" />
      </div>
    </div>
  );
}

/* ---------------- Reusable presentational bits ---------------- */

function Section({ icon: Icon, title, subtitle, accent, compact, testid, children }) {
  return (
    <section
      data-testid={testid}
      className={`mb-8 border ${accent || "border-[#E5E7EB] bg-white"} p-5 md:p-6`}
    >
      <div className="flex items-start gap-2">
        <Icon size={20} weight="duotone" className="mt-0.5 shrink-0" />
        <div className="flex-1">
          <h2 className={`font-display ${compact ? "text-lg" : "text-2xl"} font-black leading-tight`}>
            {title}
          </h2>
          {subtitle && <p className="mt-1 text-sm text-[#4B5563]">{subtitle}</p>}
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function GoldenRule({ n, title, body }) {
  return (
    <div className="flex items-start gap-3 border border-[#DC2626]/30 bg-white p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-[#DC2626] font-display text-lg font-black text-white">
        {n}
      </div>
      <div>
        <div className="font-display text-base font-black text-[#030712]">{title}</div>
        <p className="mt-1 text-sm text-[#374151] leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

function StreamCard({ icon: Icon, label, body, to, cta }) {
  return (
    <div className="border border-[#E5E7EB] bg-white p-4">
      <Icon size={22} weight="duotone" />
      <div className="mt-2 font-display text-lg font-black">{label}</div>
      <p className="mt-1 text-sm text-[#4B5563] leading-relaxed">{body}</p>
      {to && cta && (
        <Link to={to} className="mt-3 inline-block text-xs font-bold text-[#0044FF] underline decoration-dotted">
          {cta}
        </Link>
      )}
    </div>
  );
}

function FieldTip({ n, label, tip }) {
  return (
    <div className="flex items-start gap-2 border border-[#F59E0B]/30 bg-white p-3">
      <div className="font-mono text-xs font-bold text-[#92400E]">{n}.</div>
      <div>
        <div className="font-bold text-sm">{label}</div>
        <p className="mt-0.5 text-xs text-[#4B5563] leading-relaxed">{tip}</p>
      </div>
    </div>
  );
}

function TierCard({ tier, title, criteria, example, accent }) {
  return (
    <div className={`border ${accent || "border-[#E5E7EB]"} bg-white p-4`}>
      <div className="font-mono-label">{tier}</div>
      <div className="mt-1 font-display text-lg font-black">{title}</div>
      <div className="mt-1 text-xs text-[#4B5563]">{criteria}</div>
      <div className="mt-3 border-t border-[#F3F4F6] pt-2 font-mono text-xs text-[#030712]">{example}</div>
    </div>
  );
}

function CatRow({ cat, type, base, a, s, e, muted }) {
  return (
    <tr className={muted ? "bg-[#FAFAFA]" : ""}>
      <td className="p-2 font-mono font-bold">{cat}</td>
      <td className="p-2">{type}</td>
      <td className="p-2 text-xs text-[#4B5563]">{base}</td>
      <td className="p-2 text-right font-mono">{a}</td>
      <td className="p-2 text-right font-mono">{s}</td>
      <td className="p-2 text-right font-mono">{e}</td>
    </tr>
  );
}

function FAQ({ q, a }) {
  return (
    <details className="border border-[#E5E7EB] bg-white p-3">
      <summary className="cursor-pointer font-bold text-sm flex items-start gap-2">
        <ChatCircleText size={14} weight="duotone" className="mt-0.5 shrink-0 text-[#0044FF]" />
        <span>{q}</span>
      </summary>
      <p className="mt-2 pl-6 text-sm text-[#4B5563] leading-relaxed">{a}</p>
    </details>
  );
}

function QuickLink({ to, icon: Icon, label, sub }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 border border-[#E5E7EB] bg-white p-4 hover:border-[#030712] transition-colors"
    >
      <Icon size={22} weight="duotone" />
      <div>
        <div className="font-bold text-sm">{label}</div>
        <div className="text-xs text-[#4B5563]">{sub}</div>
      </div>
    </Link>
  );
}

const OUTLETS = [
  {
    name: "Facebook",
    category: "Groups · Marketplace · Profile",
    do: [
      "Use all four surfaces: Groups, Pages, Marketplace, Personal Profile",
      "Read group rules before posting — respond only where someone is asking",
      "One post per group per week max",
      "Personalize every DM",
      "Post value before you pitch (engage, then introduce service)",
    ],
    dont: [
      "Post solicitations in groups that ban them",
      "Send the same copy-paste DM to 50 people at once",
      "Create duplicate Marketplace listings to game search",
      "Create a Page using company brand assets",
      "Continue messaging someone who said no",
    ],
  },
  {
    name: "LinkedIn",
    category: "Professional networking — commercial focus",
    do: [
      "Personalize every connection request with a specific note",
      "Reference their role / company / industry",
      "Keep opening messages 2–3 sentences",
      "Build one exchange before pitching",
      "Target Property Mgmt, Real Estate, Facilities, Healthcare, Legal, Construction",
    ],
    dont: [
      "Pitch immediately after a connection accepts",
      "Send more than 20–25 connection requests/day (account limit)",
      "Post promotions in groups that prohibit it",
      "Export contact data outside the platform",
      "Misrepresent your role",
    ],
  },
  {
    name: "Craigslist",
    category: "Classifieds",
    do: [
      "Post one listing per service category",
      "Write honest, clear descriptions",
      "Refresh listings every 48h (per Craigslist rules)",
      "Respond to Wanted ads the same day",
      "Personalize every reply",
    ],
    dont: [
      "Post duplicate listings to flood search results",
      "Use stock photos / unlicensed images",
      "Make inflated claims or fake guarantees",
      "Copy-paste replies",
      "Post in unrelated categories",
    ],
  },
  {
    name: "Nextdoor",
    category: "Local social network",
    do: [
      "Use your real, verified account",
      "Respond to recommendation requests promptly",
      "Conversational tone — neighborly, never salesy",
      "Reference their specific post when replying",
      "DM only neighbors who showed clear interest",
    ],
    dont: [
      "Create fake neighbor accounts",
      "Post the same message in multiple neighborhoods",
      "Cold DM strangers",
      "Post promotionally more than once a week per neighborhood",
      "Use hard sales / pressure tactics",
    ],
  },
  {
    name: "Reddit",
    category: "Online forums",
    do: [
      "Build account history first — engage on unrelated topics",
      "Respond only to direct service-request threads",
      "Read every subreddit's sidebar rules",
      "Be helpful, community-first",
      "Target r/baltimore, r/HomeImprovement, r/Landlord, r/moving etc.",
    ],
    dont: [
      "Post service ads with zero prior account history",
      "Promote in subreddits that ban self-promo",
      "Create multiple accounts to upvote yourself",
      "Ignore moderator warnings",
      "Cross-post the same message simultaneously",
    ],
  },
  {
    name: "Yelp / Thumbtack / Angi / HomeAdvisor",
    category: "Listing & service marketplaces",
    do: [
      "List services accurately and honestly",
      "Respond to every inquiry within a few hours",
      "Keep listing descriptions consistent across platforms",
      "Follow each platform's quoting guidelines",
      "Encourage genuinely satisfied clients to leave reviews",
    ],
    dont: [
      "Fabricate or solicit fake reviews (FTC violation)",
      "List services the team does not perform",
      "Include company brand assets during Month 1",
      "Create duplicate listings on the same platform",
      "Delay or ignore inquiries",
    ],
  },
  {
    name: "Google Business / Maps",
    category: "Search & maps outreach",
    do: [
      "Search by service type + location (e.g. 'dental office Towson MD')",
      "Cross-reference LinkedIn for decision-maker names",
      "Be honest about how you found them",
      "Contact during stated business hours only",
      "One call + one voicemail, then one email follow-up",
    ],
    dont: [
      "Call businesses repeatedly",
      "Misrepresent yourself as a referral or prior client",
      "Mass-contact every business in a zip code",
      "Use Google data to build external databases",
      "Contact businesses in industries the team doesn't serve",
    ],
  },
  {
    name: "Cold Email",
    category: "Commercial only — CAN-SPAM compliant",
    do: [
      "COMMERCIAL prospecting only — never residential",
      "Use honest, accurate subject lines",
      "Clearly identify yourself",
      "Include a clear opt-out option",
      "Honor opt-out requests within 10 business days",
      "Keep first emails 3–4 sentences max",
      "Max 2 total emails per unresponsive prospect",
    ],
    dont: [
      "Cold email residential / personal addresses",
      "Purchase or use scraped email lists",
      "Use deceptive subject lines",
      "Send bulk emails via automation",
      "Send from fake / disguised sender addresses",
      "Email anyone who said no",
      "Violate CAN-SPAM (fines up to $51,744 PER email)",
    ],
  },
];
