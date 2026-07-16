# HCOB Network — Admin Training Manual

**Audience:** Admins, Program Managers, and the Owner
**Portal:** `/ops` (log in at `/login` with an admin account)
**Last updated:** June 2026

---

## 1. Getting Started

### 1.1 Logging in
1. Go to `/login` and enter your admin email and password (or use **Continue with Google** if your account was created that way).
2. You land on the **Dashboard** (`/ops`).
3. If you forget your password, use **Forgot password** on the login page. The Owner can also reset any user's password from their detail page.

### 1.2 Admin roles
| Role | What it adds |
|---|---|
| **Admin** | Full access to assignments, workers, blasts, reports, projects, and the VA program review tools. |
| **Program Manager (PM)** | An admin flagged as PM — primary reviewer of VA leads and commissions. |
| **Owner** | Everything above, plus: final commission sign-off, **Payouts** page, mark-paid, the **Blast Kill Switch**, and resetting any user's password. |

### 1.3 The sidebar
The left sidebar is organized into collapsible groups. Amber/blue count badges show items waiting for you:

- **Dashboard** and **Calendar** (always visible at top)
- **Work Pipeline** — Requests · Quotes · Assignments · AI Assignment · Projects
- **People** — Workers · Certifications · Trades · Referrals · Messages
- **Growth** — Blast · SMS Consent · Service Catalog · Announcements · Reports
- **Finance** — Bookkeeping · Worker Pay · Payouts (Owner only)
- **VA Program** — Overview · Applications · Lead Pipeline · Digital Services · Digital Jobs · Rates · Teams · Commissions · VA Accounts · Commercial
- **Settings**

### 1.4 The notification bell
The bell in the top bar shows in-app notifications (new requests, quote submissions, VA events, messages). Click any notification to jump straight to the relevant page.

---

## 2. Dashboard & Calendar

### 2.1 Dashboard (`/ops`)
Your daily command center:
- **KPI cards** — open assignments, pending requests, workers, and more.
- **Pending requests strip (yellow)** — "X requests waiting for your approval → REVIEW NOW" links to the Requests queue.
- **Available Now strip (green)** — "X workers are available right now" — perfect for filling RUSH assignments fast.

### 2.2 Calendar (`/ops/calendar`)
Three views (toggle top-right): **Month / Week / Day**.
- **Month** — heatmap-tinted grid (bluer = lighter day, redder = busier); each day shows pay/hours/slots mini-stats.
- **Week** — 7 columns with stacked assignment cards.
- **Day** — hour-by-hour timeline with KPIs and an "At a glance" roster panel.
- **Click an empty day** to create an assignment pre-set to that date. **Click a chip** to open the assignment.
- Times always show the wall-clock time you entered — no timezone drift for you or the workers.

---

## 3. Work Pipeline

### 3.1 Requests (`/ops/requests`)
The **global queue** of every pending worker request across all assignments, oldest first.
- **Approve** — reserves the slot, notifies the worker, and reveals the full address to them.
- **Reject** — removes the request and notifies the worker.
- Important: a request does **not** hold a slot. Multiple workers can request the same slot; you pick.

### 3.2 Quotes (`/ops/quotes`)
Customer quote requests submitted from the public site. Review details and follow up with the customer directly.

### 3.3 Assignments (`/ops/assignments`)
The full list of assignments (gigs), with sortable columns (Title, Category, When, Pay, Slots, Status, Blasts) and status filters.

**Creating an assignment** (the "+ New" button or from the Calendar):
- **Title, category, description** — descriptions support Markdown (bold, lists, links) with a Write/Preview editor.
- **Location vs. Address line** — `Location` (street + zip) is public; `Address line` is the sensitive full address, shown to a worker **only after you approve them**.
- **Date & time, slots, backup slots** — backups queue behind the main roster and auto-promote if someone cancels.
- **Pay** — hourly or flat rate; **Break (min)** deducts unpaid break time from hourly pay.
- **Payment timeline** — Same day / 2-3 days (default) / Weekly / Custom (with a note). Workers see this as a colored pill.
- **Recurring** — daily / weekly / biweekly / monthly, up to 52 occurrences, generated as a linked series.
- **Best-fit workers panel** — suggests workers whose trades/skills match the category as you type.
- **Templates** — start from a saved posting template to pre-fill everything.

**On the assignment detail page** you can:
- **Edit / Duplicate** the assignment.
- **Pin tags** — 🔥 RUSH · PRIORITY NEED · SAME DAY · TOP PAY. Any tag pins the card to the top of the worker feed with a colored border.
- **Blast** it (see §5.1) — blasting auto-sets the RUSH tag.
- **Review pending requests** — Approve / Approve as backup / Reject per row.
- **Add a worker** directly (skips the request step) or **Remove** someone (releases the slot, notifies them).
- **Roster & time tracking** — see clock-in/out per worker, edit timesheets, apply pay overrides, approve timesheets (workers only see earnings after approval).
- **Share link** — copies a link that unfurls with a branded preview card in iMessage/WhatsApp/Facebook.
- **Open gig group chat** — the per-assignment group thread with all approved workers.

### 3.4 AI Assignment (`/ops/ai-assignment`)
Describe the job in plain English and the AI drafts a complete assignment (title, description, category, pay suggestion) for you to review, tweak, and post.

### 3.5 Projects (`/ops/projects`)
A **Project** bundles related assignments that share one job site (e.g. driver + handyman + crew lead).
- Create a project with defaults (location, date, payment timeline, contact) that can sync into linked assignments.
- Link/unlink assignments from the project or the assignment page.
- See the combined crew across all linked assignments, keep an admin-only notes thread, and **blast the whole project** at once.
- Archiving a project unlinks its assignments but never deletes them.

---

## 4. People

### 4.1 Workers (`/ops/workers`)
Search and filter the roster: status tabs, skills, availability, zip, vehicle, profile completion, and the **Available Now** toggle (workers who flipped their green "available" pill get a pulsing badge).

**Worker detail page** (`/ops/workers/:id`) — everything about one worker:
- **Documents** — view and **Verify ID**, **Verify W-9**, **Verify signed agreement**. Workers cannot claim assignments until their ID is verified.
- **Account actions** — Approve / Reject / Suspend / Reinstate (reject and suspend kill their sessions immediately), reset password (temp password shown once), delete (cascades and releases their slots).
- **Profile override** — edit any profile field on the worker's behalf (skills, contact, status, email).
- **Pay defaults** — set the worker's default rate; per-assignment overrides are set on the assignment page.
- **Ratings & activity** — star ratings and their requested/approved/completed/no-show history.
- **Message worker** — one click opens a DM.

> Tip: Worker names are clickable **everywhere** in the admin portal (rosters, reports, queues) and open the worker's page in a new tab.

### 4.2 Certifications (`/ops/badges`)
Manage the professional certified badge catalog and award badges to workers. Badges show on worker profiles.

### 4.3 Trades (`/ops/trades`)
Manage the worker trade taxonomy (the categories/specialties workers pick at signup). This powers best-fit matching and specialist targeting.

### 4.4 Referrals (`/ops/referrals`)
The contractor referral program: track client referrals submitted by workers and manage their reward status.

### 4.5 Messages (`/ops/messages`)
Full inbox: DMs and per-assignment group chats.
- **Quick template chips** (Available? · ID reminder · Shift soon · Late · Thanks) auto-fill with the recipient's name.
- **Email / SMS companion toggles** — send a DM and simultaneously deliver it by email and/or text (DMs only, never group chats).
- Unread badge polls automatically; recipients also get an email digest if a message sits unread for 15+ minutes.

---

## 5. Growth

### 5.1 Blast (`/ops/email-blast`)
The unified mass-messaging composer — **Email and SMS in one send**.
1. Pick channels (Email / SMS / in-app) — you can send any combination.
2. Write the email subject/body and/or the SMS text. The SMS composer shows a **live character & segment counter** — stay under 160 GSM-7 characters for a single segment, and use plain hyphens (`-`), never em-dashes.
3. Or click **Start from template** to pre-fill both email and SMS bodies.
4. Send. In-app notifications go instantly; email/SMS deliver in the background — the toast confirms "queued".

**SMS compliance is automatic:** the "Reply STOP to opt out" footer is appended server-side, and texts only go to workers who opted in.

**Safety systems (built-in, always on):**
- **Cooldown** — re-blasting the same assignment/project within 5 minutes is blocked (429 "wait Xs").
- **Deduplication** — duplicate emails/phones are collapsed before sending; a retried blast never re-mails an address.
- **Kill Switch** — the Owner can disable ALL blasts platform-wide from Settings in one click (see §8).
- **Blast audit** — every send is logged with counts, failures, and sender name (see Reports → Blasts).

### 5.2 SMS Consent (`/ops/sms-consent`)
The compliance audit log: who opted in to texts, when, and from where (profile toggle, feed nudge, admin). **Export to CSV** for carrier/Twilio audits. Workers self-manage opt-in from their profile.

### 5.3 Service Catalog (`/ops/services`)
Manage the VA service catalog — the digital services (and rates) that VAs can be hired for.

### 5.4 Announcements (`/ops/announcements`)
Post platform-wide announcements that appear in worker portals.

### 5.5 Reports (`/ops/reports`)
Every report supports date filters, **CSV download**, and **Google Sheets export**:
- **Timesheets** — per-worker clock-in/out, break minutes, paid hours, earnings; approve state included.
- **Earnings / Payroll** — one row per worker with totals.
- **Workers / Roster** — full roster export with an optional PII toggle.
- **Gigs** — assignments with fill rates and payout per assignment.
- **Activity** — requested / approved / completed / no-shows per worker.
- **Blasts** — every blast ever sent: channels, targets, delivered, failed, sender.

---

## 6. Finance

### 6.1 Bookkeeping (`/ops/bookkeeping`)
Ledger view of platform money movement — payroll logs and commission entries.

### 6.2 Worker Pay (`/ops/worker-pay`)
Central pay administration: default rates, per-assignment overrides, and payout review.

**The timesheet approval flow (important):**
1. Worker clocks in/out on their phone → hours computed automatically (breaks deducted for hourly pay).
2. You review on the assignment page — edit clock times or break override if needed.
3. **Approve timesheet** → only then does the worker see their earnings.

### 6.3 Payouts (`/ops/payouts`) — Owner only
The final gate for VA commission payouts:
- Queue of PM-approved commissions awaiting sign-off.
- **Approve** individually or **bulk-approve** per VA per week.
- **Mark paid** (records method + reference). A paid commission is frozen — double-payment is blocked at the database layer.

---

## 7. VA Program

The VA program lets Virtual Assistants submit cleaning-lead prospects and earn commissions through a controlled review chain: **VA submits → PM reviews → Owner signs off → paid**.

| Page | What you do there |
|---|---|
| **VA Overview** | Program KPIs + "Open detailed analytics →" (velocity chart, per-VA conversion funnel, stuck-lead leak report). |
| **Applications** | Approve or reject new VA signups. Pending VAs cannot submit leads. |
| **Lead Pipeline** | Kanban of all leads through 7 stages (New → Contacted → Quoted → Booked → Paid → Completed/Lost). Advance stages, edit any lead, soft-delete to Trash (restorable), full audit trail per lead. |
| **Digital Services / Digital Jobs** | Manage the VA digital-services catalog and job postings. |
| **Rates** | Commission rate configuration. Defaults: routine $10, recurring V1 $15 / V2 $25 / V3-6 $10 (cap $100/client), deep/move-out/specialty $25 flat, commercial 5% of monthly revenue. |
| **Teams** | 2-level VA team structure with leader override commissions. |
| **Commissions** | PM review queue — Approve / Flag (note required) / Reject each commission. |
| **VA Accounts** | Manage VA users: approve, suspend (kills sessions), remove. |
| **Commercial** | Recurring commercial accounts earning 5% monthly commission. |

**Built-in fraud safeguards** (automatic, logged as violations): duplicate-lead blocking (same phone/email), self-referral blocking (prospect address matches the VA's own), ownership timestamp locks, and the double-payment freeze.

**Commission lifecycle:** Lead reaches *Booked* → commission created → lead reaches *Paid* (with job value) → enters the PM queue → PM approves → Owner signs off → Owner marks paid → VA is notified.

---

## 8. Settings (`/ops/settings`)

- **Email (Resend) & SMS (Twilio) credentials** — enter/update API keys; secrets are masked after saving (only the last 4 characters show). Status cards flip between **READY / NOT CONFIGURED** so you always know which blast channels will actually deliver. Use the **Test** button to dry-run a real email or SMS.
- **Blast Kill Switch (Owner)** — the big red "Disable all blasts" button. When ON, every blast attempt platform-wide returns an error and any in-flight background sends stop. Shows who toggled it and when. Use it the moment anything looks wrong with outbound messaging.
- **Change password** — self-service for your own account.
- **Admin users** — add admins, set read-only roles, promote/demote (Owner controls).

---

## 9. Common Workflows (Cheat Sheet)

### Post and fill an assignment
1. **Assignments → + New** (or click a calendar day). Fill in details, set slots + backups, pick payment timeline. Save.
2. **Blast it** from the assignment page (this pins it as RUSH) or add pin tags manually.
3. Watch **Requests** — approve the workers you want, reject the rest. Approved workers see the full address and can clock in.
4. After the job: review clock-in/out, edit if needed, **Approve timesheet** → worker sees earnings.

### Onboard a new worker
1. Worker registers, completes the trade questionnaire, uploads ID (+ W-9 and signed agreement from their profile).
2. Open their page from **Workers** → verify ID, verify W-9, verify agreement.
3. Once ID-verified, they can request assignments. Set their default pay under Pay defaults if it differs from standard.

### Send a text + email campaign
1. **Growth → Blast**. Toggle Email and SMS on.
2. Start from a template or write fresh — keep SMS ≤ 160 characters, one segment.
3. Send. Check **Reports → Blasts** later for delivered/failed counts.

### Pay a VA commission (Owner)
1. PM approves the commission in **VA Program → Commissions**.
2. Owner opens **Finance → Payouts**, signs off (or bulk-approves), then **Mark paid** with method + reference.

### Emergency: stop all outbound messages
**Settings → Blast Kill Switch → Disable all blasts.** Effective immediately, platform-wide, reversible with one click.

---

## 10. Quick Reference

| I need to... | Go to |
|---|---|
| Approve worker requests | Work Pipeline → **Requests** |
| Create/edit an assignment | Work Pipeline → **Assignments** |
| Draft an assignment with AI | Work Pipeline → **AI Assignment** |
| Verify an ID / W-9 / agreement | People → **Workers** → worker page |
| Text or email everyone | Growth → **Blast** |
| Check who opted in to SMS | Growth → **SMS Consent** |
| Run payroll | Growth → **Reports** → Earnings / Timesheets |
| Approve VA commissions | VA Program → **Commissions** |
| Pay out commissions (Owner) | Finance → **Payouts** |
| Stop all blasts NOW (Owner) | **Settings** → Blast Kill Switch |
| Update email/SMS API keys | **Settings** |
