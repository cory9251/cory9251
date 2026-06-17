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
} from "@phosphor-icons/react";

/**
 * VA Training playbook — hard-coded markdown content aligned with the
 * HCOB VA Role + Scripts + Marketing Outlets PDFs. Edit by deploying.
 * DB-backed version is a future enhancement.
 */
export default function VATraining() {
  return (
    <div className="p-6 md:p-10 max-w-4xl" data-testid="va-training">
      <div className="mb-8">
        <div className="font-mono-label">VA Portal · Playbook</div>
        <h1 className="font-display text-4xl font-black tracking-tight flex items-center gap-3">
          <BookOpenText size={32} weight="duotone" /> Training & Playbook
        </h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Everything you need to know to crush this role. Bookmark this page — review
          it on Day 1, then every Monday before you start outreach.
        </p>
      </div>

      {/* ---- The 5 required fields ------------------------------------------ */}
      <Section
        icon={CheckCircle}
        title="The 5 required fields"
        subtitle="Collect these on every qualified prospect. No submission = no commission."
        accent="border-[#030712] bg-[#FEF3C7]"
        testid="section-required-fields"
      >
        <ol className="grid grid-cols-1 gap-1 font-mono text-sm sm:grid-cols-2">
          <li>1. Full name</li>
          <li>2. Phone number</li>
          <li>3. Service type</li>
          <li>4. Property size</li>
          <li>5. Preferred date / timeframe</li>
        </ol>
        <p className="mt-3 text-xs text-[#92400E]">
          The form is your commission. The form is your commission. The form is your commission.
        </p>
      </Section>

      {/* ---- Month 1 Brand Ambassador rules -------------------------------- */}
      <Section
        icon={WarningCircle}
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

      {/* ---- Do / Do Not ---------------------------------------------------- */}
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
            <li>Submit every qualified lead <strong>immediately</strong> through the intake form</li>
            <li>Follow up with non-responders (up to 2 follow-ups per prospect)</li>
            <li>Prioritize commercial prospecting — 5% revenue commission lifetime</li>
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
            <li>Contact the Owner directly about day-to-day matters</li>
            <li>Contact cleaners or field contractors</li>
            <li>Hold leads — submit them immediately</li>
            <li>Submit a lead without all 5 fields</li>
            <li>Quote prices, confirm dates, or promise availability</li>
            <li>Try to close, schedule, or handle customer service / disputes</li>
            <li>Direct other VAs (no management responsibilities)</li>
            <li>Bulk-message the same copy to 50 strangers</li>
          </ul>
        </Section>
      </div>

      {/* ---- Commission tier structure ------------------------------------- */}
      <Section
        icon={Trophy}
        title="Commission tier structure"
        subtitle="Hourly rate unlocks with cumulative lead submissions + Week 1 completion."
        testid="section-tiers"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <TierCard
            tier="Tier 0"
            title="Starting state"
            criteria="0–14 leads submitted"
            hourly="No hourly"
            commission="Commission only (per rate schedule)"
          />
          <TierCard
            tier="Tier 1"
            title="Week 1 + 15 leads"
            criteria="Week 1 complete + 15 cumulative leads"
            hourly="$1.50 / hour"
            commission="Commission per rate schedule"
            accent="border-[#0044FF]"
          />
          <TierCard
            tier="Tier 2"
            title="30 leads"
            criteria="30 cumulative submitted leads"
            hourly="$2.50 / hour"
            commission="Commission per rate schedule"
            accent="border-[#10B981]"
          />
        </div>
        <p className="mt-4 text-xs text-[#4B5563]">
          Commission is earned when a job <strong>originated by you</strong> is both <em>completed</em> by the
          field team <strong>and</strong> <em>paid in full</em> by the client. Commercial accounts pay <strong>5% of monthly
          collected revenue</strong> for the lifetime of the account.
        </p>
      </Section>

      {/* ---- Daily closing checklist --------------------------------------- */}
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

      {/* ---- Marketing outlets summary ------------------------------------- */}
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

      {/* ---- Quick links ---------------------------------------------------- */}
      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <QuickLink
          to="/va/templates"
          icon={GraduationCap}
          label="Pitch templates"
          sub="80+ ready-to-copy scripts"
        />
        <QuickLink
          to="/va/submit"
          icon={Target}
          label="Submit a lead"
          sub="The 5 required fields"
        />
        <QuickLink
          to="/va/leaderboard"
          icon={Trophy}
          label="Leaderboard"
          sub="See where you rank"
        />
      </div>
    </div>
  );
}

function Section({ icon: Icon, title, subtitle, accent, compact, testid, children }) {
  return (
    <section
      data-testid={testid}
      className={`mb-6 border ${accent || "border-[#E5E7EB] bg-white"} p-5`}
    >
      <div className="flex items-start gap-2">
        <Icon size={18} weight="duotone" className="mt-0.5 shrink-0" />
        <div className="flex-1">
          <h2 className={`font-display ${compact ? "text-lg" : "text-2xl"} font-black`}>
            {title}
          </h2>
          {subtitle && <p className="mt-1 text-xs text-[#4B5563]">{subtitle}</p>}
        </div>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TierCard({ tier, title, criteria, hourly, commission, accent }) {
  return (
    <div className={`border ${accent || "border-[#E5E7EB]"} bg-white p-4`}>
      <div className="font-mono-label">{tier}</div>
      <div className="mt-1 font-display text-lg font-black">{title}</div>
      <div className="mt-1 text-xs text-[#4B5563]">{criteria}</div>
      <div className="mt-3 text-sm font-bold">{hourly}</div>
      <div className="text-xs text-[#4B5563]">{commission}</div>
    </div>
  );
}

function QuickLink({ to, icon: Icon, label, sub }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 border border-[#E5E7EB] bg-white p-4 hover:border-[#030712]"
    >
      <Icon size={24} weight="duotone" />
      <div>
        <div className="font-bold">{label}</div>
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
