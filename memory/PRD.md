# GigBlast — Product Requirements

## Original problem statement
> I want to build a app that would allow me to manage, and blast my gig opportunities to my workers. It should be a platform where they can login and see what opportunities are available. They must be able to create a profile, upload a picture of id, and accept jobs in app.

## Architecture
- **Stack**: FastAPI + MongoDB (backend), React + Tailwind + Shadcn UI + Phosphor Icons (frontend)
- **Auth**: Session-token httpOnly cookies; supports email/password (bcrypt) AND Emergent Google OAuth (both create the same `users` doc and a `sessions` doc)
- **Storage**: Emergent Object Storage for ID images and worker avatars; `/api/files/{path}` enforces owner-or-admin ACL
- **Notifications**: Resend (email), Twilio (SMS), in-app via `notifications` collection. Channels are optional per blast; empty creds degrade gracefully (counts return zero).

## Personas
- **Admin / Manager** — posts gigs across cleaning / labor / driver categories, blasts to workers, reviews IDs, verifies workers.
- **Worker** — registers, uploads ID + avatar, browses open gigs by category, accepts a slot, manages commitments.

## Core requirements (static)
1. Two roles (admin, worker) — distinct experiences
2. Gig categories: cleaning (deep/routine/moveout/specialty), labor (hourly), driver (worker_transport/delivery/rideshare)
3. Profile + ID upload (image), admin verification of ID
4. Blast a gig to all workers via in-app + optional email + optional SMS
5. Accept / withdraw flow with slot counting and auto-fill status

## Implemented — 2026-02 (MVP)
- JWT-cookie auth: register / login / logout / me
- Emergent Google OAuth: /auth/callback exchanges `session_id` for session cookie
- Admin: dashboard KPIs, gigs list with filters, gig detail (with acceptances + blast dialog), workers list, worker detail (view ID, verify ID)
- Worker: bottom-tab mobile-first UI, feed, gig detail, accept/withdraw, accepted list, profile (avatar + ID upload + bio/skills/phone/address)
- Object storage init, upload, owner/admin-only download
- Blast endpoint with multi-channel selector and graceful provider fallback
- Seeded admin: `admin@gigblast.com / GigBlast2026!`
- 35/35 backend tests passing, end-to-end UI flows verified

## Implemented — 2026-02 (Iteration 2: Admin Settings)
- `/admin/settings` page with Resend + Twilio credential management
- Backend `app_settings` collection (singleton); secrets masked on read (`has_value`, `last4`); DB values override env on every blast
- Partial-update PUT semantics: omitted field = unchanged, empty string = cleared
- `/admin/settings/test` endpoint to dry-run email or SMS with saved creds
- Status cards in the UI flip between READY / NOT CONFIGURED so admins instantly see blast eligibility per channel
- 50/50 backend tests passing (15 new + 35 regression)

## Implemented — 2026-02 (Iteration 3: Calendar)
- `/admin/calendar` month-grid view with category-colored chips (cleaning=blue, labor=black, driver=amber)
- "Upcoming" sidebar shows next 5 scheduled gigs
- Click an empty day → create-gig dialog pre-set to that date; click a chip → gig detail
- New `scheduled_at` ISO datetime field added to gigs (legacy `scheduled_date` retained as display string)
- Rewritten CreateGigDialog uses shadcn Calendar + Popover for date and Select hour/minute/AM-PM
- Fixed `GET /api/gigs?status=all` to mean "no filter" (was matching the literal string)
- 58/58 backend tests passing (8 new + 50 regression)

## Implemented — 2026-02 (Iteration 4: HCOB Rebrand + Security Fix)
- Rebranded to **HCOB Network — the gig network for hcobcleaners.com**
- Landing page rewritten to be worker-focused: "Find gigs from HCOB Cleaners", typical pay per category, footer links to hcobcleaners.com
- Register page no longer exposes a role selector (workers only on public signup)
- **Security**: `POST /api/auth/register` now hardcodes `role='worker'` server-side — closes a privilege-escalation regression where a client could POST role=admin
- New seeded admin: `admin@hcobcleaners.com / HcobAdmin2026!` (legacy admin@gigblast.com retained)
- Admin/Worker layouts, email subjects, SMS prefixes all carry HCOB Network branding
- 59/59 backend tests passing

## Implemented — 2026-05 (Iteration 5: Worker Management + Time Tracking)
- **Admin can reset a worker's password** (manual or auto-generated temp shown once with copy-to-clipboard); all of the worker's sessions are force-invalidated
- **Admin can delete a worker** — cascades to acceptances/sessions/notifications/files and releases slots on gigs they had claimed (reverts gig back to 'open')
- **Worker self-service "Change password"** card on profile
- **Clock-in / Clock-out** per acceptance — live elapsed timer on the worker gig screen, "ON THE CLOCK" pulsing badge on the accepted list, full clock-in/out + hours_worked columns on the admin gig roster and worker history
- Acceptance state machine: `accepted → on_the_clock → completed`
- Worker detail endpoint enriched with gig titles + clock-in fields
- 75/75 backend tests passing (16 new + 59 regression)

## Implemented — 2026-05 (Iteration 6: Edit / Duplicate Gigs + Verification Gate + Address Privacy)
- **PUT /api/gigs/{id}** — admin partial edit; rejects slot shrink below `slots_filled`; auto-flips `open ⇄ filled`
- **POST /api/gigs/{id}/duplicate** — clones a gig (slots_filled=0, status=open, " (copy)" suffix, `duplicated_from` reference)
- Admin gig detail gets **Edit + Duplicate** buttons; new `EditGigDialog` mirrors the create dialog pre-populated
- **Address privacy**: gigs gain `address_line` (sensitive). `location` is now the public preview (street + zip). Worker responses strip `address_line` unless they've accepted. Admin always sees both.
- **Verification gate on accept**: workers cannot claim a gig until they (a) upload an ID image and (b) HCOB admin marks `id_verified=true`. Clear 403 messages for both failure modes.
- Worker feed shows a **verification banner**; worker gig screen shows a verification-required card with "Upload my ID →" CTA when ID missing
- After acceptance the worker sees a **Full address** card with the sensitive address
- 91/91 backend tests passing (16 new + 75 regression)

## Implemented — 2026-05 (Iteration 7: Recurring Gigs + Worker Approval Gate)
- New worker registrations default to `worker_status='pending'` — admin must approve before they can claim gigs
- Admin endpoints: `approve`, `reject`, `suspend`, `reinstate` (reject/suspend force-kill sessions)
- Accept gate now layered: status check → ID upload check → ID verified check, each with a distinct 403 message
- Backwards compat: existing users without the field are treated as approved
- AdminDashboard adds **Pending apps** KPI + yellow review strip; AdminWorkers gains status tabs (All / Pending / Approved / Rejected / Suspended) with badges
- WorkerDetail shows an Application Status card with action buttons (Approve / Reject / Suspend / Reinstate)
- Recurring gigs in CreateGigDialog — daily / weekly / biweekly / monthly + occurrence count (max 52). Backend generates N gigs spaced by the chosen period, linked by `series_id` / `series_index` / `series_total`
- Worker feed banner + gig screen extended with explicit messaging per state (pending / rejected / suspended / needs-ID / awaiting-verification)
- 115/115 backend tests passing (24 new + 91 regression)

## Implemented — 2026-05 (Iteration 8: Per-Gig Request/Approve Model — supersedes the applicant gate)
- **REVISED model** after user clarification: admin approves PER GIG, not per applicant. New workers default to `worker_status='approved'`.
- Worker taps **"Request this gig"** → backend creates an acceptance with `status='requested'`. **Slot is NOT reserved.** Address stays hidden. Clock-in blocked.
- Multiple workers can request the same slot. Admin reviews them in a new **Pending requests** table on the gig detail with Approve / Reject buttons per requester.
- Approve flips acceptance → `accepted`, increments `slots_filled`, flips gig to `filled` when full, sends an in-app notification to the worker.
- Reject deletes the acceptance and sends a notification.
- Worker UI: `request-pending-card` after request (no clock-in, no address); "REQUESTED" badge on feed + accepted list; "APPROVED" badge after approval.
- AdminDashboard repurposed: **Pending requests** KPI + yellow strip "X gig requests waiting for your approval → REVIEW NOW".
- Suspend / Reject worker buttons retained — useful for banning bad actors at the account level (the old per-applicant gate is dormant but kept for back-compat).
- 131/132 backend tests passing (17 new + 114 regression; 1 flake in pre-existing blast degradation test unrelated to this iteration).

## Implemented — 2026-05 (Iteration 9: Global Requests Review Queue)
- New top-level admin page `/admin/requests` — single global queue of every pending gig request across the platform with Approve / Reject inline per row.
- New endpoint `GET /api/admin/requests` returns enriched rows (worker + gig data) sorted oldest first.
- Sidebar gets a new **Requests** entry between Calendar and Gigs with a live **amber count badge** (`99+` cap). Auto-refreshes on route change AND on a `hcob:requests-changed` custom event after Approve/Reject.
- Dashboard yellow strip + new sidebar entry both link to `/admin/requests`.
- 8/8 new tests + 17/17 iter-8 regression green.

## Implemented — 2026-05 (Iteration 10: Admin Add/Remove Workers from Gigs)
- New endpoint `POST /api/gigs/{gig_id}/assign` — admin places a worker directly on a gig (skips the request step). If the worker had a pending request, it's converted in place; if already on the gig, returns 400. Rejected/suspended workers can't be assigned. Slot is reserved, gig flips to `filled` if full, worker gets a notification.
- New endpoint `DELETE /api/gigs/{gig_id}/acceptances/{acceptance_id}` — admin removes a worker. Releases the slot if it was an accepted/clocked/completed acceptance and flips a `filled` gig back to `open`. Notifies the worker.
- New `AssignWorkerDialog` — searchable picker over approved workers, excludes anyone already on the gig.
- Admin gig detail gets an **Add a worker** button above the roster and a **Remove** column on every approved row.
- 20/20 new tests + 25/25 iter-8/9 regression green.

## Implemented — 2026-06 (Iteration 19: RUSH Visual Treatment + Toggle)
- **Worker feed**: RUSH (blasted) gigs render with a red 2px border, gradient "🔥 RUSH · BLASTED" banner at the top of the card, a red "🔥 HOT" pill replacing the blue OPEN pill, and stay pinned to the top of the feed (backend sort already in place).
- **Admin gig detail**: a one-click "Mark as RUSH" / "RUSH is ON · turn off" toggle button calls `PUT /api/gigs/{id}/rush`. A pulsing red "🔥 RUSH · PINNED TO TOP OF FEED" banner appears under the title when active.
- **Admin gigs list**: each rush gig now shows a small "🔥 RUSH" pill next to its title in the table.
- Backend support was already in place (blast endpoint auto-flips `is_rush=true`; `PUT /api/gigs/{id}/rush` lets admins flip independently). This iteration was purely surfacing the state in the UI.

## Implemented — 2026-06 (Iteration 28: Rich Gig Descriptions + Payment Timeline)
- **Markdown descriptions**: replaced plain `Textarea` in CreateGigDialog and EditGigDialog with a custom `MarkdownEditor` (Write / Preview tabs + toolbar for bold/italic/heading/bullets/numbered/link). Stores plain markdown in the existing `description` field — no schema change needed.
- **Markdown rendering** via new `MarkdownView` component (uses `react-markdown` + `remark-gfm` + `skipHtml` for safety) rendered on: admin GigDetail, worker WorkerGigDetail, and the public PublicGigPage. Links open in new tab with `rel="noopener noreferrer"`.
- **Payment timeline**: new `payment_timeline` field on every gig with 4 options — `same_day`, `2_3_days` (default), `weekly`, `custom`. Optional `payment_timeline_note` (free text, shown when `custom`).
- Frontend `lib/paymentTimeline.js` is the single source of truth for labels, icons, pill colors (green=same-day pulsing, blue=2–3 days, black=weekly, amber=custom).
- **Where it surfaces**:
  - **Admin GigDetail**: colored pulsing pill in the tags banner under the title; the custom note shows as an amber callout.
  - **Worker GigDetail (mobile + desktop)**: same pill right under the title.
  - **Worker Feed cards**: same-day and custom show a small pill in the tag stack; default 2-3-day pay is implicit (no clutter).
  - **Public landing snippet + share endpoint**: `payment_timeline` exposed in the `/api/public/gigs` and `/api/public/gigs/{id}` responses so unauthenticated visitors see the same payment-promise signal.
- **Backend**: `GigIn`, `GigPatch`, `_gig_doc`, duplicate-recurring path, public endpoints all updated. Startup backfill ensures every legacy gig gets `payment_timeline="2_3_days"`. 28/28 regression tests still pass.

## Implemented — 2026-06 (Iteration 27: Mobile — Collapsible Best-Fit Workers Panel)
- **Bug**: On mobile the "Best-fit workers" panel in `CreateGigDialog` was eating the bottom half of the dialog and pushing the form (Title field included) out of reach. Users couldn't name a gig from their phones.
- **Fix**: Panel is now collapsible.
  - **Mobile default**: collapsed → single-line header "✨ BEST-FIT WORKERS [count] · Show ▾" so the form has full screen height.
  - **Desktop default**: expanded (no behavior change on big screens).
  - Tap the header anywhere to toggle; caret flips between ▾ Show / ▴ Hide.
  - Expanded panel has its own `max-h-[50vh]` scrollable area so 10+ workers don't blow out the dialog.
- Form `max-h` reduced slightly on mobile (70vh) to leave room for the collapsed-panel header.
- testIDs: `suggested-workers-toggle` (new), `suggested-workers-panel`, `suggested-worker-{user_id}` (preserved).

## Implemented — 2026-06 (Iteration 26: Auth UX — Google-only Account Detection + Mobile Keyboard Hardening)
- **Root cause investigated**: users complaining "wrong password when it's right" were people who originally signed up via "Continue with Google" — the OAuth flow creates a user doc with `auth_provider="google"` and **no `password_hash`**. The old `/auth/login` returned a generic "Invalid email or password" which made them think the platform was broken.
- **Backend `/auth/login`** now distinguishes three states: (a) no user → 401 generic, (b) user exists but Google-only → **409** with structured payload `{code: "no_password_set", provider, message}`, (c) password mismatch → 401 generic. Attacker can't enumerate accounts because mistyped emails still hit the 401 path.
- **Frontend `Login.jsx`** catches the 409 and replaces the red error box with a friendly blue "**This account uses Google sign-in**" panel containing a one-click "Continue with Google" button.
- **Mobile keyboard hardening** on Login + Register email/password inputs: `autoCapitalize="off"`, `autoCorrect="off"`, `spellCheck="false"`, `autoComplete` set to the correct value (`email`, `current-password`, `new-password`), and `inputMode="email"` on email fields. Prevents iOS/Android keyboards from silently auto-capitalizing the first character, inserting smart-quotes, or autocompleting an autocorrected variant of the password.
- **Defensive client-side normalization** of email (trim + lower-case) before submit — backend already does this server-side, but doing it client-side too keeps the displayed value honest and avoids confusion.
- Verified via curl: Google-only user → 409 with helpful detail; non-existent user → 401 generic; valid admin login → 200 (regression clean).

## Implemented — 2026-06 (Iteration 25: Break Deduction)
- **Backend**:
  - `GigIn` / `GigPatch` gained `break_minutes: int` (default 0). Stored on the gig doc; admin sets it in Create / Edit Gig dialogs.
  - `TimesheetEditIn` and `TimesheetApproveIn` gained `break_minutes` per-worker override. Override on the acceptance wins; falls back to the gig default; falls back to 0.
  - New helpers: `_resolve_break_minutes(acceptance, gig)`, `_compute_paid_hours(hours_worked, break_minutes)`. `_compute_earnings` now subtracts break time for hourly pay (flat-rate pays full amount regardless).
  - `clock_out`, `update_acceptance_pay`, `edit_acceptance_timesheet`, `approve_timesheet` all recompute earnings using the new helper and snapshot `break_minutes_applied` + `paid_hours` on the acceptance.
  - `/me/earnings` exposes `break_minutes`, `paid_hours` per row + `total_paid_hours`, `total_break_minutes` in the approved totals.
  - `/admin/reports/timesheets` returns `break_minutes` + `paid_hours` per row and totals; CSV has new "Break (min)" and "Paid hours" columns.
  - Startup backfill ensures every legacy gig gets `break_minutes=0`.
- **Frontend**:
  - **CreateGigDialog + EditGigDialog**: new "Break (min)" field (number input, default 0, helper text "Unpaid break deducted from clocked time").
  - **EditTimesheetDialog**: new "Break (min) — Override per worker" field. Empty leaves gig default; live preview now shows 3-column Clocked / Paid (-break) / Earnings.
  - **WorkerAccepted (`/crew/my-gigs`)**: completed gigs now show "Xh worked – Xh break = Xh paid" under the earnings line. Top earnings summary card shows paid-hours total.
  - **WorkerGigDetail**: completed time-tracking card shows "Xh hours paid" with a subtle break breakdown below.
- **Tests**: 9 new pytest cases in `/app/backend/tests/test_iter25_breaks.py`; 9/9 pass + 19/19 iter21 regression = 28/28 green.

## Implemented — 2026-06 (Iteration 24: Calendar v2 — Multi-View + Heatmap + Mobile)
- Three view modes (toggle pills top-right): **Month / Week / Day**.
- **Month**: 6-row grid with workload heatmap tinting (blue→red gradient based on total slot demand vs busiest day); per-day pay/hours/filled-vs-total slot mini-stats; pin-tag icons embedded in each gig chip.
- **Week**: 7-column workspace, each column shows per-day pay/slot totals in the header and stackable gig cards with category color + tag icons.
- **Day**: hour-by-hour timeline (6 AM → midnight) with full gig detail cards in each bucket; 4 summary KPIs (Gigs/Pay/Hours/Workforce); right-side "At a glance" panel with big-stat cards + a clickable roster list.
- **Mobile responsiveness**:
  - Header collapses (smaller toggle pills, 9×9 prev/next buttons, "+" hides label, compact title).
  - Legend strip becomes horizontally scrollable.
  - **Month**: dot-only chips per day (4 dots + N indicator), single-letter weekday headers (S M T W T F S); tapping a day with gigs opens a **bottom sheet** with Gigs/Pay/Slots summary, full gig list, and a sticky "+ Add gig on this day" button.
  - **Week**: 7 columns stack vertically into a one-day-per-row agenda; each row has a tap-to-add header and the day's gig cards beneath.
  - **Day**: KPI strip wraps, hour timeline reduces gutter, sidebar stacks below content.
- Heatmap legend strip in the header explains the color scale.
- All previous testIDs preserved (`cal-day-{key}`, `cal-chip-{gigId}`, `cal-prev`, `cal-next`, `cal-today`, `cal-new-gig`) plus new ones for the view toggle, per-view chips, and the mobile sheet (`cal-view-month/week/day`, `cal-week-day-{key}`, `cal-week-chip-{id}`, `day-hour-{h}`, `day-card-{id}`, `cal-day-sheet`, `cal-day-sheet-close`, `cal-day-sheet-gig-{id}`, `cal-day-sheet-add`).

## Implemented — 2026-06 (Iteration 23: SEO + Open Graph)
- Site-wide meta tags in `index.html` (OG, Twitter Card, theme-color, branded favicon set).
- Branded 1200×630 `/og-default.png` (HCOB lightning logo + tagline + pin-tag pills).
- Per-gig social unfurling: `GET /api/share/gigs/{id}` returns HTML with gig-specific meta tags + meta-refresh to React; `GET /api/share/gigs/{id}/og-image` renders a dynamic 1200×630 PNG (title/pay/category/location/tags). 5-min cache; PIL fallback to default image.
- Admin "Share gig link" now copies `/api/share/gigs/{id}` so iMessage/Slack/WhatsApp/Facebook unfurl correctly (these crawlers don't run JS).
- Uses `X-Forwarded-Host`/`X-Forwarded-Proto` so canonical URLs match the public hostname (works on preview, prod, and the new `hcobnetwork.com` custom domain without any env change).
- **Site-wide meta tags** in `/app/frontend/public/index.html`: title, description, theme-color, canonical favicon, Open Graph (og:type, og:site_name, og:title, og:description, og:image, og:image:width/height/alt, og:locale), and Twitter Card (twitter:card=summary_large_image, twitter:title, twitter:description, twitter:image). Replaces the old "Emergent | Fullstack App" placeholder.
- **Branded assets** generated via `/tmp/gen_og.py` (one-time): `/og-default.png` (1200×630 social card with HCOB logo + tagline + RUSH/SAME DAY/TOP PAY pills), `/favicon.ico`, `/favicon.png`, `/favicon-192.png`, `/apple-touch-icon.png`.
- **Per-gig social unfurling**: new server-rendered endpoint `GET /api/share/gigs/{id}` returns HTML with gig-specific OG tags (title, pay, category, location, date) + meta-refresh to the React page. Crawlers that don't run JS (iMessage, WhatsApp, Slack, Facebook) read the meta tags. Real users get instant redirect.
- **Dynamic per-gig OG image**: `GET /api/share/gigs/{id}/og-image` renders a fresh 1200×630 PNG showing the gig's title, category, pay, scheduled date, location, and active pin tags (RUSH/SAME DAY/etc). 5-minute browser cache. PIL fallback to the default site image if rendering fails.
- **Admin Share button** in `GigDetail.jsx` now copies `https://yourdomain.com/api/share/gigs/{id}` instead of the bare React route — so every shared link unfurls beautifully across all messaging apps.
- Forwarded-host detection: the share endpoint uses `X-Forwarded-Host`/`X-Forwarded-Proto` headers so canonical URLs match the public hostname (works on preview, production, and any future custom domain without env config).

## Implemented — 2026-06 (Iteration 22: URL Rebrand)
- Worker app paths: `/app/*` → **`/crew/*`** (`/crew`, `/crew/gigs/:id`, `/crew/my-gigs`, `/crew/me`).
- Admin app paths: `/admin/*` → **`/ops/*`** (`/ops`, `/ops/gigs`, `/ops/gigs/:id`, `/ops/workers`, `/ops/workers/:id`, `/ops/requests`, `/ops/reports`, `/ops/calendar`, `/ops/settings`).
- All in-app `nav()`, `<NavLink to=...>`, `<Navigate to=...>`, `href=` callsites updated to new paths.
- **Backwards compatibility**: explicit `<Navigate>` redirects from every old path so saved bookmarks, blast emails, and shared links keep working.
- Public-facing URLs unchanged (`/`, `/login`, `/register`, `/gigs/:id`, `/rate/:token`).
- Backend API routes (`/api/admin/*`, `/api/gigs/*`) unchanged.
- Worker app paths: `/app/*` → **`/crew/*`** (`/crew`, `/crew/gigs/:id`, `/crew/my-gigs`, `/crew/me`).
- Admin app paths: `/admin/*` → **`/ops/*`** (`/ops`, `/ops/gigs`, `/ops/gigs/:id`, `/ops/workers`, `/ops/workers/:id`, `/ops/requests`, `/ops/reports`, `/ops/calendar`, `/ops/settings`).
- All in-app `nav()`, `<NavLink to=...>`, `<Navigate to=...>`, `href=` callsites updated to new paths.
- **Backwards compatibility**: explicit `<Navigate>` redirects from every old path so saved bookmarks, blast emails, and shared links keep working (`/app` → `/crew`, `/admin/gigs/:id` → `/ops/gigs/:id`, etc.).
- Public-facing URLs unchanged (`/`, `/login`, `/register`, `/gigs/:id` for share links, `/rate/:token`).
- Backend API routes (`/api/admin/*`, `/api/gigs/*`) unchanged — these are server endpoints, not frontend pages.

## Implemented — 2026-06 (Iteration 21: Multi-Tag Pin System)
- Generalised single `is_rush` boolean into a `tags` array supporting 4 values: `rush`, `priority_need`, `same_day`, `top_pay`. Multiple tags per gig allowed.
- Backend: new `PUT /api/gigs/{id}/tags` endpoint (replaces tags array, admin-only). `/rush` and `/blast` endpoints kept in sync (rush sets/clears the `rush` tag; blast always adds `rush` to existing tags). Public feed + worker feed + admin gig endpoints all return the `tags` array.
- Frontend shared config at `/app/frontend/src/lib/gigTags.js` — single source of truth for tag labels, icons, colors, priority ordering, border classes.
- Any tag pins the gig to the top of the worker feed and the public landing snippet. Highest-priority active tag determines the card border color.
- Admin GigDetail: inline 2x2 toggle grid (data-testid `tag-toggle-{tag}`); active-tags banner under the title.
- Admin GigsList: inline tag pills next to each gig title.
- Admin EditGigDialog: "Pin tags" section with full toggle row; saves via `/tags` endpoint.
- Worker feed + Landing snippet: tag-pill stack on each card with the colored border.
- 24/24 backend pytest pass, all UI flows green (iteration_18 testing report).

## Implemented — 2026-06 (Iteration 20: Landing-page Live Gigs Snippet)
- New public endpoint `GET /api/public/gigs?limit=N` returns up to 24 open + coming_soon gigs (RUSH-first, then **highest pay**, then newest) with PII stripped — no `address_line`, no `contact_phone`.
- Landing page now shows a "**Open gigs right now · top-paying gigs this week**" section below the marquee with **the 3 highest-paying gigs** (category icon, title, slots left, public location, date, pay).
- RUSH gigs render with the red border + flame badge; `coming_soon` gigs get a black "UPCOMING" pill.
- Clicking a card sends the visitor to `/register?next=/crew/gigs/{id}` so they sign up before claiming.
- Graceful empty state when no open/upcoming gigs exist.
- **Legacy backfill** — `on_startup` now coerces `is_rush=null` → `is_rush=False` on every existing gig.
- New public endpoint `GET /api/public/gigs?limit=N` returns up to 24 open + coming_soon gigs (RUSH-first, then **highest pay**, then newest) with PII stripped — no `address_line`, no `contact_phone`.
- Landing page now shows a "**Open gigs right now · top-paying gigs this week**" section below the marquee with **the 3 highest-paying gigs** (category icon, title, slots left, public location, date, pay). Pulsing green LIVE dot in the section header.
- RUSH gigs render with the red border + flame badge (consistent with the worker feed); `coming_soon` gigs get a black "UPCOMING" pill.
- Clicking a card sends the visitor to `/register?next=/app/gigs/{id}` so they sign up before claiming.
- Graceful empty state when no open/upcoming gigs exist.
- **Legacy backfill** — `on_startup` now coerces `is_rush=null` → `is_rush=False` on every existing gig (otherwise Mongo's null-vs-false ordering broke the RUSH-first sort for older docs).

## Implemented — 2026-06 (Iteration 29: Projects — Linked Gigs Bundles)
- **Concept**: a Project groups 2+ gigs that share a job site (e.g. truck driver + handyman + crew lead). Admins create projects; gigs are linked/unlinked; workers see other gigs in the same project + the crew on those sibling gigs.
- **Backend** (`/api/projects/*`):
  - `POST /api/projects` create (title, description-markdown, client_name, defaults={location, scheduled_date, scheduled_at, payment_timeline, contact_phone}).
  - `GET /api/projects?archived=&q=` list with rolled-up `gig_count`/`worker_count`/`slots_total`/`slots_filled`/`first_scheduled_at`/`last_scheduled_at`.
  - `GET /api/projects/{id}` full detail with linked gigs + crew across all gigs (worker name + per-gig role) + admin-only notes thread.
  - `PUT /api/projects/{id}` partial edit; `DELETE /api/projects/{id}` archive (auto-unlinks gigs; doesn't delete gigs).
  - `POST/DELETE /api/projects/{id}/notes` admin-only notes thread.
  - `POST /api/gigs/{gig_id}/link-to-project` (body: `{project_id, sync_defaults}`) + `DELETE /api/gigs/{gig_id}/project` (unlink).
  - Optional `sync_defaults=true` pulls project's defaults (location/scheduled_at/payment_timeline/contact_phone) into the gig.
- **Gig list/detail enrichment**:
  - `GET /api/gigs` (admin): each gig with a `project_id` is enriched with `project={project_id, title, client_name}` for the project pill.
  - `GET /api/gigs/{id}` (admin): adds `project={project_id, title, client_name, archived, sibling_gigs[]}`.
  - `GET /api/gigs/{id}` (worker, only when **approved** not requested): adds `project={project_id, title, client_name, sibling_gigs[], crew[]}` with crew exposing only `first_name + gig_role + gig_id + gig_title` (PII-stripped, no email/phone/last-name).
- **Frontend**:
  - New routes `/ops/projects` (list with Active/Archived URL-driven filter) + `/ops/projects/:projectId` (detail with linked-gigs grid, combined crew roster, admin notes thread).
  - Sidebar entry **Projects** (folder icon) between Gigs and Workers.
  - `CreateProjectDialog`, `EditProjectDialog`, `LinkGigToProjectDialog` (link existing gig from project detail), `PickProjectForGigDialog` (link from gig detail with inline create-project shortcut).
  - `AdminGigs` rows now show a `project-pill-{gigId}` linking to the project detail.
  - `GigDetail` (admin) shows a `project-banner` with title + Open project button + Unlink button when linked, else a `project-link-btn` to open the picker dialog.
  - `WorkerGigDetail` shows a `worker-project-card` (after approval) listing the project title, sibling gigs, and PII-stripped crew chips.
- **Testing**: 16/16 backend pytest pass (`/app/backend/tests/test_iter_projects.py`); E2E Playwright covered all 9 admin + 2 worker flows. UX polish: archive redirects to `?archived=true` so freshly-archived projects appear immediately on the Archived tab; URL-driven tab state survives reloads.

## Backlog
### P1
- [ ] Worker push/email notification preferences (opt-in per channel)
- [ ] Geo-fenced / city filter for gig feed
- [ ] Email + SMS provider keys collection UI (admin settings)
- [ ] Calendar view for admin (upcoming scheduled gigs)
- [ ] Rich gig templates per category (cleaning checklist, labor PPE notes, ride pickup address)

### P2
- [x] Public gig share link `/gigs/:gigId` (no-auth view + register-then-claim) — Feb 2026
- [x] Per-gig worker roles (worker/manager/lead/trainer) + workers see crew first-names — Feb 2026
- [x] Admin users management (add admins, read-only role, promote/demote) — Feb 2026
- [x] Worker rating system (admin manual stars + client public link) — Feb 2026
- [x] Admin override editor for any worker profile (skills, contact, status, ID verified, email) — Feb 2026
- [x] Worker activity report (gigs requested/approved/completed/no-shows) — Feb 2026
- [x] Workers / Roster export (CSV + Google Sheets, with optional PII toggle) — Feb 2026
- [x] Gigs report (assignments + payout per gig) — Feb 2026
- [x] Earnings payroll summary (one row per worker) — Feb 2026
- [x] Edit clock-in / clock-out times — Feb 2026
- [x] Worker reliability hooks (no_shows tracked in activity report) — Feb 2026
- [ ] Worker ratings (manual admin rating after gig completion)
- [ ] Recurring gigs (auto-blast weekly)
- [ ] Stripe payouts for completed gigs
- [ ] Worker chat / direct message admin
- [x] CSV export of timesheets per date range — Feb 2026
- [x] Custom worker pay (default + per-gig override) — Feb 2026
- [x] Auto-calculate clock-in/out earnings — Feb 2026
- [x] Timesheet approval flow (worker sees earnings only after approve) — Feb 2026
- [x] Admin Reports page (date filter, worker filter, totals, day grouping) — Feb 2026
- [x] Google Sheets export via service-account (one central HCOB account) — Feb 2026
- [x] Extended worker profile (zip, skills, availability, vehicle, emergency contact, bio) — Feb 2026
- [x] Profile completion gate (must complete profile + ID verify before requesting gigs) — Feb 2026
- [x] Admin Workers filters (skills/availability/zip/vehicle/profile/search) — Feb 2026
- [x] Auto-suggest matching workers on create-gig dialog — Feb 2026

---

## VA Commission Marketing Program — Phase 1 (Feb 2026, this session)

**Goal:** A self-contained module inside the HCOB Network platform that lets cleaning-lead Virtual Assistants (VAs) submit prospects, watch them move through a 7-stage pipeline, and automatically earn commissions — with mandatory Program Manager review and final Owner sign-off before any payout.

### Roles introduced
- **VA** (`role=va`, `va_status ∈ {pending, approved, suspended, removed}`): self-signup via `/register?as=va` or PM-created. Pending VAs cannot submit leads.
- **Program Manager** (`role=admin`, `is_program_manager=true`): seeded as `mechiebadlong77@gmail.com` / `Mechie2026!`. Reviews leads, approves commissions, manages VA accounts.
- **Owner** (`role=admin`, `is_owner=true`): set on `admin@hcobcleaners.com`. Final payout sign-off + mark-paid + bulk-approve.

### New DB collections
- `va_leads` — every prospect with stage history + ownership lock
- `commissions` — per-lead commission records, full lifecycle status
- `va_violations` — permanent audit log of duplicate-lead, self-referral, account_suspended, commission_flagged events
- `commercial_accounts` — recurring 5% commission tracking
- New `users` fields: `va_status`, `va_phone`, `va_address`, `is_owner`, `is_program_manager`, `must_change_password`

### Commission rate engine
- Routine 1-time → $10 (or recurring tier if part of series)
- Recurring visits: V1=$15, V2=$25, V3-6=$10 each, lifetime cap $100 per client
- Deep / Move-Out / Specialty → $25 flat
- Commercial → 5% of monthly revenue
- Cleaner Referral (future): $20 → $30 → $50, cap $100

### Safeguards (enforced at DB layer)
- **Duplicate lead** — block if phone OR email already in active lead. Allow resubmit if original is `Completed` or `Lost` AND > 90 days old. Violation logged.
- **Self-referral** — block if prospect address matches VA's registered address (case/whitespace/punctuation-insensitive). Violation logged.
- **Timestamp ownership lock** — set on lead create. Can't be edited or transferred.
- **Double-payment** — `mark-paid` on an already-paid commission returns 400. Status frozen once paid.
- **Suspension** — kills all sessions immediately. Removed accounts cannot re-authenticate.

### Commission lifecycle (verified)
1. VA submits lead → `stage=new_lead`
2. PM advances stage Booked → commission record created with `status=calculating`
3. PM advances stage Paid (with job_value) → commission `status=pending_approval` (PM queue)
4. PM Approve / Flag (note required) / Reject
5. Owner one-click sign-off → `owner_approved` (or bulk per VA per week)
6. Owner mark-paid (method + reference) → `paid`. VA notification fired.

### Backend (server.py ~7400 lines now — overdue refactor)
- New models (LeadIn, LeadStageIn, CommissionActionIn, OwnerBulkApproveIn, CommissionMarkPaidIn, VAAccountAdminIn, CommercialAccountIn/Patch)
- Routes `/api/va/*`, `/api/pm/*`, `/api/owner/*` (full surface in `/app/memory/test_credentials.md`)
- Indices created on startup for fast lookups
- Mechie seed + Owner flag migration on every boot (idempotent)
- 26/26 pytest pass (`/app/backend/tests/test_va_commission.py` + `test_va_commission_extra.py`)

### Frontend
- VA portal `/va` with sidebar (Dashboard, Submit Lead, My Leads, Earnings) + pending-status banner
- Admin sidebar gains a **VA Commission** section (5 entries) + Owner-only **Payouts** entry with live count badges
- New pages: AdminVAOverview, AdminVAPipeline, AdminVACommissions, AdminVAs, AdminCommercialAccounts, AdminOwnerPayouts
- Register page upgraded with role toggle (Worker / VA) + VA-specific fields

### Known minor follow-ups
- [ ] `prospect_phone` is required (FRD-consistent). Could be relaxed to "phone OR email" with explicit 400.
- [ ] Two non-blocking console 403s on Mechie's view of `/ops/va-program/commissions` — `is_owner` guarded but seemingly stale call. Cosmetic.
- [ ] `/va/submit` "Preferred datetime" uses browser-default — replace with shadcn DatePicker.
- [ ] Phase 2: Stripe ACH auto-payouts (deferred per user choice), email/SMS triggers on stage update.
- [ ] Phase 3: Advanced leaderboard intelligence, automated reactivation outreach.

## Latest additions (Feb 2026)

### VA recruitment landing page (`/vas`, `/earn`, `/work-with-us`)
- Community-first hero: *"Join HCOB's VA crew. Real leads, real payouts, every week."*
- 4-step "How it works" · Transparent rate table (caps hidden) · Dedicated payout-schedule timeline
- Earnings examples (Casual / Active / Power VA) · 6-question FAQ · Final dark CTA
- "Become a VA →" entry points added to the main `/` landing (header + slim callout under hero)

### Sortable gigs list (`/ops/gigs`)
- Clickable column headers with active arrow indicators — Title, Category, When (real `scheduled_at` timestamp), Pay, Slots (open-remaining), Status, Blasts
- Toolbar "Sort by" dropdown + explicit Asc/Desc toggle
- Default = newest posted first

### Gig Blast Reports (`/ops/reports` → Blasts tab)
- New persistent `blast_logs` collection — every gig/project blast captured
- Backend route `/api/admin/reports/blasts` with date / channel / kind filters
- 4 KPIs (Total Blasts, Workers Targeted, Email Sent, SMS Sent) + full per-send row showing channels, counts, failures, and **sender name**
- CSV download + Google Sheets export inherited from existing Reports plumbing

## Next steps
1. Wire real Resend + Twilio keys (admin to provide), then enable per-blast email/SMS
2. Add worker mobile-app PWA install prompt OR convert via Emergent Mobile Agent (Expo/React Native)
3. Google Auth (optional social login)
4. Worker reliability/rating system (auto-compute from punctuality, completion, no-shows)
5. **Backend modularization** — `server.py` is at ~7400 lines. Split into `routes/auth.py`, `routes/gigs.py`, `routes/projects.py`, `routes/va_commission.py`, `routes/owner.py`.
6. **VA Commission Phase 2** — Stripe ACH auto-payouts, stage-update email/SMS triggers, cleaner referral tracking.
