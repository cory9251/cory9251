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

## Implemented — 2026-02 (Iter 33: Backend Modularization Phase 3e — Admin + Reports Extracted) — VERIFIED
- **server.py: 5,439 → 3,378 lines** (−2,061; cumulative −5,633 ≈ **62% reduction** from the 9,011 baseline).
- **`routes/admin.py`** (~1,140 lines) owns: `/admin/workers/*` (list/match/get/profile/verify-id/id-upload/approve/reject/suspend/reinstate/reset-password/delete), `/admin/users/{id}/reset-password` (Owner-only), `/admin/requests`, `/admin/stats`, `/admin/workers/{id}/pay` defaults, `/gigs/{id}/acceptances/{aid}/pay` overrides, `/gigs/{id}/acceptances/{aid}/{approve,unapprove}-timesheet`, `/gigs/{id}/acceptances/{aid}/timesheet` edit. Helpers `_set_worker_status`, `_completed_gigs_by_worker_and_category`, `_parse_admin_dt` and inline Pydantic models (`AdminProfileUpdateIn`, `AdminGigNoteIn`, `WorkerMessageIn`, `AcceptanceRoleIn`, `AdminCreateIn`, `AdminRoleUpdateIn`) live here. Re-exports `GIG_ROLES`/`GIG_ROLE_LABELS` for the 3 remaining gig-acceptance admin endpoints in server.py.
- **`routes/reports.py`** (~1,070 lines) owns the entire reports stack: builders (`_build_workers_report`, `_build_gigs_report`, `_build_activity_report`, `_build_earnings_report`, `_build_blasts_report`, `_build_timesheet_rows`), dispatcher (`_dispatch_report` + `REPORT_TYPES`), endpoints (`/admin/reports/{type}`, `/admin/reports/{type}.csv`, `/admin/reports/timesheets[.csv]`, `/admin/reports/export-google-sheets`), and the worker-facing `/me/earnings`.
- **Verified by testing agent**: **104/104 tests pass** (29 new iter30 + 75 prior regression). Zero behavior change confirmed across pay overrides + earnings recompute, session-kill on reject/suspend/reset, delete-cascade, report shape parity, /me/earnings worker-vs-admin gating, and Google Sheets export error path.

## Implemented — 2026-02 (Iter 32: Backend Modularization Phase 3d — Gigs Extracted) — VERIFIED
- **server.py: 7,136 → 5,439 lines** (−1,697; cumulative −3,572 from baseline ≈ 40% reduction).
- **`routes/gigs.py`** (~1,500 lines) owns the entire gig surface:
  - **CRUD**: `POST /gigs` (with recurrence series), `GET /gigs`, `GET /gigs/{id}`, `DELETE /gigs/{id}`, `PUT /gigs/{id}`, `POST /gigs/{id}/duplicate`
  - **Lifecycle**: `POST /gigs/{id}/accept`, `POST /gigs/{id}/requests/{aid}/approve`, `POST /gigs/{id}/requests/{aid}/approve-backup`, `POST /gigs/{id}/acceptances/{aid}/promote`, `POST /gigs/{id}/requests/{aid}/reject`, `POST /gigs/{id}/assign`, `DELETE /gigs/{id}/acceptances/{aid}`, `POST /gigs/{id}/cancel-shift`, `POST /gigs/{id}/withdraw` (legacy alias)
  - **Broadcast**: `POST /gigs/{id}/blast`, `PUT /gigs/{id}/rush`, `PUT /gigs/{id}/tags`, `POST /gigs/{id}/publish`
  - **Time tracking**: `POST /gigs/{id}/clock-in`, `POST /gigs/{id}/clock-out`
  - **Helpers** (re-exported for admin/timesheet/reports): `_gig_doc`, `_strip_sensitive_for_worker`, `_effective_status`, `_resolve_pay`, `_resolve_break_minutes`, `_compute_paid_hours`, `_compute_earnings`, `_format_gig_email`, `_format_gig_sms`, `_promote_first_backup`, `_notify_matching_workers_of_new_gig`, `_publish_due_gigs_loop`
- **`notifications.py`**: gained `_log_blast` (moved from server.py — used by both gig blast and project blast endpoints).
- **Verified**: 80/80 backend tests pass (15 new iter29 + 65 prior regression). Testing agent confirmed zero behavior change across blast→rush+tags flip, clock-in/out guards, cancel-shift→backup-promotion chain, and delete-cascade. 3 unrelated pre-existing test_calendar fixture failures explicitly excluded by testing agent.

## Implemented — 2026-02 (Iter 31: Backend Modularization Phase 3c — Profile Extracted) — VERIFIED
- **server.py: 7,262 → 7,136 lines** (−126; cumulative −1,875 from baseline).
- **`routes/profile.py`** (163 lines) owns `/profile/options`, `/profile` (PUT), `/profile/avatar`, `/profile/id`, `/files/{path}`, plus the shared `_upload_user_image` helper. server.py re-imports `_upload_user_image` so the admin worker-ID upload endpoint keeps working unchanged.
- **Verified**: 86/87 backend pytests still green; curl: login ✅, /profile/options ✅, /files/nope unauth 401 ✅, /files/nope auth 404 ✅.

## Implemented — 2026-02 (Iter 30: Backend Modularization Phase 3b — Auth Extracted) — VERIFIED
- **server.py: 7,545 → 7,262 lines** (−283; cumulative −1,749 from the 9,011 baseline).
- **`routes/auth.py`** (329 lines) now owns the full auth surface: `_issue_session` helper + `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/google/session`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`.
- **Pure move, zero behavior change**: VA-vs-worker register branching, Google-only 409 detection, single-use token expiry, kill-all-sessions-on-reset — all preserved verbatim.
- **Verified**: 86/87 backend pytests pass (1 pre-existing skip). End-to-end curl: login ✅, /auth/me ✅, bad-password 401 ✅, forgot-password 200 ✅, logout 200 ✅.

## Implemented — 2026-02 (Iter 29: Backend Modularization Phase 3a — Push Extracted) — VERIFIED
- **server.py: 7,688 → 7,545 lines** (−143).
- **`push_service.py`** (90 lines) now owns `_send_push_sync`, `_send_push_to_user`, and `PushSubscriptionGone`. Async fan-out + auto-prune of dead (404/410) subscriptions.
- **`routes/push.py`** (102 lines) — 5 endpoints lifted out: `GET /push/public-key`, `POST /push/subscribe`, `DELETE /push/subscribe`, `GET /push/status`, `POST /push/test`.
- server.py now imports the fan-out helper (`from push_service import _send_push_to_user`) for the 4 places that fire pushes (approve-request, promote-backup, blast-gig, publish-due-gigs).
- **Verified**: 35/35 modularization tests pass; 86/87 broader sweep green (1 pre-existing skip); `curl /api/push/public-key` returns VAPID key; unauth `/api/push/status` returns 401.

## Implemented — 2026-02 (Iter 28: Backend Modularization Phase 1+2) — VERIFIED
- **server.py: 9,011 → 7,688 lines** (-1,323, ~15% reduction).
- **7 new modules extracted** (1,546 lines pulled into focused files):
  - `config.py` (51) — env vars, logger, Mongo client, Resend init
  - `constants.py` (92) — WORKER_SKILLS, GIG_CATEGORY_TO_SKILLS, etc.
  - `models.py` (331) — ALL Pydantic request models in one place (~35 classes)
  - `storage.py` (78) — object storage helpers (put_object, get_object, _ext_from)
  - `auth_deps.py` (164) — get_current_user, require_admin, password helpers, profile-completion helpers
  - `notifications.py` (184) — Resend + Twilio helpers (_send_user_email, _public_base, _email_layout, etc)
  - `routes/messages.py` (646) — entire messenger module (10 endpoints + email-digest background task)
- **Flat-import pattern** (e.g., `from config import db`) matches existing uvicorn invocation (`server:app` from `/app/backend`)
- **Verified clean**: 35/35 pre-existing pytests pass; 16/16 new regression suite (`test_iter28_refactor_regression.py`) passes; all admin nav pages, VA portal, public pages, worker register→login→feed→detail E2E all work with zero console errors and zero 5xx.

## Implemented — 2026-02 (Iter 27: Removed Emergent Badge) — VERIFIED
- Removed static `<a id="emergent-badge">` from `index.html` and added a MutationObserver to strip the runtime-injected version. Verified across login / /ops / /ops/messages — zero badge presence.

## Implemented — 2026-02 (Iter 26: Clickable Worker Names Everywhere) — VERIFIED
- New `<WorkerLink>` component at `/components/admin/WorkerLink.jsx` — renders a worker's name as a dotted-underline `<a target="_blank" href="/ops/workers/:id">` with `data-testid=worker-link-{worker_id}`. Falls back to plain `<span>` when worker_id is missing.
- Applied across every admin surface that displays a worker name:
  - **GigDetail** (3 spots): pending requests row, backups row, approved roster row
  - **AdminRequests** global queue
  - **AdminReports** timesheet/blast rows
  - **AdminProjectDetail** crew list
  - **Dialogs**: ApproveTimesheet, PayOverride, Rating (2 spots), EditTimesheet
  - **Messages**: DM thread header (when admin→worker) + each non-mine message bubble sender label
- New-tab behavior preserves admin context (don't lose the gig/project/report you were on)
- Worker and VA portals intentionally unmodified (admin-only feature)
- Testing: 100% pass on 5 live-verified surfaces, source-verified on the 4 dialogs (no seed data available to live-trigger them)

## Implemented — 2026-02 (Iter 25: Tightened Messenger Permissions) — VERIFIED
- **Workers can no longer freely DM other workers**. New rule:
  - Workers can always DM any admin (preserves the "Message admin" button on gig pages).
  - Workers can DM another worker **only if they've shared a gig** (both approved on the same gig at any point — historical completed gigs count).
  - VAs unchanged (admins only).
  - Admins unchanged (anyone).
- **`/api/messages/eligible-users`** for workers now returns admins + their coworkers (workers they've shared a gig with). Strangers are hidden from the New Message dialog.
- **Existing threads remain accessible** — the gate is at thread-creation only. Already-open conversations don't get cut off.
- **Gig group chats unchanged** — approved workers + admins still see the per-gig group thread.
- **Empty state copy** in the New Message dialog now explains the rule to workers ("You can DM HCOB admins anytime, and any worker after you've shared a gig with them.").
- **Testing**: 13/13 messenger pytests pass (5 new coworker-rule tests added).

## Implemented — 2026-02 (Iter 24: In-App Messenger) — VERIFIED
- **DMs + per-gig group chats**: Worker↔Admin, Worker↔Worker, VA↔Admin (role-gated). Deterministic thread IDs (`dm_{sortedA}__{sortedB}`, `gig_{gig_id}`) so opening is idempotent.
- **General inbox + per-gig threads**: `/ops/messages`, `/crew/messages`, `/va/messages` all render the same `Messages.jsx` page inside their respective layouts. Thread list left, conversation right; mobile collapses with a back arrow.
- **Polling delivery**: navbar badge polls `/api/messages/unread-count` every 10s; active thread polls `/api/messages/threads/{id}/messages` every 5s. Custom `hcob:messages-changed` event refreshes the badge instantly after send.
- **Email digest**: background asyncio task runs every 5min, rolls up unread messages older than 15min into a single Resend email per user. Throttled by `message_digest_state` so each head message only emails once. Graceful degradation when Resend isn't configured.
- **Text + image attachments**: paperclip → upload (10MB cap, image MIME only) → thumbnail preview → send → renders in bubble. Attachment ACL: any thread participant can fetch (extended `/api/files/{path}`).
- **Quick CTAs**: Worker GigDetail shows 'Message HCOB admin' + 'Group chat' when approved. Admin GigDetail shows 'Open gig group chat'. Admin WorkerDetail shows 'Message worker'.
- **Testing**: 8/8 backend pytests (`test_messenger.py`) + 28/28 regression. Full Playwright E2E on admin, worker, and VA portals — every flow verified.

## Implemented — 2026-02 (Iter 23: Backup Workers + Shift Cancellation + Email Notifications) — VERIFIED
- **Backup workers**: Gigs gain `backup_slots` (CreateGigDialog field `gig-backup-slots`) and `backups_filled` counter. Approve-as-backup button next to Approve on pending requests. New Backups section on admin GigDetail with Promote and Remove actions.
- **Backend endpoints**: `POST /api/gigs/{id}/requests/{aid}/approve-backup`, `POST /api/gigs/{id}/acceptances/{aid}/promote`. Slot accounting (`slots_filled`/`backups_filled`/`status`) updates correctly.
- **Worker shift cancellation**: New `POST /api/gigs/{id}/cancel-shift` body `{reason, note}`. Replaces silent withdraw for accepted workers. WorkerGigDetail shows a Cancel Shift modal with reason radios + optional note. If `scheduled_at < 24h` away the cancellation is flagged `is_late=true` and the worker sees a late-cancel toast. If a backup is queued they're auto-promoted in the same response (`backup_promoted=true`, `promoted_worker_id`).
- **Pending withdraw retained**: Workers who are still pending (not approved) see a Withdraw button that cancels their request before the slot is reserved.
- **Resend email notifications**: Hooked into approve / reject / remove / suspend / gig-update flows. Graceful degradation when Resend isn't configured (admin action still succeeds).
- **Testing**: 12/12 backend pytests pass (`test_backups_and_cancel.py` + `test_iter23_e2e_setup.py`). Full Playwright E2E coverage for Admin GigDetail backup flow and Worker GigDetail cancel-shift modal (iter23 report).

## Implemented — 2026-06 (Iter 34: Wall-Clock Times + 'Available Now' Toggle) — VERIFIED
- **Calendar/feed timezone bug FIXED**. Recurring gigs were storing the human display string (`scheduled_date`) in UTC because `strftime` was called on a UTC-aware datetime, so an admin in EST posting "9 AM weekly" saw "9 AM" on occurrence 0 but "2 PM" on every later one. Root cause + fix verified end-to-end.
- **New field `scheduled_local`** (`"YYYY-MM-DDTHH:mm"`, no TZ) is now the single source of truth for display. Same string is shown to the admin and any worker, anywhere in the world — no drift.
  - Backend: added to `GigIn` + `GigPatch` (`models.py`). `routes/gigs.py` `_gig_doc` persists it; the recurring loop now advances both the wall-clock and the UTC datetime in lock-step.
  - Backfill on `on_startup`: derives `scheduled_local` from `scheduled_at` interpreted in `America/New_York` (HCOB HQ, override via `HCOB_SITE_TZ` env). Idempotent.
- **New frontend helper `/app/frontend/src/lib/gigDate.js`**:
  - `getGigDate(g)` — JS Date in browser-local with the admin's wall-clock hour, regardless of viewer TZ.
  - `formatGigWhen(g)` — "Today · 9 AM – 5 PM", "Tomorrow · …", "Fri Mar 14 · 9 AM"
  - `formatGigLong(g)` — "Friday, March 14 · 9:00 AM – 5:00 PM (8h)"
  - `formatGigShort(g)` — "Fri Mar 14 · 9 AM"
  - `formatGigRelative(g)` — "Starts in 3h", "Started 20m ago"
  - `isGigToday(g)` / `isGigTomorrow(g)` for highlight styling.
- **Applied across every surface**: WorkerFeed (with Today highlight pill), WorkerGigDetail, WorkerAccepted, AdminCalendar (replaces `parseISO(scheduled_at)`), AdminGigs (sortable column), AdminDashboard, GigDetail (admin), PublicGigPage, Landing live snippet. CreateGigDialog + EditGigDialog now send `scheduled_local` alongside `scheduled_at`.

### "Available Now" worker toggle (user picked option E from the AI suggestions)
- **Backend**:
  - `PUT /api/me/availability` body `{available: bool, hours?: int}` — worker self-service. Default `available=true` sets `available_until = end-of-day in HCOB_SITE_TZ` (America/New_York). Custom `hours` = 1..24. Non-workers get 403.
  - New user fields: `available_now: bool`, `available_until: ISO string`, `available_set_at: ISO string`.
  - Auto-expiry: `_get_user_by_id` and `GET /admin/workers` recompute on read — if `available_until < now`, the flag is auto-cleared (and persisted for housekeeping).
  - `GET /admin/workers?available_now=true|false` filter.
  - `GET /admin/stats` adds `available_now` integer count of currently-available workers.
- **Frontend**:
  - New component `/app/frontend/src/components/worker/AvailableNowToggle.jsx` with two variants (`card`, `compact`).
  - Worker `/crew` (WorkerFeed): big green pill above the verification banner. Tap → broadcasts. Shows live countdown "Until 9:30 PM" with "Xm left" pulse when <60min remain. Hidden for pending/rejected/suspended workers.
  - Admin `/ops` dashboard: green strip "X worker(s) are available right now — perfect for RUSH gigs" → links to roster (data-testid `dashboard-available-strip`).
  - Admin `/ops/workers`: new toggle button (data-testid `filter-available-now`) next to Filters; each available worker card shows a pulsing green `AVAILABLE NOW` badge.
  - Admin `Add a worker` dialog: available workers pinned to top + per-row badge + counter pill (data-testids `assign-available-{id}`, `available-now-count`).
- **Tests**: 9/9 pytest (`test_iter34_tz_and_availability.py` + `test_iter35_backcompat.py`). 100% E2E via the testing agent (iteration_35.json) — calendar timezone fix, robust feed formatting, and full Available-Now flow all verified.


## Implemented — 2026-06 (Iter 36: Cloudflare 524 Blast Timeout — Hotfix) — VERIFIED
- **Bug**: User reported a Cloudflare "origin took too long" 524 error in production when blasting a gig. Root cause: the blast endpoint sent emails + push + SMS **serially** to every worker (~1,900 in the user's case). Resend rate-limits at 25 req/s + push at ~100ms/call ⇒ ~10+ minutes of synchronous HTTP I/O inside one request, far past Cloudflare's 100s cap.
- **Fix**:
  - In-app notifications stay inline (single `insert_many` is fast — <1s for thousands).
  - Email + SMS + Push moved into `BackgroundTasks` via the new helper `notifications.fanout_blast_channels(...)`. Endpoint returns `{ok, counts, queued: true, blast_id}` in well under 1s.
  - **Per-channel concurrency caps** to stay within third-party rate limits: email=5 (≤25 req/s Resend), sms=1 (Twilio default), push=30 (in-house).
  - Recipients now filtered to **active workers only** (`worker_status in approved/active/null`); pending/rejected/suspended are skipped — saves Resend quota.
  - Blast log is persisted upfront with estimated counts, then **reconciled** with the actual delivered numbers on completion (new `completed_at`, `email_failed`, `sms_failed` fields on the log doc).
  - Frontend toast distinguishes queued vs synchronous: "Blast queued — in-app X sent now; Y emails / Z push delivering in the background."
- **Tests**: `test_iter36_blast_perf.py` (3/3) — verifies <10s response with all channels, `queued: true` flag, log row created. Full regression suite 72/72 still green.
- **Action required for user**: redeploy production (the fix is in preview only).


## Implemented — 2026-06 (Iter 37: Backend Modularization Phase 3f) — VERIFIED
- **Projects, VA, PM, and Owner routes extracted from `server.py`** into dedicated modules. The monolith is now **1,534 lines** (down from 3,416 at the start of this iteration, or 9,011 at the very start of the refactor — **83% reduction**).
- **New modules**:
  - `va_commission.py` (396 lines) — shared deps + Pydantic models + commission calculation engine. Used by VA/PM/Owner routes.
  - `routes/va.py` (218 lines) — VA portal (`/api/va/*`): dashboard, lead submission, earnings, commercial accounts.
  - `routes/pm.py` (492 lines) — Program Manager (`/api/pm/*`): lead pipeline, commission queue, VA roster management, violations, commercial accounts, weekly report.
  - `routes/owner.py` (228 lines) — Owner sign-off (`/api/owner/*`): payout queue, bulk approve, mark-paid (with double-pay guard).
  - `routes/projects.py` (649 lines) — Projects CRUD + worker-view (PII-gated) + notes + gig linking + consolidated blast (background fan-out).
- **Zero behavior change**: All URLs, payload shapes, and permission gates preserved exactly. Testing agent verified 108/108 tests pass (72 prior + 36 from `test_iter37_*.py` covering full VA-Commission lifecycle, Owner permission gate, projects worker-view PII gating, double-pay guard, order guards).
- **Remaining in server.py**: Notifications, worker ratings, public/share endpoints, quote requests, admin user management, settings, startup/shutdown handlers. Phase 3g (optional) could split these further.


## Implemented — 2026-06 (Iter 38: VA Commission Analytics) — VERIFIED
- **New endpoint**: `GET /api/pm/analytics` (admin/PM/Owner) returns three datasets in one round-trip:
  - **`velocity`** — Monthly commission totals, broken down by `paid` / `owner_approved` / `pm_approved` / `pending` / `rejected`. Configurable window (1-12 months, default 6).
  - **`funnel`** — Per-VA conversion: leads → contacted → quoted → booked → paid + `conversion` % (paid/leads). Cumulative ("at-or-past" stage) so the pyramid is always monotonic.
  - **`leaks`** — Leads stuck in a non-terminal stage longer than `leak_days` (default 7, configurable 1-60). Sorted oldest-first with `days_stuck` field.
- **New page**: `/ops/va-program/analytics` (`AdminVAAnalytics.jsx`). Three sections:
  - Stacked bar chart for velocity with 3mo / 6mo / 12mo window toggles. Legend distinguishes paid (green), approved-pending-payout (violet), pending PM review (amber).
  - Per-VA funnel table — sortable, color-coded conversion rate (green ≥25%, amber 10-25%, red <10%). Totals footer + 25-row cap to keep it scannable.
  - Leaks list — color-coded (rose for ≥21d, amber for ≥14d, neutral otherwise) with deep-link to the lead in the pipeline. Cash-flow summary strip at bottom.
- **Discoverability**: New CTA button on `/ops/va-program` ("Open detailed analytics →") so PMs and the Owner can find it.
- **Tests**: `test_iter38_va_analytics.py` (5/5) — shape, funnel monotonicity, leak threshold filter, params clamping (months 1-12), permission gate (worker → 403). Full regression: 71/71 + 1 skip green.


## Implemented — 2026-02 (Iter 39: Blast Safety — P0 SEV1 fix) — VERIFIED
**Incident**: ~25,000 duplicate emails sent to the same test addresses after the Iter 36 BackgroundTask refactor, draining the Resend quota in preview and production.

**Defense in depth — three layers**:
1. **Owner-toggleable kill switch** (`/admin/blast-kill-switch`): When ON, every `/blast` endpoint returns 503 and any in-flight `fanout_blast_channels` re-checks and exits early. Toggleable via Owner UI (no redeploy) OR `BLAST_KILL_SWITCH` env var (emergency override). State persisted in `app_settings.blast_kill_switch` with `toggled_at` / `toggled_by` audit fields.
2. **Per-gig / per-project cooldown** (default 300s via `BLAST_COOLDOWN_SECONDS`): Repeat blasts of the same gig or project within the cooldown window return 429 with a clear "wait Xs" message. Per-resource — blasting different gigs in the same window still works.
3. **Dedupe by email (and phone)** in `fanout_blast_channels`: Worker list is lower-cased + deduped before any sends, so duplicate user docs can't multiply the send count. Also persists `sent_emails`/`sent_phones` on `blast_logs` so a retried fan-out skips already-mailed addresses.

**New endpoints**:
- `GET /api/admin/blast-kill-switch` — admin; returns `{enabled, source, toggled_at, toggled_by, cooldown_seconds}`
- `POST /api/admin/blast-kill-switch` — Owner-only; body `{enabled: bool}`
- `GET /api/admin/blast-audit?gig_id&project_id&hours` — admin; returns recent `blast_logs` rows + top email recipients in window (forensic tool for future incidents)

**New UI** — Settings page (`/admin/settings`): `BlastKillSwitchPanel` between status cards and password panel. Big red "Disable all blasts" button (green "Re-enable" when ON). Shows last-toggled timestamp + by-whom. Read-only when env-var override is active.

**Observability**: structured `[blast {blast_id}]` log lines at fanout start, completion, and abort. Reconciliation persists counts on `blast_logs` even on partial failures.

**Tests**: `test_iter39_blast_safety.py` (6) + `test_iter39_blast_safety_extra.py` (8) = 14 new tests; combined with `test_iter36_blast_perf.py` regression = **17/17 green**. Resend is mocked / channel-restricted to `in_app` — zero quota consumed during tests.




## Implemented — 2026-02 (Iter 40: One-click "Message user" + DM companion channels) — VERIFIED 24/24
**Goal**: From any worker/VA surface, admins can DM the user in one click. Plus per-send email/SMS companion delivery.

**New reusable component** — `/app/frontend/src/components/messages/MessageUserButton.jsx`:
- Variants: `default` (full button), `icon` (28px square), `row` (table cell pill), `compact` (text link)
- Calls `POST /api/messages/threads/dm` → navigates to portal-aware Messages route (`/ops/messages`, `/va/messages`, `/crew/messages`)
- Stops event propagation so it can sit inside clickable cards/rows safely

**Wired into**:
- WorkerDetail (full button under Account management)
- AdminWorkers list (icon top-right of each card; card body refactored from `<button>` to `<div role="button">` to allow nested interactivity)
- AdminVAs table (row pill in actions cell — pending / approved / suspended)
- AdminVAPipeline (icon button in VA column)
- GigDetail — pending requests, backups, approved acceptances (icon next to WorkerLink)

**Messages page enhancements** (admin + DM-thread only):
- **Quick template chips**: Available? · ID reminder · Shift soon · Late · Thanks · Update lead — `{name}` token replaced with recipient first name on click
- **Channel toggle row**: ☐ Email ☐ SMS checkboxes, persisted to localStorage (`hcob_dm_channels`)
- After send, toast confirms: "Sent via in-app + email" when companion channels used

**Backend** (`/app/backend/routes/messages.py`):
- `MessageSendIn.channels: List[str]` (optional) accepts `["email", "sms"]`
- `send_message` dispatches `_deliver_dm_companion()` via `asyncio.create_task()` (fire-and-forget — won't block HTTP response)
- Gated by: sender role in (admin/owner/pm), thread.type == "dm" (NEVER on gig_group → avoids mass-spam), and `is_blast_disabled()` kill switch
- Response now includes `companion_channels: []` so UI can confirm what was attempted

## Implemented — 2026-02 (Iter 41: Editable VA Program — Batch 1) — VERIFIED 41/41
**Goal**: Make leads fully editable + soft-deletable, with audit log.

**Backend** (`/app/backend/routes/pm.py`, `routes/va.py`, `va_commission.py`):
- `LeadEditIn`, `LeadDeleteIn` Pydantic models + `_log_lead_activity()` helper (writes to new `va_lead_activity` collection)
- `PATCH /api/pm/leads/{lead_id}` — admin edits any field; auto-renormalizes phone/email/address; reassigns commission when `va_user_id` changes (commission.va_name also follows)
- `DELETE /api/pm/leads/{lead_id}` — soft-delete (sets `deleted_at`, `deleted_by`, `deleted_reason`); idempotent; non-paid commissions auto-rejected; paid commissions LEFT INTACT
- `POST /api/pm/leads/{lead_id}/restore` — clears `deleted_at`
- `GET /api/pm/leads?trash=true|false&include_trashed=true` — Trash filter
- `GET /api/pm/leads/{lead_id}` — returns `{lead, activity, commission}`
- `PATCH /api/va/leads/{lead_id}` — VA edits OWN lead ONLY while `stage='new_lead'`; 403 otherwise; va_user_id/job_value blocked for VAs (admin-only)
- `DELETE /api/va/leads/{lead_id}` — VA soft-deletes OWN lead ONLY while `stage='new_lead'` AND no commission exists
- `GET /api/va/leads/{lead_id}` — VA detail (own only, 404 for others)
- Activity log records every stage_change, edit, delete, restore — survives even when lead is trashed (audit trail)

**Frontend**:
- `/app/frontend/src/pages/LeadDetail.jsx` (NEW, ~600 lines) — shared by admin (`/ops/va-program/pipeline/:leadId`) and VA (`/va/leads/:leadId`). Form-with-edit-mode, activity timeline with diff renderer, commission sidebar, Trash banner
- `AdminVAPipeline.jsx`: Active/Trash tabs, per-row Edit + Trash buttons, Restore button in Trash view, prospect names are blue links to detail page
- `VAMyLeads.jsx`: rows are clickable → `/va/leads/{id}` detail
- New routes registered in `App.js`: admin scope + va scope

**Tests**: `test_iter41_lead_crud.py` — 17 new tests (permission boundaries, edit + renormalize, reassign + commission move, soft-delete idempotency, restore, activity log, VA-side blocks). Regression: 24 (iter39 + iter40). **41/41 GREEN**.


## Implemented — 2026-02 (Iter 42: VA-Success Batch 2 — Six Features) — VERIFIED 50/50
**Goal**: Make every VA more effective with goals, leaderboard, pitch templates, stale-lead nudges, coaching notes, and richer dashboard analytics.

**Backend** (`/app/backend/routes/va.py`, `routes/pm.py`, `va_commission.py`):
- New models: `VAGoalIn`, `PitchTemplateIn`, `PitchTemplatePatch`, `CoachingNoteIn`, `CoachingNotePatch`. Constants: `STALE_LEAD_DAYS=7`, `STALE_LEAD_STAGES=('contacted','quoted')`
- New collections: `va_goals`, `pitch_templates`, `va_coaching_notes`
- Enhanced `GET /api/va/dashboard` — now includes `conversion_rate`, `stale_leads_count`, `paid_count`, `goal{month,target_leads,target_commission,mtd_leads,mtd_commission,note}`, `shared_notes[]`. Internally fan-out via `asyncio.gather()` so all 7 independent queries run in parallel.
- New VA endpoints: `GET /va/stale-leads`, `GET /va/leaderboard?period=week|month|all`, `GET /va/templates`, `GET /va/coaching-notes` (shared only — private leaks blocked), `GET /va/goals?months=6`
- New PM endpoints: `GET/POST /pm/va-goals/{va_user_id}` (POST with both targets null deletes), `GET/POST/PATCH/DELETE /pm/templates` (with `include_archived` and `active` toggle for soft-archive), `GET/POST/PATCH/DELETE /pm/coaching-notes/{va_user_id|note_id}`, `GET /pm/vas/{va_user_id}/detail` (combined profile + stats + month goal)

**Frontend**:
- `VADashboard.jsx` (rewritten) — stale-leads alert, monthly-goal card with progress bars, leaderboard rank card (links to leaderboard), pitch templates CTA, shared coaching notes from PM
- `VALeaderboard.jsx` (NEW) — week/month/all toggle, crown on #1, "You" badge, earnings masked
- `VATemplates.jsx` (NEW) — searchable + channel-filtered library, one-click copy to clipboard
- `AdminTemplates.jsx` (NEW) — CRUD table with new-template dialog, archive toggle, soft-delete
- `AdminVADetail.jsx` (NEW) — single page with stats + monthly-goal editor + coaching notes (private vs shared, edit-in-place, delete)
- `AdminVAs.jsx` — VA name is now a Link to `/ops/va-program/vas/{user_id}`
- `AdminVAOverview.jsx` — added "Pitch templates" and "Manage VAs · Goals · Notes" CTAs
- `VALayout.jsx` — sidebar now has Leaderboard + Templates tabs
- `App.js` — new routes: `/va/leaderboard`, `/va/templates`, `/ops/va-program/vas/:vaUserId`, `/ops/va-program/templates`

**Tests**: `test_iter42_va_success.py` (17 new) covering: dashboard payload shape + parallel queries, stale-leads with mongo-backdated leads, leaderboard period toggle + is_self flag, templates CRUD with archive + soft-delete, coaching-notes private-vs-shared privacy boundary, va_goals upsert with delete-on-null-targets, /pm/vas/{id}/detail, full permission boundaries (VA can't hit /pm/* endpoints). Regression: 33 (iter39 + iter40 + iter41). **50/50 GREEN**.




**Tests**: `test_iter40_dm_companion.py` (10 new) covering admin sends with channels, worker sends silently ignored, kill-switch gates companion path, gig_group threads bypass companion, regressions on threads list/unread/mark-read/empty-body. Combined with iter39 = **24/24 GREEN**.


## Implemented — 2026-06 (Iter 43: VA Training Playbook Page) — VERIFIED 100%
**Goal**: In-app playbook for VAs aligned with the 5 uploaded training PDFs (VA Role, Daily Operations, Marketing Outlets, Communication Scripts, Recovery Scripts).

**New page**: `/app/frontend/src/pages/va/VATraining.jsx` (433 lines, hard-coded content) — accessible at `/va/training`.

**Sections** (each with own `section-*` testid):
- The 5 required fields (yellow callout): name · phone · service type · property size · preferred date/time
- Month 1 Brand Ambassador rules (red callout): no company name/phone/website/brand assets; position as "I coordinate for a local Maryland property services team"
- Do / Do NOT side-by-side grid (20-30 messages/day, 5-10 active conversations, no holding leads, no quoting, etc.)
- Commission tier structure (3 tiers: 0/15/30 cumulative leads → unlocks $1.50/hr → $2.50/hr)
- Daily closing checklist (7 yes/no questions)
- 8 marketing outlets with collapsible Do/Don't lists: Facebook · LinkedIn · Craigslist · Nextdoor · Reddit · Yelp/Thumbtack/Angi · Google Business · Cold Email (CAN-SPAM compliant)
- 3 quick links at bottom → Templates / Submit Lead / Leaderboard

**Wired into**:
- `App.js` — `<Route path="training" element={<VATraining />} />` under `/va` block + import statement
- `VALayout.jsx` — "Training" tab (BookOpenText icon) between Templates and Messages; works on desktop sidebar and mobile drawer

**Test credentials seeded**: `va.demo@hcobcleaners.com / VaDemo2026!` (approved VA) for future testing.

**Tests**: Testing agent iter43.json — **100% frontend pass**. Verified Training tab visible, route navigates, all 7 sections render, mobile drawer has Training entry, all 6 other VA pages load clean, Submit Lead has expanded dropdowns (Routine/Deep/Move-out/Specialty/Commercial + LinkedIn/Craigslist/Nextdoor/Reddit/Yelp/Thumbtack/Angi/HomeAdvisor/Google Business/Cold Email).



## Next steps
1. **Backend modularization (P1)** — `server.py` still has ~3,378 lines: split `routes/projects.py`, `routes/va.py`, `routes/pm.py`, `routes/owner.py` (Phase 3f).
2. **Google Auth integration (P1)** via `integration_playbook_expert_v2` (Emergent-managed).
3. **Stripe auto-payouts (P2)** — VA commissions + worker payouts.
4. **Auto-blast on gig create (P3)** — hook blast system to gig creation.
5. **Automated review/rating collection (P3)** — post-gig SMS/email blast for worker ratings.
6. **VA Commission Phase 2** — stage-update email/SMS triggers, cleaner referral tracking.
7. **Security**: Resend API key currently committed to `backend/.env` — rotate + move to secret manager.
8. **Observability**: Add `logger.info` around `_send_email_sync` invocations (success/failure currently silent).


## Implemented — 2026-06 (Iter 44: Pending VA Feature Gating) — VERIFIED 100%
**Goal**: Restrict unapproved (pending/suspended) VAs from accessing revenue-generating features. User picked: keep **Dashboard, Leaderboard, Templates, Training** accessible; lock **Submit Lead, My Leads, Earnings, Messages** until PM approves.

### Backend changes
- **New dependency** `block_unapproved_va` in `/app/backend/va_commission.py` (lines ~273-285) — passes through everyone EXCEPT `va` users with status != `approved`, who get 403 with a clear message. Used for cross-role routes (e.g. messaging) where you can't just slap `require_va_active`.
- **Switched 4 endpoints** in `/app/backend/routes/va.py` from `require_va` → `require_va_active`:
  - `GET /api/va/leads` (list)
  - `GET /api/va/leads/{lead_id}` (detail)
  - `GET /api/va/earnings`
  - `GET /api/va/commercial-accounts`
- **Switched 8 messages endpoints** in `/app/backend/routes/messages.py` from `get_current_user` → `block_unapproved_va`:
  - GET /threads · GET /unread-count · POST /threads/dm · GET /threads/gig/{gig_id} · GET /threads/{thread_id} · GET /threads/{thread_id}/messages · POST /threads/{thread_id}/messages · POST /threads/{thread_id}/read · POST /attachments · GET /eligible-users

### Frontend changes
- **New guard component** `/app/frontend/src/components/va/VAApprovedGuard.jsx` — wraps locked routes; if `user.va_status !== 'approved'`, renders a polished "Locked · Pending Approval" placeholder with 3 CTAs (Training, Templates, Leaderboard). Branches copy for `suspended` vs `pending` states.
- **VALayout tabs** now carry a `requiresApproved` boolean; sidebar (desktop + mobile drawer) filters to `visibleTabs` based on `user.va_status === 'approved'`.
- **Updated yellow banner** copy: "While we review your account, you can study the Training playbook, browse Templates, and watch the Leaderboard. Submit Lead, My Leads, Earnings, and Messages unlock once your Program Manager approves you."
- **5 routes wrapped** in `<VAApprovedGuard>`: /va/submit, /va/leads, /va/leads/:leadId, /va/earnings, /va/messages.

### Tests
- Testing agent iter44 — **24/24 pytest pass** + frontend regression clean.
- New reusable test at `/app/backend/tests/test_va_pending_gate_iter44.py` covers pending vs approved across all 12 endpoints plus admin-messaging regression.
- Pending VA fixture: `va.pending@hcobcleaners.com / Pending2026!`.



## Implemented — 2026-06 (Iter 45: Worker Agreement Gate) — VERIFIED 100%
**Goal**: Workers must agree to a 3-rule checklist EVERY time they request a gig, with full legal-grade audit trail (typed name + timestamp + IP + verbatim rules) — per user choice (3 rules, every-accept frequency, audit option A).

### The 3 rules (versioned `v1`)
1. No-shows on first gigs are an automatic deletion from the platform.
2. You will be professional when on your gig site.
3. You must clock in on your shift, or you may not be paid.

Rules stored as `WORKER_AGREEMENT_RULES_V1` constant in `models.py` so bumping to v2 is a one-line change; the version is stored on every audit doc.

### Backend
- New Pydantic model `WorkerAgreementIn` (typed_name, agreed_rules, version)
- `POST /api/gigs/{gig_id}/accept` now **requires** an agreement body; validates typed_name matches `user.name` (case-insensitive, whitespace-trimmed), agreed_rules matches canonical set verbatim, version matches `v1`. On success writes a doc to `worker_agreements` collection (indices on agreement_id, worker_id, gig_id, accepted_at).
- New `GET /api/worker/agreement-rules` — returns canonical rules + version
- New `GET /api/worker/my-agreements` — worker's audit trail (worker-role gated)
- Audit doc shape: `{agreement_id, worker_id, worker_name, worker_email, gig_id, typed_name, version, rules, accepted_at, ip, user_agent}` — IP honors `x-forwarded-for` header for ingress proxy

### Frontend (`WorkerGigDetail.jsx`)
- Clicking "Request this gig" now fetches `/worker/agreement-rules` and opens a modal
- Modal shows 3 numbered rules in a clean stack, "I have read and agree to all 3 rules" checkbox, "Sign by typing your full name" input with the worker's profile name as both placeholder and validation target
- Submit button disabled until BOTH checkbox checked AND typed name matches (case + whitespace tolerant)
- "Never mind" and modal-backdrop click both close without submitting
- All data-testids in place: `worker-agreement-modal`, `worker-agreement-rule-{0,1,2}`, `worker-agreement-checkbox`, `worker-agreement-typed-name`, `worker-agreement-submit`, `worker-agreement-cancel`

### Tests
- New `/app/backend/tests/test_iter45_worker_agreement.py` — 8/8 pass
- Updated `/app/backend/tests/test_iter29_gigs_router.py` to send agreement body — 15/15 pass
- Combined regression: 47/47 pytest pass (iter45 + iter29 + iter44)
- Testing agent iter45.json: **100% backend + 100% frontend E2E**
- Test fixtures: `worker.demo@hcobcleaners.com / WorkerDemo2026!` (id_verified, profile-complete, name='Worker Demo')



## Implemented — 2026-06 (Iter 46: Admin Shift Edit from Worker Profile) — VERIFIED 100%
**Goal**: Admin can edit any shift directly from the worker profile's Gig History (per user request "I need to be able to edit shifts from worker profiles" + standard combo: edit times, cancel, no-show, mark-completed, admin note).

### Backend
- Extended `TimesheetEditIn` with `admin_note: Optional[str]` — persisted with `admin_note_at` + `admin_note_by` audit fields; empty-string unsets the note.
- New `AcceptanceNoShowIn` model + endpoint `POST /api/gigs/{gig_id}/acceptances/{acceptance_id}/no-show` — requires `reason`, optional `admin_note`. Clears clock_in/out + earnings, sets status='no_show', notifies worker via in-app notification.
- New `AcceptanceMarkCompletedIn` model + endpoint `POST /api/gigs/{gig_id}/acceptances/{acceptance_id}/mark-completed` — force-marks completion. Resolves clock_in from payload → existing acceptance → gig.scheduled_at. Resolves clock_out from payload → existing → gig.scheduled_at + duration_hours. Recomputes hours + earnings via standard pay-resolution pipeline.
- Existing DELETE endpoint reused for "Remove worker" — frees the slot, backup auto-promote handled by existing code.

### Frontend
- New component `/app/frontend/src/components/admin/ShiftEditDialog.jsx` — 3-tab modal (Edit times · No-show · Remove) with datetime-local pickers, admin-note textarea, contextual warnings, and disabled-button logic that prevents accidental destructive actions.
- `/app/frontend/src/pages/admin/WorkerDetail.jsx` — added "Edit" column with per-row `Manage` button (data-testid `shift-manage-btn-{acceptance_id}`); dialog mounts once and is driven by `editingShift` state.

### Tests
- New `/app/backend/tests/test_iter46_shift_edit.py` — 10/10 pass
- Regression: Iter45 (worker agreement) 8/8 still pass
- Testing agent iter46.json: **100% backend + 100% frontend E2E**

### Reviewer notes (non-blocking, deferred)
- `WorkerDetail.jsx` is 1182 lines — split candidates: `AdminProfileEditor`, `DefaultPayCard`, `ApplicationStatusCard`
- `ShiftEditDialog` uses custom view state instead of Radix `<Tabs>` — works visually but Radix would add keyboard a11y for free



## Implemented — 2026-06 (Iter 47: Truthful Worker Approval Gate) — VERIFIED 100%
**Goal**: An "approved" worker must genuinely be able to book a shift. Workers cannot be approved (and the green badge can't render) unless ID is uploaded + verified AND every required profile field is filled. The booking gate at `/gigs/accept` was already correct; this iteration brings the admin approval + UI badge in sync with it.

### Backend
- New helpers in `auth_deps.py`: `_worker_approval_blockers(user)` returns human-readable reasons (e.g. "ID not uploaded", "Profile incomplete (7 fields missing)"); `_worker_is_fully_active(user)` returns True only when status=approved AND ID-verified AND profile-complete.
- `_set_worker_status` in `routes/admin.py`: refuses to set status='approved' when blockers exist → returns 400 with detailed message. Affects `/approve`, `/reinstate` paths.
- `PUT /admin/workers/{id}/profile`: same guard applied to `worker_status='approved'` edits. Uses **prospective merge** so admins can fix profile fields AND set approved in ONE call (still validates the merged future state).
- All worker read endpoints (`GET /admin/workers`, `GET /admin/workers/{id}`, `PUT /admin/workers/{id}/profile`) now return `approval_blockers` and `fully_active`. Centralized enrichment ensures the badge is truthful immediately after any save.

### Frontend
- `AdminWorkers.jsx` — `StatusBadge` rebuilt to take the full worker object. Renders "ACTIVE" (green) only when `fully_active=true`. Edge case: worker_status='approved' but blockers present → "SETUP NEEDED" (yellow) instead. PENDING/REJECTED/SUSPENDED unchanged.
- `WorkerDetail.jsx` — `ApplicationStatusCard` adds a new "setup_needed" state; surfaces a bulleted **Still needed** list (data-testid `approval-blockers`); the Approve button disables with a tooltip when blockers exist.

### One-time migration
- `/app/backend/scripts/migrate_downgrade_incomplete_approvals.py` — auto-downgrades workers whose `worker_status='approved'` but who actually have blockers. **Run on preview**: examined 1,825 approved workers → downgraded 1,526 → 299 remained ACTIVE. Idempotent; safe to re-run on production after redeploy.
- **Production**: redeploy + then run `cd /app/backend && python -m scripts.migrate_downgrade_incomplete_approvals` to clean the production DB.

### Tests
- New `/app/backend/tests/test_iter47_truthful_approval.py` — 8/8 pass
- Regression: iter44 (24) + iter45 (8) + iter46 (10) = **50/50 GREEN**
- Testing agent iter47.json: **100% backend + 100% frontend E2E**



## Implemented — 2026-06 (Iter 48: Sealed the leaks — new workers default to pending) — VERIFIED 100%
**Goal**: Iter47 added the badge logic and the approval gate, but new signups were STILL flowing in as `worker_status="approved"`. Production showed 83 fresh workers in the APPROVED tab with "SETUP NEEDED" pills. Iter48 closes the remaining write paths.

### 4 write paths sealed
1. `POST /api/auth/register` — `worker_status="approved"` → **`"pending"`**
2. `POST /api/auth/oauth/google/callback` (social login) — `worker_status="approved"` → **`"pending"`**
3. Admin → worker demotion in `server.py:1028` — `worker_status="approved"` → **`"pending"`**
4. On-startup auto-migration in `server.py:1462` — already idempotent; catches any historical or "leaked" approved records on every boot. **Now redundant for net-new traffic since signups can't leak — but still defends against legacy data.**

### Tests
- New `/app/backend/tests/test_iter48_new_signups_pending.py` — 3 dedicated tests:
  - Email signup defaults to pending (response + DB check)
  - Fresh signup appears in PENDING tab, NOT in APPROVED tab (the exact regression target)
  - Fresh signup cannot be admin-approved until profile + ID complete (400 with reason)
- Combined regression: **65/65 pytest pass** across iter28, iter29, iter44, iter45, iter46, iter47, iter48.

### 🚨 Production fix path
**Redeploy once.** On the next backend boot:
1. The on-startup auto-migration sweeps the 83 currently-misleading "approved" workers → flips them to `pending`.
2. From that moment on, new signups default to `pending` (verified on preview: `worker_status: pending` in the actual register response).
3. The APPROVED tab will only ever contain truly bookable workers.

No SSH, no manual scripts, no database migration commands needed beyond the existing auto-migration.



## Implemented — 2026-06 (Iter 49: Workers Search Bug — `$or` collision) — VERIFIED 100%
**Goal**: Fix the broken search box on `/ops/workers` where typing "Cory" returned every approved worker (not just Cory).

### Root cause
`GET /admin/workers` builds the MongoDB filter by stacking multiple `$or`-style conditions (status back-compat, vehicle="any", free-text search) into a SINGLE `$or` key. MongoDB treats those as DISJUNCTS — so the query for "approved + Cory" actually said *"`worker_status=approved` OR `worker_status` missing OR `name~Cory` OR `email~Cory` OR `phone~Cory`"*. Every approved worker matched on the status clause regardless of the search term.

### Fix
Refactored the query builder in `/app/backend/routes/admin.py` (lines 82-145) to collect each disjunctive filter as a separate `or_blocks` entry, then combine them at the end:
- 0 blocks → no $or
- 1 block → top-level `$or`
- 2+ blocks → wrap in `$and: [{$or: ob1}, {$or: ob2}, ...]` so each block is independently required

### Tests
- New `/app/backend/tests/test_iter49_workers_search.py` — 5 dedicated tests:
  - Search alone returns only matches
  - Search + status intersects (regression target)
  - Search by phone with status
  - Status alone still returns the full set
  - Search + status + vehicle="any" — three disjunctive filters all AND together
- Combined regression: **89/89 backend pytest pass** (iter28/29/44/45/46/47/48/49)

### 🚨 Production
Redeploy once. Search will work correctly across all workers, all status tabs.



## Implemented — 2026-06 (Iter 50: Founder Welcome Email) — VERIFIED 100%
**Goal**: Send a one-shot founder-voiced welcome email when a new worker signs up. User explicitly chose welcome-only (no 24h/72h reminder cadence).

### Backend
- New helper `send_worker_welcome_email(user)` in `/app/backend/notifications.py` — renders a personalized HTML email from Cory (founder), with a CTA pushing the worker to `/crew/profile` to finish setup.
- Wired into both signup write paths:
  1. `POST /api/auth/register` (email signup) — fires `asyncio.create_task(send_worker_welcome_email(user))` after session is issued
  2. `POST /api/auth/google/session` (Google OAuth) — fires only on `is_new=True` so existing users don't get re-greeted on every login
- Errors are logged inside `_send_user_email` and never raised — registration always succeeds even if Resend is down.
- Email layout uses the standard `_email_layout` template, branded "HCOB Network" header.

### Email content (Cory's verbatim message, light cleanup)
> Hey [first name], my name is **Cory**, and I'm the founder of The HCOB Network. I created this platform to bring value to customers and more opportunities to smaller businesses — established and non-established alike. Either way, we structure the unstructured. There are so many talented professionals in Baltimore, and we want to bring amazing people like you the work you deserve. Thank you for signing up.
>
> *Quick next step*: Finish your profile and upload a photo of your ID. The moment those are in, we'll review and activate your account so you can start claiming shifts.

Subject: `Welcome to The HCOB Network, [first name]`

### Tests
- `/app/backend/tests/test_iter50_welcome_email.py` — 4/4 pass:
  - HTML body contains Cory's introduction + Baltimore + "structure the unstructured"
  - Empty-name fallback ("Hey there,")
  - register() endpoint imports and calls the welcome function
  - google_session() endpoint imports and calls it only for new users
- Full regression: 38 tests across iter45/46/47/48/49/50 pass

### 🚨 Production
Already redeployed (per prior iterations). The email will send automatically on production via your Resend creds (in preview the API key is invalid so emails are logged-as-skipped without crashing).



## Implemented — 2026-06 (Iter 51: Worker Feed Cleanup — Full Date + Filters/Sort) — VERIFIED
**Goal**: Workers see the full date AND time of every gig, with a powerful filter/sort bar across all worker-facing feeds (Open gigs feed + My Gigs).

### New components / helpers
- `formatGigFull(gig)` in `/app/frontend/src/lib/gigDate.js` — e.g. "Today · Thu, Jun 18, 2026 · 10:25 AM – 2:25 PM". Adds Today/Tomorrow word prefix where applicable.
- New shared component `/app/frontend/src/components/worker/FeedFilters.jsx` — reusable across any worker feed:
  - **Sort**: Newest · Soonest start · Highest pay · Closest (zip)
  - **Filters**: Category · When (Today / Tomorrow / This week / Next 7d / Next 30d) · Minimum pay ($) · ZIP starts with · Rush only · Open slots only
  - Active-filter **chips** with one-tap clear + "Clear all"
  - **Result count** ("42 / 466 SHOWN")
- New `applyFeedFilters(gigs, filters, workerZip)` pure helper — single source of truth for filter+sort logic. Used by both feeds for identical semantics.

### Pages updated
- `/app/frontend/src/pages/worker/WorkerFeed.jsx` — replaced single-category Select with FeedFilters; full date now shown on every card.
- `/app/frontend/src/pages/worker/WorkerAccepted.jsx` ("My Gigs") — same FeedFilters bar; defaults sort to "Soonest start" since these are the worker's own upcoming commitments.

### Notes
- Filtering is client-side. The /gigs endpoint already returns up to 500 gigs ordered by rush/created_at — instant filter response, no extra round trip.
- Mobile-first layout: filter bar collapses to a single row; expanded panel uses native select elements (best mobile UX).
- 33/33 backend regression tests pass (iter29 + iter45 + iter46) — no API surface changed.



## Implemented — 2026-06 (Iter 52: Slot Overbooking — Atomic Reservation) — VERIFIED 100%
**Bug**: Production showed a 4-slot gig with 5 approved workers. Root cause: classic check-then-update race condition.

### Root cause
The 4 endpoints that grew `slots_filled` (`approve_request`, `approve_request_as_backup`, `assign_worker`, plus the corresponding decrement on `remove_worker_from_gig`) did:
```python
filled = gig.slots_filled        # read
if filled >= slots: raise 400    # check
gig.slots_filled = filled + 1    # write
```
Two concurrent admin clicks (or one double-click) could both read `slots_filled=3`, both pass the check, both write `4` — overbooking by 1 silently. Five clicks racing could overbook by more.

### Fix
Replaced check-then-update with **single atomic `find_one_and_update`** using `$expr: {$lt: [slots_filled, slots]}` as a filter. Only the request whose write commits the increment "wins"; concurrent losers get `None` back and immediately return 400.
```python
reserved = await db.gigs.find_one_and_update(
    {"gig_id": gig_id, "$expr": {"$lt": [{"$ifNull": ["$slots_filled", 0]}, {"$ifNull": ["$slots", 1]}]}},
    {"$inc": {"slots_filled": 1}},
    return_document=ReturnDocument.AFTER,
)
if not reserved: raise HTTPException(400, "All slots filled")
```
Plus **rollback compensation** on acceptance-write failures — `try/except` wraps the acceptance update; if it raises, we `$inc -1` the gig counter so the system never wedges above truth.

Same pattern applied to:
- `POST /gigs/{id}/requests/{aid}/approve` (primary slot)
- `POST /gigs/{id}/requests/{aid}/approve-backup` (backup slot)
- `POST /gigs/{id}/assign` (admin direct assignment)
- `DELETE /gigs/{id}/acceptances/{aid}` (decrement on removal — now `$inc -1` with `slots_filled > 0` guard)

### Data healing
New `on_startup` task in `server.py` — **slot-count reconciliation**. Walks every gig, recomputes `slots_filled` from actual `gig_acceptances.count_documents({status: accepted|on_the_clock|completed})`, and writes only when they differ. Heals any historical drift from the pre-Iter52 race. Idempotent — re-runs are no-ops on clean data. Also reconciles the `status='filled'` flag.

**On production redeploy**: the boot task will surface every historically-overbooked gig with the correct counter (e.g. the screenshotted gig will display `5/4 filled` instead of misleading `4/4 filled` with 5 names — admin can then remove one to restore truth).

### Tests
- New `/app/backend/tests/test_iter52_slot_overbooking.py` — 4 dedicated tests:
  1. **Serial cap** — 5 requests + 4 slots → 4 succeed, 5th gets 400
  2. **Concurrent cap** — 5 ThreadPoolExecutor threads against a 3-slot gig → **EXACTLY 3 succeed**
  3. **Remove releases the slot** — removing a worker frees their spot for a queued approval
  4. **Reconciliation idempotent** — running over a clean gig changes nothing
- Combined regression: **53/53 backend pytest pass**



## Implemented — 2026-02 (Iter 53: Payout Method Collection + Background Reminders) — VERIFIED 11/11

**Goal**: Collect worker payout details (Zelle / Apple Cash / Chime) in their profile WITHOUT blocking gig acceptance. Pair it with two background email cadences — a 24h shift reminder and a 3-day / 7-day "add your payment info" nudge for workers who never set a payout method.

### Backend
- **Model** (`models.py`): `ProfileUpdateIn` gains `payout_method: Literal["zelle"|"apple_cash"|"chime"]` + `payout_handle: str`. A `field_validator` coerces incoming `""` → `None` so the frontend can clear the method without tripping the Literal validator (which would otherwise return 422).
- **Route** (`routes/profile.py`):
  - PUT `/api/profile` peeks at the raw JSON body (`await request.json()`) to detect a `payout_method: ""` clear-intent — since `exclude_none=True` would otherwise drop the cleared field. When clear-intent fires, both `payout_method` and `payout_handle` are nulled.
  - Sending `{payout_method: "zelle"}` without a handle (or with an empty handle in the same payload) returns **400** — handle is required when a method is being set.
  - Setting a method stamps `payout_updated_at` (ISO UTC).
  - **Never blocks gig acceptance** — payout fields are purely informational.
- **Reminders daemon** (`reminders.py`, new):
  - Single coroutine `reminders_runner()` started in `server.py` `on_startup`; sleeps 60s, then loops every 10min.
  - **Shift pass**: scans `gigs` whose `scheduled_at` is 23-25h from now; for each active acceptance (`accepted` or `on_the_clock`), looks up the dedupe key `shift_24h::{acceptance_id}` in the new `reminder_log` collection. If unseen, sends a Resend email reminding the worker of when/where/pay + a "clock in!" callout, then upserts the key.
  - **Payment-info pass**: for each tier (`payment_3d` at +3d, `payment_7d` at +7d), finds workers with no `payout_method` whose `created_at <= now - tier_delta` and `worker_status not in (rejected, suspended)`. Sends a short email with a CTA back to `/crew/profile`. Dedupes via `{tier}::{user_id}` keys so each tier sends at most once per worker.
  - Graceful degradation — if Resend isn't configured, `_send_user_email` no-ops and the reminder is logged so we don't retry forever.

### Frontend
- `WorkerProfile.jsx`: new "Payment information" section between phone and emergency contact. Method dropdown (Zelle/Apple Cash/Chime/None) drives the handle field's label, placeholder, and `inputMode`. The card never gates anything else — workers can clear or change anytime.

### Tests
`/app/backend/tests/test_iter53_payouts_reminders.py` — **11/11 pass**:
- Set/clear Zelle, Apple Cash, Chime
- Invalid method rejected (422 — Literal)
- Method without handle rejected (400 — manual validation)
- Clearing resets both fields (200)
- `/auth/me` echoes the saved payout
- `reminder_log` dedupe is idempotent
- Shift + payment passes run without errors (smoke)
- Shift reminder dedupe key prevents double-send

### Files touched
- `/app/backend/models.py` — `ProfileUpdateIn` gains payout fields + `field_validator`
- `/app/backend/routes/profile.py` — raw-body peek for clear-intent
- `/app/backend/reminders.py` — new (~200 lines)
- `/app/backend/server.py` — `asyncio.create_task(reminders_runner())` on startup
- `/app/frontend/src/pages/worker/WorkerProfile.jsx` — payment section UI
- `/app/backend/tests/test_iter53_payouts_reminders.py` — 11 tests


## Implemented — 2026-02 (Iter 54: Startup Refactor — `startup.py`) — VERIFIED

**Goal**: `server.py`'s `@app.on_event("startup")` had grown to 313 lines of intertwined concerns — Mongo indices, legacy backfills, idempotent seeds, env-var failsafes, and background-task kickoff. Moved everything into a focused `startup.py` module.

### New file `/app/backend/startup.py` (373 lines)
Four ordered phases, each idempotent and individually testable:

1. **`ensure_indices()`** — all Mongo indices (users, sessions, gigs, acceptances, worker_agreements, messenger, projects, blast_logs, password reset tokens, VA commission program).
2. **`run_migrations()`** — legacy backfills + healing passes:
   - `_backfill_gigs()` — `is_rush`, `tags`, `break_minutes`, `payment_timeline`, `project_id`.
   - `_backfill_scheduled_local()` — derive wall-clock string from UTC `scheduled_at` for pre-Iter34 docs.
   - `_migrate_truthful_approvals()` — downgrade any historically-approved worker with unresolved blockers (Iter47 data healing).
   - `_reconcile_slot_counts()` — rebuild `slots_filled` / `backups_filled` / `status` from actual acceptance docs (Iter52 race healing).
3. **`seed_accounts_and_templates()`** — idempotent seeds:
   - `_seed_pitch_templates()` — auto-runs when active count < 50.
   - `_seed_admin()` — legacy GigBlast admin (env-var rotatable).
   - `_owner_reset_failsafe()` — `OWNER_RESET_EMAIL` + `OWNER_RESET_PASSWORD` boot-time lockout recovery.
   - `_seed_hcob_owner_and_pm()` — Owner flag on `admin@hcobcleaners.com` + Mechie PM seed.
4. **`start_background_tasks()`** — `_message_digest_runner` + `reminders_runner` via `asyncio.create_task` with lazy imports to avoid circular import.

### server.py: 1,649 → 1,351 lines (-298, -18%)
`@app.on_event("startup")` is now a 19-line orchestrator that calls the 4 phases in order with `init_storage()` sandwiched between phase 3 and 4. The intent of each phase is now visible from the function name; the implementation is a click away in `startup.py`.

### Verified
- Backend boots clean — startup logs show `Object storage initialized` and zero errors
- `admin@hcobcleaners.com` (Owner) and `mechiebadlong77@gmail.com` (PM) login + flags both confirmed via curl
- 27/27 regression tests pass across iter48/49/50/52/53 (workers search, welcome emails, slot overbooking, payouts/reminders, pending defaults)
- Zero behavior change — pure code organization

### Files touched
- `/app/backend/startup.py` — NEW
- `/app/backend/server.py` — `on_startup` slimmed to a 19-line orchestrator


## Implemented — 2026-02 (Iter 54 — follow-up to Iter 53: Production bugs) — VERIFIED 18/18

User reported 3 issues with the payment-info reminder email sent in production:

### Bug 1: Email link pointed to preview URL instead of hcobnetwork.com
**Root cause**: Production env still had `PUBLIC_BASE_URL=https://work-connect-147.preview.emergentagent.com` (legacy from preview). `_resolve_public_base()` honored it blindly.
**Fix**: `notifications._resolve_public_base()` now detects preview hostnames (`preview.emergentagent.com`, `emergent.host`, `preview.emergent`) in `PUBLIC_BASE_URL` and skips them — falls through to the canonical `https://hcobnetwork.com`. The user can override with any non-preview URL via env var.

### Bug 2: "Add payment method" CTA went to blank page
**Root cause**: Both `reminders.py` and `notifications.py` linked to `/crew/profile` — but the worker profile route is `/crew/me`. Clicking the button landed on a non-route and the React Router fell through.
**Fix**: Both files now use `/crew/me`.

### Bug 3: Admin couldn't see the payment data workers submitted
**Root cause**: `AdminProfileUpdateIn` didn't include payout fields, so the admin's WorkerDetail editor neither displayed nor persisted them.
**Fix**:
- Backend `AdminProfileUpdateIn` gains `payout_method` + `payout_handle`. The admin route now validates (zelle/apple_cash/chime), enforces handle-when-method-set, handles `""` clear-intent, and stamps `payout_updated_at`.
- Frontend `WorkerDetail.jsx` gains a "Payment information" section above Emergency Contact — method dropdown + dynamic-label handle input + "Last updated" timestamp.
- `fromWorker()` initializer picks up `payout_method`/`payout_handle` from the worker doc so the section pre-populates with whatever the worker entered.

### Tests
`/app/backend/tests/test_iter54_payout_admin_and_links.py` — **7/7 pass**:
- `test_resolve_public_base_skips_preview_url` (4 env combos)
- `test_email_cta_url_uses_crew_me_not_crew_profile` (source-grep guard against regression)
- `test_admin_can_set_worker_payout`
- `test_admin_can_clear_worker_payout`
- `test_admin_invalid_method_rejected`
- `test_admin_method_without_handle_rejected`
- `test_admin_payout_visible_in_worker_response` (GET /admin/workers/{id} returns the payout)

**Combined regression with iter53: 18/18 pass.**

### Files touched
- `/app/backend/notifications.py` — `_resolve_public_base` preview-URL skip; welcome email link `/crew/profile` → `/crew/me`
- `/app/backend/reminders.py` — payment reminder CTA `/crew/profile` → `/crew/me`
- `/app/backend/routes/admin.py` — `AdminProfileUpdateIn` + validation block for payout fields
- `/app/frontend/src/pages/admin/WorkerDetail.jsx` — new Payment Information section + `fromWorker()` payload
- `/app/backend/tests/test_iter54_payout_admin_and_links.py` — 7 tests

### Action required from user on production
Production needs a redeploy to pick up the code fixes (links + admin endpoint). After redeploy:
- Recommended (optional): set `PUBLIC_BASE_URL=https://hcobnetwork.com` in production env (or remove the variable entirely — the fallback now defaults to it).
- Existing reminder emails already sent will still contain the broken `/crew/profile` link; the fix only applies to emails sent after redeploy.


## Implemented — 2026-02 (Iter 55: "Missing Payout" Filter + Dashboard Strip) — VERIFIED 21/21

**Goal**: Surface a one-click answer to "Who can't I pay yet?" so admin doesn't chase payouts blind on payday.

### Backend
- `GET /api/admin/workers?payout_status=missing|set` — server-side filter on whether `payout_method` is set. Garbage values are ignored (no 400) so the filter is forgiving.
- `GET /api/admin/stats` returns a new `missing_payout` integer — workers who are `role=worker`, not `rejected|suspended`, and have no `payout_method`.

### Frontend
- **AdminWorkers (`/ops/workers`)**:
  - New "Missing payout" amber toggle pill next to "Available now" (`data-testid="filter-payout-missing"`).
  - Toggle state auto-syncs from `?payout_status=missing` URL param so deep-links work.
  - Each worker card shows a `NO PAYOUT` amber badge or a `ZELLE / APPLE CASH / CHIME` green badge (with method + handle in tooltip).
- **AdminDashboard (`/ops`)**: Amber strip "X workers missing a payout method — you can't pay them yet" with one-click "See list →" CTA that opens the filtered roster (`data-testid="dashboard-missing-payout-strip"`).

### Tests
`/app/backend/tests/test_iter55_missing_payout_filter.py` — **3/3 pass**:
- `test_stats_includes_missing_payout_count` — endpoint returns an integer
- `test_workers_filter_missing_payout` — set/clear cycle moves a worker between missing/set lists
- `test_payout_filter_invalid_value_is_ignored` — garbage value is no-filter, not 400

**Combined regression with iter53+54: 21/21 pass.**

### Files touched
- `/app/backend/routes/admin.py` — `payout_status` query param + `missing_payout` stat
- `/app/frontend/src/pages/admin/AdminWorkers.jsx` — filter pill + per-card payout badges
- `/app/frontend/src/pages/admin/AdminDashboard.jsx` — payout-missing dashboard strip
- `/app/backend/tests/test_iter55_missing_payout_filter.py` — 3 tests


## Implemented — 2026-02 (Iter 56: Mass Email Blast) — VERIFIED 8/8 (45/45 combined)

**Goal**: A proper "send a mass email to any slice of the workforce" tool. Templates as the easy path, full custom for power use. Email-only (Resend). 3-step UX with all the safeguards.

### Backend
- New routes file `/app/backend/routes/admin_blasts.py`
- `GET /admin/email-templates` — 5 built-in templates: `payout_request`, `profile_complete`, `id_upload`, `shift_availability`, `custom`
- `POST /admin/email-blast/preview` — accepts audience filters, returns `{count, preview: [{user_id, name, email}, ...first 5]}`
- `POST /admin/email-blast/send` — with `test_only=True` sends ONE copy to the admin; with `test_only=False` sends to the full audience honoring cooldown
- Refactored `routes/admin.py` to expose a shared `_filter_workers()` helper — both `/admin/workers` AND the blast composer use it, so audience preview matches the Workers page 1:1 (no drift)
- New `id_status` filter (`missing` | `submitted` | `verified`) added to both endpoints

### Safeguards (all 4 requested)
1. **3-day per-template, per-worker cooldown** — `email_blast_log` collection keyed by `{template_key, user_id}`. Logged even on Resend-failed attempts to prevent retry storms
2. **Preview before send** — `/preview` shows recipient count + first 5 names/emails; live-updates as filters change (debounced 350ms)
3. **Test send to admin** — `test_only=True` route doesn't write to cooldown log
4. **Global kill-switch** — `is_blast_disabled()` (Settings → Blast Kill Switch) returns 503

Plus: `bypass_cooldown=True` admin override for emergency reminders.

### Frontend
- New page `/app/frontend/src/pages/admin/AdminEmailBlast.jsx` at `/ops/email-blast`
- 3-step wizard: Audience → Compose → Review & send
- Step 1: full audience builder mirroring the Workers page (status, payout, ID, profile-complete, skills, availability, ZIP, vehicle, rating, search). Live preview pane on the right
- Step 2: template picker, subject + body (HTML + merge tags: `{{first_name}} {{name}} {{email}}`), optional CTA label + path. Live email preview rendered with sample recipient
- Step 3: final preview + safety-check checklist + "Send test to me" + bypass-cooldown toggle + big green Send button
- Sidebar nav: added "Email Blast" entry with `PaperPlaneTilt` icon between Messages and Reports
- Dashboard strip: now has "See list →" AND "Email them →" buttons (the second routes straight to `/ops/email-blast?payout_status=missing` with the audience pre-applied)

### Tests
`/app/backend/tests/test_iter56_email_blast.py` — **8/8 pass**:
- list templates
- preview returns count + first 5
- preview honors payout-missing filter (missing + set + everyone counts add up)
- test send doesn't log cooldown
- invalid `cta_path` (no leading slash) → 400
- empty audience → 400
- subject min-length validation → 422
- cooldown: send twice with same template → second is skipped; bypass_cooldown reattempts

**Combined regression**: 45/45 pass (iter48/49/50/52/53/54/55/56). Patched iter50 test that was still referencing the old `/crew/profile` route.

### Files touched
- `/app/backend/routes/admin_blasts.py` — NEW (~270 lines)
- `/app/backend/routes/admin.py` — extracted `_filter_workers()` helper + `id_status` filter
- `/app/backend/startup.py` — `email_blast_log` indices
- `/app/backend/server.py` — register `admin_blasts_router`
- `/app/frontend/src/pages/admin/AdminEmailBlast.jsx` — NEW (~830 lines, 3-step wizard)
- `/app/frontend/src/pages/admin/AdminDashboard.jsx` — "Email them →" CTA on missing-payout strip
- `/app/frontend/src/components/admin/AdminLayout.jsx` — Email Blast sidebar entry
- `/app/frontend/src/App.js` — route registration
- `/app/backend/tests/test_iter56_email_blast.py` — 8 tests
- `/app/backend/tests/test_iter50_welcome_email.py` — patched `/crew/profile` → `/crew/me`

## Implemented — 2026-02 (Iter 57: Landing revamp + Gigs → Assignments rename) — VERIFIED 40/40 regression

### Goal
Reposition `hcobnetwork.com` from "gig platform" to "managed contractor network led by Cory Clarke". Rename "gigs → assignments" across UI/UX. Contractor-facing only (customers go to `/customers` directly).

### Landing page — full rewrite (`Landing.jsx`)
- **Hero**: "A structured team for any scope. **Led by Cory Clarke.**" (blue accent on founder name)
- **Subhead**: "HCOB Network isn't a gig app. It's a managed contractor network — where vetted professionals get plugged into real projects, not just same-day work."
- **Founder credit card**: Quote "This is more than a side hustle. It's a structured professional network." — Cory Clarke, Owner · Founder · Project Manager
- **Service lines** (right column): Commercial cleaning programs · Project staffing & labor · Multi-service projects · Same-day assignments (positioned as the floor, not the ceiling)
- **Why join** (4 cards): "On a team, not in a queue" · "Larger scope = larger checks" · "Real project management" · "Paid right after the work"
- **Live feed**: renamed to "What the network is working on right now" — reframed as routed-through-network, not classified ads
- **3-step joining** with icons: Apply → Get vetted → Get assignments
- **Removed**: customer-strip bar at the top (customers have their own page at `/customers`); "Find gigs from HCOB Cleaners" framing; "Join the crew" CTAs replaced with "Apply to join the network"
- **Marquee**: COMMERCIAL CLEANING · POST-CONSTRUCTION · MOVE-OUTS · PROJECT STAFFING · WAREHOUSE · MULTI-SERVICE · RUSH RESPONSE

### Rename: Gigs → Assignments (Hybrid scope)
**UI labels + frontend route paths only — backend `/api/gigs` unchanged for PWA / deployed-cache safety.**

- **Canonical routes**:
  - `/crew/gigs/:id` → `/crew/assignments/:id`
  - `/crew/my-gigs` → `/crew/my-assignments`
  - `/ops/gigs` → `/ops/assignments`
  - `/ops/gigs/:id` → `/ops/assignments/:id`
- **Legacy redirects** preserved so existing emails / bookmarks / PWA caches still work:
  - `/crew/gigs/:id`, `/crew/my-gigs`, `/app/gigs/:id`, `/app/accepted`, `/ops/gigs`, `/ops/gigs/:id`, `/admin/gigs`, `/admin/gigs/:id` — all 301-style redirect to the new canonical paths

- **Visible UI text swapped** in:
  - Worker sidebar: "My gigs" → "My work"
  - Admin sidebar: "Gigs" → "Assignments"
  - Worker Feed h1: "Open gigs" → "Open assignments"
  - Worker Accepted h1: "My gigs" → "My assignments"
  - Admin Gigs page h1 + "New gig" button + empty state copy
  - Admin Dashboard "Recent gigs" + "New gig" CTA
  - Admin Calendar "New gig" button + Stat labels
  - Admin Reports "Gigs" tab label + blurb
  - Worker Detail history table header
  - Push toggle copy ("new assignment hits the feed")
  - Project dialogs ("pre-fill new assignments")
  - GigDetail pending-requests copy
  - WorkerProfile profile-blocked copy
  - Project detail "Add new assignment" CTAs

- **Internal identifiers preserved** to avoid breakage:
  - `gig_id` field name (DB + API)
  - `/api/gigs/*` API paths
  - Component names: `GigDetail`, `CreateGigDialog`, `EditGigDialog`, `AdminGigs`, etc. (renaming is a separate refactor)
  - Helper modules: `gigTags`, `gigDate`, `formatGigShort`
  - Variable names: `gigs`, `setGigs`, etc.

### Verified
- Landing page renders correctly with new hero + founder credit + service lines (screenshot)
- Lint passes on Landing.jsx + App.js
- 40/40 backend regression tests pass (iter48–56)

### Files touched
- `/app/frontend/src/pages/Landing.jsx` — REWRITE (~500 lines)
- `/app/frontend/src/App.js` — canonical assignment routes + legacy redirects
- `/app/frontend/src/components/worker/WorkerLayout.jsx` — sidebar "My work"
- `/app/frontend/src/components/admin/AdminLayout.jsx` — sidebar "Assignments"
- `/app/frontend/src/components/worker/PushNotificationToggle.jsx` — copy
- `/app/frontend/src/components/admin/CreateGigDialog.jsx` — "Post a new assignment"
- `/app/frontend/src/components/admin/CreateProjectDialog.jsx` — copy
- `/app/frontend/src/components/admin/EditProjectDialog.jsx` — copy
- `/app/frontend/src/pages/worker/WorkerFeed.jsx` — h1 + verification copy + nav
- `/app/frontend/src/pages/worker/WorkerAccepted.jsx` — h1 + nav
- `/app/frontend/src/pages/worker/WorkerGigDetail.jsx` — "Assignment complete"
- `/app/frontend/src/pages/worker/WorkerProfile.jsx` — copy
- `/app/frontend/src/pages/worker/WorkerProjectPage.jsx` — nav
- `/app/frontend/src/pages/admin/AdminGigs.jsx` — h1 + button + empty state + nav (all)
- `/app/frontend/src/pages/admin/GigDetail.jsx` — nav (all) + copy
- `/app/frontend/src/pages/admin/AdminCalendar.jsx` — Stat labels + button + nav (all)
- `/app/frontend/src/pages/admin/AdminDashboard.jsx` — labels + button + nav (all)
- `/app/frontend/src/pages/admin/AdminProjectDetail.jsx` — nav (all) + CTAs
- `/app/frontend/src/pages/admin/AdminRequests.jsx` — nav (all)
- `/app/frontend/src/pages/admin/AdminReports.jsx` — labels + blurb
- `/app/frontend/src/pages/admin/WorkerDetail.jsx` — table header
- `/app/frontend/src/pages/PublicGigPage.jsx` — nav (all)
- `/app/frontend/src/pages/Messages.jsx` — assignment-link nav

### Not yet done (intentionally deferred to keep this safe)
- Component file renames (`CreateGigDialog` → `CreateAssignmentDialog`, etc.) — pure cosmetic, doesn't affect users
- Internal variable name renames (`gigs` → `assignments` in React state)
- DB collection rename (would require migration; PWA caches would break)
- `/api/gigs` endpoint rename (would break the deployed PWA on workers' phones until they reinstall)


## Implemented — 2026-02 (Iter 58: VA Lead Pipeline — Phase 1 of "make VAs successful") — VERIFIED 8/8

**Goal**: Stop leads from rotting. Give VAs a Kanban view of every lead they own with a response-time SLA timer on every card, and give the Program Manager a coachable view of who's letting deals age out.

### Phase 1 scope (shipped)
**Kanban board** at `/va/leads` (replaces the old flat list)
- 4 columns: **New · Contacted · Quoted · With Ops** (booked/completed/lost lumped into one read-only "With Ops" column)
- Each card: prospect name, tap-to-call phone, tap-to-email, service type, **SLA countdown badge** (ok/hot/stale), tap-to-move dropdown, inline notes textarea (saves on blur)
- VAs control soft pipeline (`new_lead → contacted → quoted`); hard outcomes (`booked/completed/paid/lost`) remain admin-only for commission integrity

**SLA windows** (hardcoded; future: settings-driven):
- `new_lead`: 24h to make first contact
- `contacted`: 48h to send a quote
- `quoted`: 72h to close the loop
- At 80% of the window: **hot** (amber, animated pulse). At 100%: **stale** (red, "Xh overdue")
- SLA timers refresh every 30s without re-fetching

### Backend (3 new endpoints in `routes/va.py`)
- `GET /api/va/pipeline` — every non-deleted lead the VA owns, decorated with `sla_state`, `hours_in_stage`, `sla_hours`, `sla_due_at_iso`. Returns `stages_va_can_move` so the frontend stays decoupled from the soft/hard split.
- `PATCH /api/va/leads/{lead_id}/stage` — VA-only soft-stage move. Rejects hard stages with 400 + helpful message ("Bookings are set by your Program Manager"). Writes `stage_history` + activity log.
- `PATCH /api/va/leads/{lead_id}/notes` — dedicated notes endpoint that works at ANY stage. Crucial because the strict edit endpoint locks at `new_lead` — without this VAs would lose the ability to add notes once they hit contacted.

### Frontend (`VAMyLeads.jsx` — full rewrite)
- 4-column Kanban grid that collapses to single-column on mobile
- Per-column "Hot count" badge (e.g. "3 hot")
- LeadCard component: header (name + open-detail caret), contact links (phone/email), SLA badge, move dropdown, inline notes textarea with dirty-state + save-on-blur
- SLA timer state managed locally — re-renders every 30s via `setInterval` tick
- Mobile-first: tap-to-move via `<select>` works without drag/drop infra

### Tests
`/app/backend/tests/test_iter58_va_pipeline.py` — **8/8 pass**:
- pipeline endpoint returns expected shape (items + stages_va_can_move + sla_hours)
- pipeline decorates each lead with SLA state
- VA can move through soft stages (and back)
- VA cannot move to hard stages (booked/completed/paid/lost/bogus → 400)
- notes endpoint works at any stage (including post-`new_lead`)
- notes 4000-char limit enforced
- 404 on unknown lead
- admin can flip to terminal stage; VA pipeline returns it with `sla_state=null`

**Combined regression: 37/37 across iter53–58.**

### Files touched
- `/app/backend/routes/va.py` — `VA_PIPELINE_STAGES`, `VA_LEAD_SLA_HOURS`, `_lead_sla_status()`, 3 new endpoints
- `/app/frontend/src/pages/va/VAMyLeads.jsx` — REWRITE: 4-column Kanban + LeadCard + inline notes
- `/app/backend/tests/test_iter58_va_pipeline.py` — 8 tests

### Phase 2/3/4 (queued, not built yet)
- **Phase 2**: AI Objection Coach — tap "Handle objection" on a card, LLM returns 3 on-brand responses using existing templates as context
- **Phase 3**: Earnings ticker + monthly goal bar on VA Dashboard (money-on-the-screen motivation)
- **Phase 4**: Private coaching notes per VA + cohort-filtered leaderboard ("VAs who joined in last 90 days")


## Implemented — 2026-02 (Iter 59: AI Objection Coach — Phase 2 of "make VAs successful") — VERIFIED 7/7

**Goal**: Turn every objection into a learning moment. VA taps "Handle objection" on a lead card, picks a common objection (or types a custom one), and Claude returns 3 distinct, on-brand response options the VA can copy-paste into SMS/email/DM.

### Backend (`routes/va_objection_coach.py`, new)
- `GET /api/va/objection-coach/objections` — returns the 7 quick-pick objections + the per-hour rate limit
  - `too_expensive`, `have_someone`, `call_back`, `not_now`, `trust`, `ghost`, `spouse`
- `POST /api/va/leads/{lead_id}/objection-coach` — main coach endpoint
  - Input: `{objection_key}` OR `{custom_text}` (max 500 chars)
  - Pipeline:
    1. Resolve objection → human-readable label
    2. Look up lead (must be owned by caller VA, not deleted)
    3. Rate-limit check: 20 calls per VA per hour (via `va_objection_calls` collection)
    4. Pull up to 6 relevant pitch templates (objection-handling + service-matched) for LLM tone context
    5. Build the prompt with VA's first name, service type, property size, lead notes, template context
    6. Call **Claude Sonnet 4.6** via emergentintegrations + EMERGENT_LLM_KEY
    7. Tolerant JSON extraction (strips ```json fences, finds first/last brace)
    8. Trim to 3 responses · sanitize (angle ≤120 chars, body ≤1200)
    9. Log to `va_objection_calls` for rate-limiting + cost-tracking
    10. Log activity on the lead so PM can see "this VA used the coach 4 times on this prospect"
  - Returns `{responses: [{angle, body}, ...3], objection_label, calls_used_last_hour, rate_limit_per_hour}`

### Frontend (`components/va/ObjectionCoach.jsx`, new)
- Full-screen modal (bottom-sheet on mobile)
- **Header**: blue bar with Sparkle icon + prospect name
- **Step 1**: Quick-pick chips (7 objections) + free-form textarea
- **Step 2**: Three response cards, each with:
  - Angle label (e.g. "Value reframe — anchor to outcome, not cost")
  - The response body, whitespace-preserved
  - Character count + "fits in a text message" hint
  - One-tap Copy button (turns green ✓ on copy, restores after 2s)
- "Try a different objection" reset link
- Calls-used counter ("4/20 coach calls used this hour")
- AI-disclaimer banner ("read once before sending, don't quote prices unless confirmed with Ops")

### VAMyLeads.jsx — wiring
- New "Handle objection ✨" button at the bottom of every active lead card (`data-testid="open-coach-{lead_id}"`)
- Only renders on soft-pipeline leads (hidden on "With Ops" terminal cards — the coach is for moving deals forward, not autopsying lost ones)
- Modal state lives per-card so multiple coaches can be active across the board

### Tests
`/app/backend/tests/test_iter59_objection_coach.py` — **7/7 pass**:
- structural: list endpoint, unknown key rejection (400), missing input rejection (400), 404 on bad lead, custom_text >500 chars rejected (422)
- **live LLM**: end-to-end objection_key call returns 1–3 well-formed responses with angle+body, usage counter increments
- **live LLM**: custom_text path works (label reflects the user's wording)

**Combined regression: 44/44 across iter53–59.**

### Cost & rate-limit notes
- 20 coach calls per VA per hour. Generous for real use (typical VA might use 2–5/day), hard ceiling against runaway/abuse
- Each call ≈ 1.5–2k input tokens (system + templates) + ≈500 output tokens. With Claude Sonnet 4.6 on the universal key that's well under $0.05/call
- LLM failure paths return 502 with helpful message — VA can retry without losing rate-limit budget

### Files touched
- `/app/backend/routes/va_objection_coach.py` — NEW (~260 lines)
- `/app/backend/server.py` — register `va_objection_coach_router`
- `/app/backend/startup.py` — index on `va_objection_calls` for rate-limit lookups
- `/app/frontend/src/components/va/ObjectionCoach.jsx` — NEW (~278 lines)
- `/app/frontend/src/pages/va/VAMyLeads.jsx` — "Handle objection" button + modal wiring
- `/app/backend/tests/test_iter59_objection_coach.py` — 7 tests


## Implemented — 2026-02 (Iter 60: Earnings Ticker + Tier Ladder — Phase 3 of "make VAs successful") — VERIFIED 5/5

**Goal**: Money on the screen. Every time a VA logs into the dashboard, the first thing they see is their MTD commission ticker counting up + a progress bar to the next earnings tier. Hungry VAs convert better.

### Backend
`routes/va.py::va_dashboard` now returns:
- `mtd_commission` (float, $) — paid commissions this month (already computed; now surfaced at top level instead of buried in `goal`)
- `tier` object with:
  - `current`: `{key, label}` — one of Hustler/Pro/Star/Elite/Legend
  - `next`: `{key, label, at_amount}` or `null` (Legend caps out)
  - `progress_pct`: 0–100 (clamped, never negative, never above 100)
  - `amount_needed_to_next`: float (0 at Legend)
  - `ladder`: full list of all 5 rungs with `{key, label, min}`

**Tier ladder** (hardcoded constants in `va_dashboard`):
- **Hustler** $0 →
- **Pro** $500 →
- **Star** $1,500 →
- **Elite** $3,000 →
- **Legend** $6,000+ (top rung)

Future: admin-editable ladder via Settings. For now constants ship the feature without needing a settings UI.

### Frontend (`components/va/EarningsTicker.jsx`, new)
Big hero banner at the top of the VA Dashboard:
- **Dark gradient card** with grain dots
- **Animated count-up** on mount/refresh (easeOutCubic, 1.2s) — `$0 → $1,247` rolls up before your eyes
- **Pulsing green dot** next to the number for "this is live"
- **Pending sub-tag**: "+$340 pending — approval in flight" (only shown when pending > 0)
- **Tier card on the right**:
  - Big tier label ("STAR")
  - Gradient progress bar (#0044FF → #10B981) with smooth 1s ease-out animation
  - "$340 to **Elite**" callout + percent
  - Mini ladder visualization — 5 segments, current = white text + green underline, past = dimmed, future = ghosted
- **Legend tier** shows trophy icon + "You've hit the top rung this month" message
- Mobile-responsive: stacks vertically on small screens

### VADashboard wiring
- `EarningsTicker` slotted at the top, ABOVE the stale-lead alert
- Pulls `mtd_commission`, `commissions_pending`, and `tier` directly from the dashboard payload — no new round-trips

### Tests
`/app/backend/tests/test_iter60_earnings_ticker.py` — **5/5 pass**:
- dashboard exposes `mtd_commission` + `tier` with all 5 ladder rungs
- at $0 MTD → Hustler tier, 0% progress, $500 needed
- seed $600 paid commission → Pro tier, correct progress math (10% of the Pro→Star range)
- seed $10,000 → Legend tier, progress=100, next=null, needed=0
- property check: progress_pct always in [0, 100]

Test fixtures use direct Mongo writes (`AsyncIOMotorClient`) for seed/cleanup so they don't go through the VA UI flow — fast and deterministic.

**Combined regression: 49/49 across iter53–60.**

### Files touched
- `/app/backend/routes/va.py` — tier ladder constants + `mtd_commission` and `tier` in dashboard payload
- `/app/frontend/src/components/va/EarningsTicker.jsx` — NEW (~165 lines)
- `/app/frontend/src/pages/va/VADashboard.jsx` — slotted ticker at top, import added
- `/app/backend/tests/test_iter60_earnings_ticker.py` — 5 tests


## Implemented — 2026-02 (Iter 61: VA pipeline — match the actual HCOB workflow) — VERIFIED 20/20

**Goal**: User feedback caught a wrong assumption — VAs don't issue quotes (especially in their first 30 days). They generate leads, warm them, and hand off to Ops who quotes. The Kanban + AI coach were both modeled on a "VA closes deals" workflow that didn't match reality. Restructured to match what VAs actually do.

### Pipeline column relabels (UI-only — stage values unchanged)
| Internal stage | Old label | **New label** | Meaning |
|---|---|---|---|
| `new_lead` | New (Reach out) | **New** *(First outreach owed)* | VA must do first touch in 24h |
| `contacted` | Contacted (Get the quote out) | **Talking** *(Get the details Ops needs)* | VA gathers the brief (sq ft / frequency / asks) |
| `quoted` | Quoted (Close the deal) | **Sent to Ops** *(Ops is quoting — keep it warm)* | VA hands lead off; Ops drafts the quote |
| terminal | With Ops | **With Ops** *(Booked / Closed / Lost)* | unchanged |

Internal stage values (`new_lead`, `contacted`, `quoted`) intentionally unchanged so commissions, admin tooling, leak reports, and historic `stage_history` records keep working without a migration.

### SLA tuning
`quoted` SLA bumped **72h → 120h (5 days)**. With the new meaning, the timer measures "how long has the lead been waiting for Ops + how long the VA has been silent with the prospect". 5 days gives Ops room to draft the quote without the timer screaming at the VA. New/Talking SLAs unchanged.

### AI Objection Coach prompt — anchored to lead-gen reality
System prompt now explicitly tells Claude: *"the VA's job is to find prospects, talk to them, gather the brief, and hand the lead to Ops who issues the actual quote. The VA does NOT quote prices themselves. Responses should reflect this — never commit to a price, never promise a specific number, but DO commit to getting Ops to put together a custom quote fast."*

Verified live:
- "Too expensive" objection → all 3 responses route back to Ops ("pass your details to our Ops team", "ask Ops to take another look with a tighter scope", "give Ops the right steer")
- No specific price commitments anywhere in the output
- Still on-brand and conversational

### UI copy updates
- Page subhead: *"Move a lead through New → Talking → Sent to Ops as you work it. You generate and warm the lead; Ops handles the actual quote. The amber/red timer means it's aging — knock those out first."*
- Move dropdown options relabeled

### Tests
- `test_iter58_va_pipeline.py` — updated SLA assertion (72→120) + comment explaining why
- 20/20 pass (iter58 + iter59 + iter60)

### Files touched
- `/app/backend/routes/va.py` — `VA_LEAD_SLA_HOURS["quoted"]` 72 → 120 + comment
- `/app/backend/routes/va_objection_coach.py` — system prompt anchored to lead-gen role
- `/app/frontend/src/pages/va/VAMyLeads.jsx` — COLUMNS labels/sublabels, page subhead, move dropdown
- `/app/backend/tests/test_iter58_va_pipeline.py` — SLA assertion updated


## Implemented — 2026-02 (Iter 62: Contractor Referral Program — Phase 1 MVP) — VERIFIED 13/13

**Goal**: Per Cory's FRD — approved contractors on the platform can refer leads they spot in the wild (carpet, junk, painting, handyman, etc.). HCOB quotes + dispatches; referring contractor earns 10% of the invoice when the customer pays.

### Scope decisions (deviations from FRD per Cory)
- **Always-on submission** — first-class CTA in worker sidebar ("Refer · earn 10%"), not gated to active assignments. `source_assignment_id` is optional metadata.
- **No 24h window**, no source-job validation — workers should know they CAN do this, friction kills the feature.
- **Intent declared upfront** ("for another contractor" vs "for yourself") — Mechie sees the signal in the inbox.
- **Self-fulfillment** still auto-voids commission if the referrer ends up assigned — belt-and-suspenders.
- **MVP only** — leaderboard / category overrides / duplicate detection are Phase 2.

### Backend (`routes/referrals.py`, new — ~290 lines)
- `POST /api/worker/referrals` — submit (validates approved-worker status, required fields, category enum)
- `GET /api/worker/referrals` — worker's own list with `totals: {pending, eligible, paid}` rollup
- `GET /api/worker/referrals/{id}` — single (ownership-gated)
- `GET /api/admin/referrals?status=` — Mechie inbox + per-status counts
- `GET /api/admin/referrals/{id}` — detail
- `PATCH /api/admin/referrals/{id}` — vet, quote, assign, mark paid, release, void
- `GET/PUT /api/admin/referrals/settings` — admin-configurable commission rate (default 10%)
- Self-fulfillment auto-detect: if `assigned_contractor_id == referring_contractor_id`, status flips to `self_fulfilled` + commission voided
- Commission accrual: `paid` status → `commission_status="eligible"` + amount computed (rounded to nearest $1); `commission_released` → `commission_status="paid"` + timestamp
- `referral_leads` collection + 4 indices added to startup

### Status lifecycle
`submitted → under_review → quoted → scheduled → in_progress → completed → invoiced → paid → commission_released`
Terminal off-ramps: `void`, `self_fulfilled`

### Frontend
**`/crew/refer` — WorkerReferrals.jsx (new ~480 lines)**
- 3-card rollup at the top: Commission **Pending** / **Eligible** / **Paid** (each with $ + sublabel)
- "Submit a lead" CTA opens a modal with:
  - Intent toggle (For another contractor [default] / For yourself [amber warning])
  - Required: property address, opportunity description, service category
  - Optional: prospect contact (name/phone/email)
  - Photo upload deferred to Phase 2 (note in modal)
- Referrals list — each card shows status pill, address, description, $ quote + 10% projection
- Empty state with CTA

**`/ops/referrals` — AdminReferrals.jsx (new ~450 lines)**
- Lead-center style inbox with status-filter pills (with live counts)
- Commission rate editor (inline edit-to-save flow, defaults to current rate)
- Row click → side drawer with full detail + edit form:
  - Status dropdown (all 11 statuses)
  - Quote $, Square invoice ID, Assigned contractor user_id
  - Self-fulfillment helper text
  - Admin notes
  - Commission rollup card (green, only shown when commission is non-zero)

### Sidebar
- Worker sidebar: new "Refer · earn 10%" entry with Handshake icon
- Admin sidebar: new "Referrals" entry between Email Blast and Reports

### Tests
`/app/backend/tests/test_iter62_referral_program.py` — **13/13 pass**:
- worker submission happy path · required-field validation · invalid category
- intent persistence (for_self / for_another)
- worker sees own list + totals rollup
- admin sees all + per-status filter + counts
- full lifecycle (quoted → paid → commission_released) with commission math
- self-fulfillment auto-voids
- admin can void at any stage
- commission rate is admin-configurable (set 15% → $1000 quote → $150 commission)
- release blocked until status reaches `paid` (400 with helpful message)
- workers can't hit admin endpoints (403)
- VAs can't submit referrals (403)

**Combined regression: 41/41 across iter56–62.**

### Files touched
- `/app/backend/routes/referrals.py` — NEW (~290 lines)
- `/app/backend/server.py` — register referrals router
- `/app/backend/startup.py` — `referral_leads` indices
- `/app/frontend/src/pages/worker/WorkerReferrals.jsx` — NEW
- `/app/frontend/src/pages/admin/AdminReferrals.jsx` — NEW
- `/app/frontend/src/App.js` — route registration + imports
- `/app/frontend/src/components/admin/AdminLayout.jsx` — sidebar entry
- `/app/frontend/src/components/worker/WorkerLayout.jsx` — sidebar entry
- `/app/backend/tests/test_iter62_referral_program.py` — 13 tests

### Out of Phase 1 (queued for follow-up if Cory wants them)
- Admin-only referral leaderboard (FRD §10)
- Category-specific commission rate overrides (FRD §6)
- Photo file uploads (currently a note in description; FRD §11 says recommended for commercial)
- Duplicate-address detection (90-day window, FRD §7)
- Square webhook for auto-paid status (FRD §12 — manual is acceptable for v1)
- Weekly admin summary email of referral activity (FRD §9 — explicitly "nice-to-have")



## Implemented — 2026-06 (Iter 62b: Referral Status Update Notifications) — VERIFIED
**Goal**: Keep referring contractors informed + motivated by emailing them every time Mechie / admin advances their referral through the pipeline. Per-event SMS for the two milestone events (`paid`, `commission_released`).

**Backend** (`/app/backend/routes/referrals.py`):
- Added `_STATUS_NOTIFICATIONS` template registry — subject + intro line per status (`under_review`, `quoted`, `scheduled`, `in_progress`, `completed`, `invoiced`, `paid`, `commission_released`, `void`, `self_fulfilled`). `paid` + `commission_released` carry an extra `sms_text` template (with `{commission}` token).
- `_build_status_email_html(referral, new_status, intro, admin_notes)` — renders the inner HTML for the standard HCOB email shell. Shows status pill, address, service, quoted amount (when set), commission (when set), + admin-note callout in amber.
- `_send_referral_status_notification(referral_id, new_status)` — background task entrypoint:
  - Loads referral + referring user from Mongo
  - Sends email via `_send_user_email` for every templated status (always)
  - Sends SMS via `_send_sms_sync` ONLY for `paid` + `commission_released` (and only when user has a phone + Twilio is configured)
  - Records every attempt to a new `referral_notifications` audit collection (id, channels attempted, email_sent flag, sms_sent flag, timestamp). Even skipped sends are logged so admins/tests can verify behavior without mocking Resend/Twilio.
- `admin_update_referral` now accepts `BackgroundTasks` and schedules `_send_referral_status_notification` only when `new_status != existing.status` — silent edits (e.g. updating just `quoted_amount` or `admin_notes`) do NOT spam the referrer.
- Self-fulfillment auto-flip + `void` transitions ALSO fire the notification (closes the loop with the referrer).

**Tests** (`/app/backend/tests/test_iter62_referral_program.py`): 7 new + 13 existing = **20/20 pass**.
- under_review → email-only audit row
- quoted → email-only audit row
- paid → email + sms attempted (SMS only when worker has phone on file)
- commission_released → email + sms attempted
- void → email audit row
- self_fulfilled (auto-flip via assigning the referrer) → email audit row
- Silent edit (`quoted_amount` change, no status change) → NO new audit row (anti-spam)

**Cross-test regression**: 51/51 across iter62 + iter39 (blast safety) + iter41 (lead CRUD). Pre-existing event-loop fixture failures in `test_iter6.py` / `test_messenger.py` / `backend_test.py` are orthogonal to this change.

**Smoke-tested end-to-end via curl**: real `PATCH /api/admin/referrals/:id` with status changes ⇒ background task fires ⇒ `referral_notifications` collection populated with channels=`['email']` for non-milestone and `['email','sms']` for `commission_released`. Resend API key is invalid in the current preview env (pre-existing condition) so `email_sent=false`, but the channel attempt + audit row are correct.

**Files modified**:
- `/app/backend/routes/referrals.py` (notification helpers + status template registry + BackgroundTasks wiring)
- `/app/backend/tests/test_iter62_referral_program.py` (7 new tests)


## Implemented — 2026-06 (Iter 63: Customer ↔ Contractor 2-Way Messenger via Magic Link) — VERIFIED
**Goal**: Let a customer (no account, no login) chat directly with the contractors assigned to their job and the HCOB team. Admin generates a shareable link they paste into a text/email to the customer.

**Design choices (user-approved)**: 1a (one thread per gig, group chat), 2a (admin manually copies link), 3c (admin pre-fills customer name), 4b (auto-close on gig completion), 5a (email-only to customer on reply), 6a (contractors see customer first-name only — privacy-first).

**Backend** (`/app/backend/routes/customer_threads.py`):
- New collections: `customer_threads` (carries token + customer name/email + status) and `customer_messages` (append-only sender_type ∈ {customer, contractor, admin}).
- Admin endpoints:
  - `POST /api/admin/customer-threads` — create (idempotent per gig+email so re-clicking doesn't spawn duplicates)
  - `GET /api/admin/gigs/:gig_id/customer-threads` — list
  - `GET /api/admin/customer-threads/:id` + `/messages` — full PII view
  - `POST /api/admin/customer-threads/:id/close` + `/reopen`
- Customer endpoints (no auth, token-validated):
  - `GET /api/customer/threads/:token` — metadata + crew first names
  - `GET /api/customer/threads/:token/messages` — list
  - `POST /api/customer/threads/:token/messages` — send (returns 410 if closed)
- Contractor endpoints (auth, gated by approved-on-gig check):
  - `GET /api/crew/gigs/:gig_id/customer-threads` — PII-stripped list (first name only, no email, no token)
  - `GET /api/crew/customer-threads/:id/messages` / `POST /api/crew/customer-threads/:id/messages`
- Auto-close behavior: on every read/write, server checks gig.status — if `completed`, flips thread to `closed` with reason "Assignment marked completed". Reads still work (preserves history); writes return 410.
- Notifications:
  - Customer → contractor: emails every approved contractor on the gig (+ thread creator) via `_send_user_email` with the customer's snippet + deep link to `/crew/assignments/:gig_id`. Graceful no-op when Resend creds missing.
  - Contractor/admin → customer: emails customer at their address with HCOB-branded template + magic-link CTA back to `/c/:token`.

**Frontend**:
- New public route `/c/:token` → `CustomerChat.jsx`:
  - HCOB-branded header, no nav, mobile-optimized
  - Polls messages + thread status every 5s
  - Right-aligned blue bubbles for customer, white for contractor, light-purple "HCOB Team" tinted bubbles for admin
  - Auto-scroll on new messages, closed-banner when thread ended, disabled composer when closed
- New admin dialog `CustomerChatDialog.jsx` opens from new `Customer chat link` button on `AdminGigDetail.jsx` (just below `Share gig link`). Lists existing threads with copy / close / reopen actions.
- New `CustomerChatPanel.jsx` embedded in `WorkerGigDetail.jsx` (only renders if worker is approved + threads exist). Each thread expandable with inline composer.

**Tests** (`/app/backend/tests/test_iter63_customer_chat.py`): 10/10 pytest pass — admin create (incl. idempotency), customer read/write via token, invalid-token 404, contractor read/write, contractor-not-on-gig 403, close + reopen lifecycle, unauth 401/403, empty-message 422.

**Frontend regression**: 5/5 flows pass per testing agent iteration_48 — admin generate link, public customer read/write, contractor reply, privacy (first name only, no email/token leak), close flow with banner + disabled composer.

**Files added / modified**:
- ADDED: `/app/backend/routes/customer_threads.py`
- ADDED: `/app/backend/tests/test_iter63_customer_chat.py`
- ADDED: `/app/frontend/src/pages/CustomerChat.jsx`
- ADDED: `/app/frontend/src/components/admin/CustomerChatDialog.jsx`
- ADDED: `/app/frontend/src/components/worker/CustomerChatPanel.jsx`
- MODIFIED: `/app/backend/server.py` (router include)
- MODIFIED: `/app/frontend/src/App.js` (public route + import)
- MODIFIED: `/app/frontend/src/pages/admin/GigDetail.jsx` (button + import)
- MODIFIED: `/app/frontend/src/pages/worker/WorkerGigDetail.jsx` (panel mount)

**Known nit (not a bug)**: The `customer_link` returned to admins always uses the production hostname (`https://hcobnetwork.com`) — by design, since admins will be sending these to real customers in production. For preview testing, swap the hostname with the preview URL.



## Implemented — 2026-06 (Iter 64: Email Blast — Rich Text Editor + Plain-Text Normalizer) — VERIFIED
**Bug fix**: User reported "everything comes out jumbled up, no formatting" in the Email Blast composer. Cause: the body was a plain `<textarea>` whose newlines collapsed when shipped as HTML to Resend.

**Two-pronged fix:**

1. **Frontend — TipTap rich-text editor** (`/app/frontend/src/components/admin/RichEmailEditor.jsx`):
   - Toolbar: Bold, Italic, Strikethrough, H2 heading, Bullet list, Numbered list, Link (with prompt), Clear formatting.
   - Live preview pane mirrors the WYSIWYG output exactly.
   - Replaces `<Textarea>` in `AdminEmailBlast.jsx` Compose step.
   - Installed: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-link`, `@tiptap/extension-placeholder`.
   - Inline-style aware: paragraphs, headings, lists styled via `index.css` so the editor preview matches Resend rendering.

2. **Backend — plain-text → HTML safety net** (`/app/backend/routes/admin_blasts.py::_normalize_plain_text_to_html`):
   - If body already contains block tags (`<p>`, `<h*>`, `<ul>`, `<ol>`, `<li>`, `<div>`, `<br>`, etc.) → passes through verbatim (TipTap path).
   - Otherwise: splits on blank lines → `<p>` paragraphs, single `\n` → `<br>`, detects consecutive `- ` / `* ` lines → `<ul>`, detects `1. ` lines → `<ol>`, auto-links bare http(s) URLs, supports `**bold**` / `_italic_` markdown.
   - HTML-escapes everything that isn't a recognized format so admins can't accidentally inject markup.
   - Windows line endings (`\r\n`) normalized.
   - `_render_body()` applies merge tags THEN normalizes — used by both `test_only` and bulk blast send paths.

**Tests** (`/app/backend/tests/test_iter64_email_format.py`): 15/15 pass — empty input, HTML passthrough, multi-paragraph, single-newline → `<br>`, bullet detection, numbered list, HTML escaping, URL auto-link, inline markdown, double-link prevention, Windows EOL, paragraph spacing, `_render_body` integration (both plain and HTML inputs).

**Frontend smoke-tested**: screenshot confirmed editor toolbar visible with all 8 buttons; template ("Ask workers to add payment method") loaded properly with bold/paragraphs intact; live preview matches editor 1:1; merge tags resolve in preview.

**Regression**: 59/59 cross-test (iter39 blast safety + iter62 referrals + iter63 customer chat + iter64).

**Files added / modified**:
- ADDED: `/app/frontend/src/components/admin/RichEmailEditor.jsx`
- ADDED: `/app/backend/tests/test_iter64_email_format.py`
- MODIFIED: `/app/frontend/src/pages/admin/AdminEmailBlast.jsx` (replaced `<Textarea>` with `<RichEmailEditor>`)
- MODIFIED: `/app/frontend/src/index.css` (added `.rich-email-editor-content` styles for paragraphs, lists, headings, links, placeholder)
- MODIFIED: `/app/backend/routes/admin_blasts.py` (added `_normalize_plain_text_to_html` + `_render_body`; both send paths use `_render_body`)
- MODIFIED: `/app/frontend/package.json` (4 new TipTap deps)



## Implemented — 2026-06 (Iter 65: Project-Wide Customer Chat) — VERIFIED
**Goal**: Same magic-link customer chat as Iter 63, but bound to a Project (which spans multiple gigs) instead of a single gig. Customer gets one persistent link, contractors picked by admin stay in for the life of the project.

**Design choices (user-approved)**: 1c (admin manually curates contractor list), 2b (NEVER auto-close — manual only since projects are long-lived), 3a (one chat per project), 4a (independent of per-gig chats from Iter 63), 5a (project title shown to customer).

**Backend** (`/app/backend/routes/customer_threads.py` — extended in place, schema migration-free):
- New thread shape: added `scope_type` (`'gig'` | `'project'`), `project_id`, `project_title`, `participant_contractor_ids` to existing `customer_threads` collection. `gig_id` becomes optional (null for project scope).
- Refactored helpers:
  - `_thread_contractor_ids(thread)` — resolves participant list based on scope.
  - `_is_thread_active(thread)` — auto-close only for gig threads (per choice 2b).
  - `_require_approved_contractor(user, thread)` — gig scope uses gig_acceptances, project scope checks participant list.
  - `_email_contractors_new_customer_msg` + `_email_customer_new_reply` — copy adapts to scope ("project" vs "assignment").
- New admin endpoints:
  - `POST /api/admin/projects/:project_id/customer-threads` — create (idempotent per project+email)
  - `GET /api/admin/projects/:project_id/customer-threads` — list
  - `PATCH /api/admin/customer-threads/:thread_id/participants` — add/remove contractors (project threads only; 400 on gig threads)
- New contractor endpoint:
  - `GET /api/crew/projects/:project_id/customer-threads` — worker-facing project-scoped list
- Extended endpoint:
  - `GET /api/crew/gigs/:gig_id/customer-threads` now ALSO returns project-scoped threads where the gig's parent project includes the worker as a participant — gives contractors a unified panel.

**Frontend**:
- New `ProjectCustomerChatDialog.jsx` with admin-curated participant picker:
  - All/None toggle buttons
  - Checkbox list of every contractor that's worked any gig in the project (de-duped, with the list of their gigs underneath)
  - Edit-participants flow on existing threads (add/remove contractors over time as crew changes)
  - Copy link · Close · Reopen actions
- Wired the dialog button into `AdminProjectDetail.jsx` action row (`data-testid="proj-customer-chat-btn"`).
- `CustomerChatPanel.jsx` (worker side) now shows a blue "PROJECT" badge for project-scoped threads.
- `CustomerChat.jsx` (public customer view) labels the header as "PROJECT" instead of "ASSIGNMENT" and displays `project_title`.
- Added DialogDescription to both Customer chat dialogs (silence Radix aria warning).

**Tests** (`/app/backend/tests/test_iter65_project_chat.py`): 13/13 pytest pass — create with participants, idempotency, customer reads/sends via token, contractor on/off list (200/403), PII privacy, admin updates participants, gig-thread participant edit blocked (400), manual close → 410, project archive does NOT auto-close, project thread appears in gig endpoint, unauth blocked, list endpoint.

**Frontend e2e** (testing_agent_v3_fork iteration_49): 6/6 flows pass — admin create, edit participants, customer public view (project label + title), contractor view (PROJECT badge + privacy stripping), manual close (banner + disabled composer).

**Cross-test regression**: 72/72 across iter39 + iter62 + iter63 + iter64 + iter65.

**Files added / modified**:
- ADDED: `/app/frontend/src/components/admin/ProjectCustomerChatDialog.jsx`
- ADDED: `/app/backend/tests/test_iter65_project_chat.py`
- MODIFIED: `/app/backend/routes/customer_threads.py` (scope-aware refactor + new project endpoints)
- MODIFIED: `/app/frontend/src/pages/admin/AdminProjectDetail.jsx` (Customer chat button)
- MODIFIED: `/app/frontend/src/components/worker/CustomerChatPanel.jsx` (PROJECT badge)
- MODIFIED: `/app/frontend/src/pages/CustomerChat.jsx` (scope-aware header label)
- MODIFIED: `/app/frontend/src/components/admin/CustomerChatDialog.jsx` (DialogDescription)



## Hotfix — 2026-06 (Iter 64b: Email Preview + Send Spacing Bug) — VERIFIED
**Bug**: User reported the email Live Preview pane still showed paragraphs running together with zero spacing, even though the TipTap editor itself rendered them correctly. Real sent emails were also at risk because TipTap emits bare `<p>` tags and Outlook desktop / Gmail strip `<style>` blocks.

**Cause**: The preview pane used `prose prose-sm` (Tailwind Typography) classes, but `@tailwindcss/typography` isn't installed — so those classes were no-ops. Tailwind preflight had reset `<p>` margins to 0.

**Fix**:
1. **Frontend live preview** (`/app/frontend/src/index.css`): Added new `.email-preview-html` class that explicitly styles `<p>`, `<h2>`, `<h3>`, `<ul>`, `<ol>`, `<li>`, `<a>`, `<strong>`, `<em>`, `<s>`, `<code>` with the same spacing/typography rules as the editor. Both preview locations in `AdminEmailBlast.jsx` (Compose live-preview pane + Confirm step "Final email" block) swapped `prose prose-sm` → `email-preview-html`.
2. **Backend inline-styler** (`/app/backend/routes/admin_blasts.py::_inline_block_styles`): Adds inline `style=` attributes to bare `<p>`, `<h1-3>`, `<ul>`, `<ol>`, `<li>`, `<blockquote>`, `<a>` tags coming from the TipTap editor. Preserves any existing `style=` attr (admin override path). Wired into `_render_body()` so every test_only and bulk send path emits inline-styled HTML — Outlook desktop / Gmail web / Apple Mail all render consistent spacing regardless of `<style>` block stripping.

**Tests**: 4 new in `test_iter64_email_format.py` → 19/19 pass. Cross-regression: 76/76 across iter39 + iter62 + iter63 + iter64 + iter65.

**Verified visually**: screenshot of the Compose step confirms preview paragraphs now show proper blank-line spacing matching the editor 1:1.

**Files modified**:
- `/app/frontend/src/index.css` (new `.email-preview-html` style block)
- `/app/frontend/src/pages/admin/AdminEmailBlast.jsx` (swapped `prose prose-sm` → `email-preview-html` in both preview render sites)
- `/app/backend/routes/admin_blasts.py` (added `_EMAIL_BLOCK_STYLES`, `_BARE_BLOCK_OPEN_RE`, `_inline_block_styles`; wired into `_render_body`)
- `/app/backend/tests/test_iter64_email_format.py` (4 new tests)



## Implemented — 2026-06 (Iter 66: Admin Chat Page — close the loop) — VERIFIED
**Gap reported by user**: After generating a customer chat link (per-gig or project), the admin had no way to actually **enter and reply to** the chat from inside the admin console — only "Copy link" / "Close". Admin would have to open the magic link themselves and appear as the customer.

**Fix**:
- New dedicated admin chat page `/app/frontend/src/pages/admin/AdminCustomerChat.jsx` at route `/ops/customer-chats/:threadId`.
  - Top bar: back arrow (smart return — to project for project threads, to assignment for gig threads), scope badge (`PROJECT CHAT` / `ASSIGNMENT CHAT`), Live/Ended status pill, page title (project_title or gig_title), Copy link + Close/Reopen actions.
  - Info strip: customer name (admin sees full name), clickable customer email, crew first-name pills.
  - Closed-banner with reason when status='closed'.
  - Message list with three styles: blue = customer, purple = HCOB Team (admin's own messages), white-bordered = contractor.
  - Composer at bottom — purple "Reply as HCOB Team" with Enter-to-send / Shift+Enter-for-newline.
  - 5s poll for thread + messages so new replies stream in automatically.
- "Open chat" button added to BOTH dialogs:
  - `CustomerChatDialog.jsx` (per-gig) — `data-testid="customer-thread-open-{id}"`
  - `ProjectCustomerChatDialog.jsx` (project) — `data-testid="project-thread-open-{id}"`
  - Closes the dialog and navigates to `/ops/customer-chats/:threadId`.
- Route wired in `App.js` under the `/ops/*` admin shell.

**Backend**: No changes — `GET /api/admin/customer-threads/:id`, `GET/POST /api/admin/customer-threads/:id/messages`, close/reopen endpoints already existed from Iter 63. Iter 66 just exposes them through a new UI surface.

**Tests** (`/app/backend/tests/test_iter66_admin_chat.py`): 6/6 pass — admin get-thread full details, send + list messages, admin message visible to customer as `sender_type='admin'`, closed thread blocks send (410), empty message 422, non-admin blocked.

**Cross-regression**: 29/29 across iter63 + iter65 + iter66.

**Verified end-to-end**: screenshot confirms admin navigates from project chat dialog → admin chat page → types and sends a message → appears as a purple HCOB Team bubble. Customer view picks up the admin's message in their lavender HCOB Team tinted bubble.

**Files added / modified**:
- ADDED: `/app/frontend/src/pages/admin/AdminCustomerChat.jsx`
- ADDED: `/app/backend/tests/test_iter66_admin_chat.py`
- MODIFIED: `/app/frontend/src/App.js` (route + import)
- MODIFIED: `/app/frontend/src/components/admin/CustomerChatDialog.jsx` (Open chat button, useNavigate)
- MODIFIED: `/app/frontend/src/components/admin/ProjectCustomerChatDialog.jsx` (Open chat button, useNavigate)



## Hotfix — 2026-06 (Iter 67: Worker Chat Visibility) — VERIFIED
**Bug reported in production**: After creating a project customer chat and posting a message, "noone in the projects sees the messages." Workers couldn't find the chat.

**Root cause** — NOT a data bug. Messages were saved correctly and visible to admin. The issue was pure UX/visibility: the `CustomerChatPanel` only mounted on individual gig detail pages (`/crew/assignments/:gigId`). Workers had to know to navigate into a specific gig to discover their project chats. The worker project page (`/crew/projects/:projectId`) had no chat panel at all, and the worker home/feed had no surface for customer chats.

**Fix (three-pronged)**:

1. **New backend endpoint** `GET /api/crew/customer-threads/mine` — returns every chat the worker can read in one shot:
   - Gig-scoped threads on gigs they're approved on
   - Project-scoped threads where they're in `participant_contractor_ids`
   - Admin variant returns ALL active chats as a convenience inbox
   - Sorted by `last_message_at desc`, PII-stripped for contractor viewer

2. **`CustomerChatPanel` extended** to accept either `gigId` OR `projectId` prop and hits the right endpoint. Mounted on `WorkerProjectPage.jsx` — workers visiting `/crew/projects/:projectId` now see the customer chat directly on the project landing.

3. **New `WorkerCustomerChatsInbox` tile** on the worker home/feed page (`/crew`):
   - Lists up to 5 most-recent chats with title, project/gig badge, customer first-name, last-message preview, and relative timestamp
   - Click row → opens the project page (project threads) or assignment page (gig threads)
   - Auto-hides when no chats exist, polls every 30s
   - Active/total counter ("3/5 LIVE") shown in top-right

**Tests** (`/app/backend/tests/test_iter67_worker_chat_visibility.py`): 6/6 pass — `/mine` returns project threads when participant, excludes when not, includes gig threads when approved, **admin-sent message visible to worker (exact production-bug repro)**, unauthenticated blocked, `/crew/projects/:id/customer-threads` returns participant threads.

**Cross-regression**: 35/35 across iter63 + iter65 + iter66 + iter67.

**Verified visually**: screenshots confirm worker feed shows the "Customer chats" tile with rows + last-message previews, clicking opens the assignment page with the chat panel showing "CUSTOMER CHATS (1) Jane LIVE".

**Files added / modified**:
- ADDED: `/app/frontend/src/components/worker/WorkerCustomerChatsInbox.jsx`
- ADDED: `/app/backend/tests/test_iter67_worker_chat_visibility.py`
- MODIFIED: `/app/backend/routes/customer_threads.py` (new `/crew/customer-threads/mine` endpoint)
- MODIFIED: `/app/frontend/src/components/worker/CustomerChatPanel.jsx` (accept `gigId` OR `projectId`)
- MODIFIED: `/app/frontend/src/pages/worker/WorkerProjectPage.jsx` (mount panel)
- MODIFIED: `/app/frontend/src/pages/worker/WorkerFeed.jsx` (mount inbox tile)



## Implemented — 2026-06 (Iter 68: Worker Shift History) — VERIFIED
**Goal**: Workers wanted a more detailed view of worked gigs — prior weeks + per-shift detail. The existing "My assignments" page showed only an earnings summary + active assignment list, no historical breakdown.

**Design choices (user-approved)**: 1b (new section on existing `/crew/my-assignments` page), 2 (everything except gig location), 3c (week + month toggle), 4b (history only — no upcoming).

**Backend** (`/app/backend/routes/reports.py::my_shifts`):
- New endpoint `GET /api/me/shifts` returns every completed shift (clock-out set) for the requesting worker with rich detail.
- Per-row payload: `acceptance_id`, `gig_id`, `gig_title`, `gig_category`, `gig_subcategory`, `gig_scheduled_date`, `project_id`, `project_title`, `clock_in_at`, `clock_out_at`, `hours_worked`, `break_minutes`, `paid_hours`, `pay_rate_applied`, `pay_type_applied`, `earnings`, `approval_status` (paid/approved/pending/no_show), `timesheet_approved_at`, `admin_note`, `no_show_reason`, `co_workers` (first-name-only roster of other approved contractors on the same gig).
- Bulk-fetches gigs, projects, and co-worker users in 3 round trips total — no N+1 queries even at 500+ shifts.
- Sorted newest first.
- 403 for non-workers; 401/403 for unauthenticated.

**Frontend** (`/app/frontend/src/components/worker/WorkerShiftHistory.jsx`):
- Collapsible "Shift history (N shifts)" section with By Week / By Month toggle.
- Week grouping: Mon–Sun rollup with weekly subtotal (paid hours + earnings) in a black header bar.
- Each shift = collapsed row showing status badge (APPROVED/PENDING/PAID/NO-SHOW with icon), gig title, clock times, paid hours, earnings (green).
- Expand → full detail: project tag, clock-in/out, worked/paid/rate triplet, approval timestamp, co-worker pills, amber admin note, red no-show reason box.
- Mounted at the bottom of `/crew/my-assignments` (per user choice 1b). Auto-hides when worker has no completed shifts.

**Tests** (`/app/backend/tests/test_iter68_shift_history.py`): 7/7 pass — contract shape, sort-desc-by-clock-in, non-worker 403, unauthenticated 401/403, co-workers PII-stripped (first name only, no email/full name leak), project context hydrated when gig is in a project, `/me/earnings` regression intact. Seeds data via sync pymongo so multi-shift tests don't conflict with motor's event-loop reuse.

**Cross-regression**: 42/42 across iter63 + iter65 + iter66 + iter67 + iter68.

**Verified visually**: screenshots confirm the section appears below the existing assignment list with weekly grouping ("Jun 29 – Jul 5 · 4 shifts · 8.00h · $240.00") + expandable shift cards showing all detail including the admin note.

**Files added / modified**:
- ADDED: `/app/frontend/src/components/worker/WorkerShiftHistory.jsx`
- ADDED: `/app/backend/tests/test_iter68_shift_history.py`
- MODIFIED: `/app/backend/routes/reports.py` (new `/me/shifts` endpoint)
- MODIFIED: `/app/frontend/src/pages/worker/WorkerAccepted.jsx` (mounted `WorkerShiftHistory`)



---

## 2026-07-02 — VA Digital Services (Other Services Tab) — DONE
**Scope (user-confirmed):** VAs submit leads for NON-cleaning digital services AND can be assigned to deliver them. All digital service types (sourcing, web dev, app dev, social media, SEO, design, other). Commission = admin-configurable % of project value (default 10%, `app_settings.digital_commission_pct`). Same 7-stage pipeline. UI in both VA portal and admin VA Program area.

**Backend:**
- `va_commission.py`: `LeadServiceType` extended (product_sourcing, web_development, app_development, social_media_marketing, seo_content, graphic_design, digital_other); `DIGITAL_SERVICE_TYPES`; `_get_digital_commission_pct()`; `_calc_commission_for_lead` → `digital_pct` kind (% × job_value); `LeadIn.property_size` now Optional + `estimated_budget` on LeadIn/LeadEditIn; `DigitalSettingsIn`, `AssignVAIn` models.
- `routes/va.py`: `GET /api/va/digital-settings`, `GET /api/va/projects` (leads assigned for delivery); property_size required (400) for non-digital services; `va_get_lead` grants access via `assigned_va_id`.
- `routes/pm.py`: `GET/PUT /api/pm/digital-settings`; `POST /api/pm/leads/{id}/assign-va` (assign/clear delivery VA + activity log `delivery_assigned`/`delivery_unassigned` + in-app notification); `GET /api/pm/leads?category=digital|cleaning`.
- Lead doc new fields: `estimated_budget`, `assigned_va_id`, `assigned_va_name`, `assigned_at`.

**Frontend:**
- `pages/va/VADigitalServices.jsx` (/va/digital): commission banner, digital lead submit form (budget + live commission preview), My digital leads table, My delivery projects cards. Tab in VALayout.
- `pages/admin/AdminVADigital.jsx` (/ops/va-program/digital): 4 KPIs, commission-% editor, digital-only pipeline table with stage moves, job-value-on-paid, delivery-VA assign select (deduped/sorted). Sidebar entry in AdminLayout.
- `lib/leadOptions.js`: DIGITAL_SERVICE_TYPES / ALL_SERVICE_TYPES / isDigitalService.
- `LeadDetail.jsx`: estimated-budget field, Digital optgroup in service dropdown, Size field hidden for digital leads, Delivery VA sidebar card, `calc_notes` shown in commission card, delivery activity rows.

**Testing:** iteration_50.json — backend 9/9 PASS, frontend 10/10 flows PASS. 3 cosmetic follow-ups from report fixed afterward (size-field hide, calc_notes display, VA select dedupe).

**Remaining backlog (unchanged priority):**
- P1: Professional Certified Badges & Testing System (user-requested, needs scoping)
- P1: Referral Program Phase 2 (public leaderboard, category overrides, duplicate-address detection)
- P2: Shift History CSV/Sheets export; Stripe auto-payouts
- P3: Review collection blasts; monthly VA summary emails; AI-suggested replies

## 2026-07-02 — Bookkeeping / Expenses Section (Admin-only) — DONE
**Scope (user-confirmed):** Admin-only. Expenses + income (P&L), link entries to projects/assignments for per-project profitability, receipt uploads (image/PDF), full reporting (P&L summary, category breakdown, monthly chart, date-range filters, CSV export), recurring monthly expenses (auto-log).

**Backend (`routes/bookkeeping.py`, registered in server.py; runner in startup.py):**
- Collections: `ledger_entries`, `recurring_expenses`.
- Endpoints: GET/POST `/api/admin/ledger`, PUT/DELETE `/api/admin/ledger/{entry_id}`, POST `/api/admin/ledger/{entry_id}/receipt` (object storage, served via existing `/api/files/{path}`), GET `/api/admin/ledger/summary` (totals, by category, by month, by project), GET `/api/admin/ledger/export` (CSV w/ totals), GET `/api/admin/ledger/meta` (categories + projects + gigs for linking), CRUD `/api/admin/recurring-expenses`.
- `recurring_expenses_runner` background loop (6h) + immediate generation on create; entries tagged `recurring_id`, created_by 'Recurring (auto)'.
- Categories — expense: supplies, travel_fuel, equipment, software, contractor_pay, payroll, marketing, insurance, rent_utilities, taxes_fees, other; income: assignment_income, project_income, digital_income, referral_income, other_income.

**Frontend:** `/ops/bookkeeping` (nav-bookkeeping in ops sidebar): `AdminBookkeeping.jsx` shell + `components/admin/bookkeeping/` BookOverview (presets/date range, 4 KPIs, recharts monthly bars, category breakdown, per-project P&L table), BookTransactions (filters, totals strip, table, add/edit dialog, receipt attach/view, CSV export), BookRecurring (add form, pause/activate, delete). `lib/ledgerOptions.js` categories + money fmt.

**Testing:** iteration_51.json — backend 13/13 PASS, frontend all flows PASS. DialogDescription a11y fix applied after. TEST seed data cleaned; ledger starts empty for production use.

## 2026-07-02 — Geofenced + Schedule-Restricted Clock-In — DONE
**Scope (user-confirmed):** 250m geofence radius; NO early clock-ins (only at/after scheduled_at); GPS failure or ungeocodable address → allow clock-in but FLAG for admin review; enforced on all gigs (no per-gig toggle).

**Backend:**
- `geo.py` (new): `geocode_address` (OSM Nominatim, keyless, UA header), `haversine_m`, `resolve_gig_coords` (lazy geocode + cache with `geocode_attempted`), `CLOCKIN_RADIUS_M=250`.
- `routes/gigs.py`: create_gig geocodes address → `site_lat`/`site_lng` on gig docs (series share coords); update_gig re-geocodes when address_line/location changes; `_strip_sensitive_for_worker` also strips site coords pre-acceptance (no address leak).
- `clock_in` rewritten: (1) schedule gate — 400 'Too early' if now < scheduled_at, message shows wait time; (2) geofence — 403 'too far' with distance if > 250m from site; (3) verified pass stores clock_in_lat/lng/accuracy/distance_m + location_verified=true; (4) GPS-denied or ungeocodable → allowed but location_flagged=true + location_flag_reason.
- `models.py`: `ClockInIn {lat, lng, accuracy, location_error}`.

**Frontend:**
- WorkerGigDetail: clock-in captures browser geolocation (10s timeout, high accuracy) and sends with request; graceful fallback sends location_error; button shows 'Verifying location…'; hint copy updated; container pb-28 so button isn't under the fixed bottom nav (testing agent finding, fixed).
- Admin GigDetail crew table: green 'GPS ✓ {N}m' badge (gps-verified-*) for verified clock-ins; amber 'UNVERIFIED' badge (gps-flagged-*) with tooltip reason for flagged ones.

**Testing:** iteration_52.json — backend 9/9 PASS (too-early 400, too-far 403, on-site verified, GPS-denied flagged, ungeocodable flagged, re-geocode on edit, coord privacy for requested workers, no-acceptance block, clock-out regression), frontend Playwright geolocation flows PASS. Test file: backend/tests/test_iter69_geofence_clockin.py.

## 2026-07-02 — BUG FIX: Bookkeeping Transactions tab blank screen — DONE
**Report:** User saw blank/white screen on the Transactions tab (production https://hcobnetwork.com).
**Root cause:** `<DialogDescription>` was used in BookTransactions.jsx without being imported (an earlier import edit never landed on disk) → ReferenceError at render time → whole tab blank. Compiles fine (no no-undef lint), fails only at runtime — reproduced in preview too.
**Fix:** Added DialogDescription to the dialog import (applied by testing agent iteration_53). Re-verified 11/11 flows (tab render, add/edit dialog, filters, CSV, recurring, tab switching) with 0 console errors.
**User action required:** REDEPLOY to production to pick up the fix.
**Deferred hardening ideas (from test report):** ErrorBoundary around /ops routes; eslint no-undef enforcement.

## 2026-07-02 — Centralized Announcement Dashboard — DONE
**Scope (user-confirmed):** Admin posts one centralized update (title + text); audience chosen per message (Workers and/or VAs); shows as LOGIN POPUP (per-message toggle) + revisitable board; dismissible per user; delivery via in-app / email / SMS / push (admin picks channels, reuses fanout_blast_channels blast infra w/ kill switch + dedupe).

**Backend (`routes/announcements.py`):**
- `announcements` collection {announcement_id, title, body, audience[], popup, channels[], active, dismissed_by[], recipients, in_app, blast_id, created_by...}.
- Admin: POST /api/admin/announcements (in-app insert_many inline + background email/SMS/push fanout with blast_logs), GET list (read_count + delivery stats merged from blast_logs), PUT (edit/hide via active), DELETE (cascade-deletes related notification docs).
- Users: GET /api/announcements (role-filtered, per-user dismissed flag), POST /api/announcements/{id}/dismiss.

**Frontend:**
- `components/announcements/AnnouncementsPopup.jsx` — auto-opens after login for popup+undismissed items, 'Got it' dismisses (queued if multiple). Embedded in WorkerLayout + VALayout.
- `components/announcements/AnnouncementsBoard.jsx` — expandable list, unread badge/new-dot, 'Mark as read'. Embedded top of WorkerFeed (/crew) + VADashboard (/va). Auto-hides when empty.
- `pages/admin/AdminAnnouncements.jsx` (/ops/announcements, Megaphone nav): compose (title/body/audience checkboxes/channel checkboxes/popup toggle), list with popup/hidden/audience chips, read counts, delivery stats, hide toggle, delete.

**Testing:** iteration_54.json — backend 17/17 pytest PASS, frontend 13/13 flows PASS (popup persistence, audience targeting, board-only, read counts, hide/delete). Cascade-delete added + verified post-test (381 notifications removed). Regression file: backend/tests/test_iter54_announcements.py.
**Known pre-existing (unrelated):** WorkerLayout console hydration warning '<span> in <option>'.

## 2026-07-02 — Custom Commission Rates + CRM Pipeline Upgrade — DONE
**Scope (user-confirmed):** (1) Editable global default rates in-app + per-VA overrides covering ALL rate types (flat cleaning $, commercial %, digital %); (2) full CRM: kanban board toggle, follow-up dates w/ overdue flags, contact log, 2-way admin↔VA comments, stage notifications; VAs see full timeline + comments + follow-up; table↔board toggle (not replace).

**Backend:**
- `va_commission.py`: `_resolve_commission_config(va_user_id)` — hardcoded defaults ← app_settings (commission_rates dict, commercial_pct, digital_commission_pct) ← per-VA `user.commission_overrides`; `_calc_commission_for_lead` uses cfg for digital/commercial/flat branches; new models (CommissionSettingsIn, VACommissionOverridesIn, LeadFollowupIn, LeadContactIn, LeadCommentIn); shared CRM helpers apply_lead_followup/contact/comment (comment by admin → notifies VA).
- `routes/pm.py`: GET/PUT /api/pm/commission-settings (validated, returns defaults too); GET/PUT /api/pm/vas/{id}/commission-overrides (full-replace semantics); POST /api/pm/leads/{id}/followup|contacts|comments; stage-change now inserts `lead_stage_changed` notification to VA (except paid, which has its own).
- `routes/va.py`: POST /api/va/leads/{id}/followup|contacts|comments (owner or assigned delivery VA; foreign lead → 404).
- Lead doc new fields: next_followup_at, followup_note, last_contact_at, contact_count, comment_count.

**Frontend:**
- `pages/admin/AdminVARates.jsx` (/ops/va-program/rates, 'Rates' nav): 16 flat-rate inputs + commercial % + digital % + reset-to-defaults.
- `components/admin/VACommissionOverrides.jsx` in AdminVADetail: global-vs-override grid, custom-count badge, clear all.
- `components/admin/PipelineBoard.jsx`: 7-column kanban, HTML5 drag&drop, transition validation toasts, job-value prompt on drop-to-paid, cards show value/contacts/comments/follow-up-overdue.
- `AdminVAPipeline.jsx`: Table↔Board toggle (localStorage persisted), new Follow-up (red when overdue) + Activity columns.
- `LeadDetail.jsx` (shared admin+VA): FollowupCard sidebar (date+note+overdue badge), CrmActions (contact method/outcome log + comment composer), timeline renderers for comment/contact_logged/followup_set.

**Testing:** iteration_55 (18/18 backend + rates/pipeline UI) + iteration_56 (3/3 drag gestures: valid move, invalid rejection, paid prompt). Regression files: backend/tests/test_iter55_rates_and_crm.py.
**Deferred suggestions from review:** extract STAGES/STAGE_TRANSITIONS to shared lib (duplicated in 3 files); board virtualization if leads > 500; pre-existing hydration console warning (tooling-injected, not app code).

## 2026-07-02 — AI Assignment Maker — DONE
**Scope (user-confirmed):** Admin types free text and/or uploads a PDF / Word (.docx) / image work order → AI (Claude Sonnet 4.6 or GPT-5.5 via Emergent LLM key) parses it into a single draft assignment → admin reviews/edits pre-filled form → creates via normal POST /api/gigs → optional blast dialog.

**Backend (`routes/ai_assignments.py`):**
- POST /api/admin/ai-assignments/parse (multipart: text?, model, file?) — admin-only.
- PDF text via pypdf (15 pages max), DOCX via python-docx (paragraphs+tables), images passed as base64 `ImageContent` for vision. 15MB file cap, 20k char doc cap.
- `emergentintegrations.llm.chat` LlmChat with fresh session per request; system prompt returns strict JSON (title, description, category, location preview, address_line, scheduled_local, pay_rate, pay_type, slots, duration_hours, contact_phone, ai_notes, missing_fields) with relative-date resolution ("this Friday" → concrete date).
- `_sanitize_draft` hardens LLM output (enum coercion, numeric guards, length caps).

**Frontend (`pages/admin/AdminAIAssignment.jsx`, /ops/ai-assignment, Sparkle nav):**
- 3-step flow: input (textarea + file chip + model select) → review (editable pre-filled form, ai_notes callout, missing_fields warning) → done (view gig / blast again / create another).
- Blast dialog auto-opens after create with channel checkboxes (in_app/email/sms/push) → POST /api/gigs/{id}/blast.

**Testing:** Backend verified via curl (text w/ Claude, image w/ Claude vision, PDF w/ GPT-5.5 — all fields extracted correctly incl. relative-date resolution). Frontend E2E via testing agent iteration_57.json — 100% pass after fixing missing `AdminAIAssignment` import in App.js (route existed but import was absent → page crash; fixed). Test gig cleaned up.

## 2026-07-02 — Professional Certified Badges & Testing System — DONE
**Scope (user-confirmed):** Badges = specialty trades (cleaning, electrician, plumber, cargo van/box truck, drywall, painting + admin-custom). Workers earn by passing a one-shot multiple-choice test AND uploading proof (cert images/PDFs, portfolio links) → approved only after internal admin review. AI (Claude Sonnet 4.6) generates quiz questions. Badges gate specialty gigs (first access). NO retakes (results stored) — admin has reset override.

**Backend (`routes/badges.py`):**
- Collections: `badges` {badge_id, name, description, color, pass_pct, questions[{q,options,correct_index}], active, seed_key}, `badge_applications` {application_id, badge_id, user_id, status: test_passed|test_failed|pending_review|approved|rejected, score_pct, answers, documents[], portfolio_links[], notes, admin_note, reviewed_by}. `users.certified_badges: [badge_id]`.
- Worker: GET /worker/badges; GET+POST /worker/badges/{id}/test (questions served without correct_index; one attempt enforced); POST/DELETE .../documents (object storage, kind=badge_doc, served via /api/files ACL); POST .../submit (needs ≥1 doc or link → pending_review).
- Admin: badges CRUD (delete cascades: apps, users pull, gigs unset); POST /admin/badges/generate-quiz (Claude via emergentintegrations, validated JSON); GET /admin/badge-applications?status; approve (adds to certified_badges + notification) / reject / reset (deletes app, revokes if approved).
- Gig gating: GigIn/GigPatch.required_badge_id; `_attach_required_badges()` enriches /gigs + /gigs/{id} with required_badge {name,color} + has_required_badge for workers; accept_gig 403s for uncertified; duplicate copies the field.
- Seed: 6 badges × 8 hand-written questions, pass 80%, idempotent ($setOnInsert on seed_key) at startup.

**Frontend:**
- `pages/worker/WorkerCertifications.jsx` (/crew/certifications): badge cards with status chips (CERTIFIED / IN REVIEW / TEST PASSED / FAILED / NOT APPROVED), full-page test screen (radio options, score result), proof panel (doc upload chips, portfolio links, notes, submit for review). Entry points: feed CTA banner + profile link card.
- `pages/admin/AdminBadges.jsx` (/ops/badges, 'Certifications' nav): Review queue tab (status filters, application cards w/ score, doc links, approve/reject w/ note, reset-allow-retake) + Badges tab (CRUD, active toggle, badge dialog with color swatches, question editor, AI test writer).
- Gig gating UI: Create/Edit gig dialogs get 'Required certification' select; admin GigDetail chip; worker feed CERT REQUIRED/CERTIFIED pill; worker gig detail chip + cert-required-card (replaces Request button, links to /crew/certifications).

**Testing:** iteration_70.json — backend 22/22 pytest PASS (regression file backend/tests/test_iter70_badges.py, idempotent), frontend 100% (worker test fail/pass flows, proof submit, admin approve, AI quiz gen ~30s real Claude, gig gating pill/card/chip, plain-gig regression). Known pre-existing: FeedFilters <span>-in-<option> hydration warning (unrelated).


## 2026-07-02 — Menu Cleanup: Grouped Dropdowns — DONE
**Scope (user-confirmed):** Admin sidebar compressed from a flat 16-item list into 5 sections with dropdowns. Worker bottom nav compressed from 5 crammed tabs into 4 tabs + "More" popover.

**Admin (`components/admin/AdminLayout.jsx`):**
- Flat "Home" section: Dashboard, Calendar.
- Collapsible "Manage" groups: Work Pipeline (Requests, Quotes, Assignments, AI Assignment, Projects) · People (Workers, Certifications, Referrals, Messages) · Growth (Email Blast, Announcements, Reports) · Finance (Bookkeeping, +Payouts for owners).
- Flat "Settings" below Manage groups.
- "VA Program" now a single collapsible group housing all 7 VA items.
- Auto-expand behavior: group containing the active route opens, others collapse. User can manually toggle; state resets to auto on next route change.
- Collapsed groups show an aggregated badge count derived from their child items (pending requests, quotes, messages, payouts, VA queue). Individual item badges still render when the group is open.
- Applies to both desktop sidebar and mobile drawer (same `renderNavBody` helper).

**Worker (`components/worker/WorkerLayout.jsx`):**
- Bottom nav reduced from 5 → 4 tabs: Feed, My Work, Messages, More.
- "More" opens a shadcn Popover (side=top) exposing "Refer · earn 10%" and "Profile". `data-testid="tab-more"` and `data-testid="worker-more-menu"` for testability. Tab highlights blue when the active route is behind it.

**Testing:** Verified via screenshot smoke tests — admin Assignments page auto-expands Work Pipeline with active row highlighted and sibling groups showing aggregated counts (People 28, Finance 38). Worker view confirms 4-column grid and the More popover renders both items above the tab bar.

## 2026-07-02 — Twilio A2P 10DLC Legal Pages + Worker SMS Opt-In — DONE
**Scope:** User is applying for a Twilio SMS API key and needs (a) publicly-hosted legal pages to submit as consent URLs, and (b) an actual opt-in checkbox on the worker signup form so the flow matches what's promised in those docs.

**Legal pages (public, no auth required):**
- New files: `pages/legal/LegalLayout.jsx`, `PrivacyPolicy.jsx`, `Terms.jsx`, `SmsTerms.jsx`. Shared header/footer with cross-link nav bar.
- Routes wired in `App.js`: `/privacy` (Privacy Policy), `/terms` (Terms & Conditions — Text Messaging Program), `/sms-terms` (SMS Messaging Terms one-pager). Long-form aliases `/privacy-policy`, `/terms-and-conditions`, `/sms-messaging-terms` redirect to the short forms.
- Content lifted verbatim from user-supplied PDFs. Effective Date set to Feb 26, 2026 (easy string-search to update).
- Landing footer links to all three (`data-testid="footer-privacy-link"` etc.).

**Worker signup SMS opt-in:**
- `Register.jsx`: added mobile phone input + non-pre-checked checkbox with full Twilio-compliant consent language (message topics, 1–10/month frequency, msg&data rates, STOP/HELP, "consent is not a condition of joining") and inline links to `/privacy` + `/sms-terms`. Checkbox is disabled until a phone is entered; clearing the phone silently un-opts-in.
- `models.py` `RegisterIn`: added optional `phone` and `sms_opt_in: bool` fields.
- `routes/auth.py` worker signup: writes `phone`, and — only when opt-in=true AND phone is present — records `sms_opt_in: True`, `sms_opt_in_at: <iso timestamp>`, `sms_opt_in_source: "worker_signup_form"` for the A2P 10DLC consent audit trail. Empty phone silently forces `sms_opt_in=False`.

**Testing:** Screenshot smoke test of `/privacy`, `/terms`, `/sms-terms`, and the updated `/register` (checkbox visible with all required disclosures + links). Backend verified via 3 curl scenarios: opt-in+phone → recorded with timestamp/source; opt-in but no phone → ignored (False); phone but opt-in=false → phone kept, opt-in False. Lint clean.

**Twilio submission URLs (post-deploy):** `https://hcobnetwork.com/privacy` · `https://hcobnetwork.com/terms` · `https://hcobnetwork.com/sms-terms`.


## 2026-07-02 — Notification Bell + Past-Date Gig Auto-Complete + Thread Close — DONE
**Scope:** Worker feed felt cluttered (customer chats from long-completed projects still surfaced), and there was no unified notifications surface. Also, gigs whose scheduled date had passed were still showing up in the worker feed and being bookable.

**Backend:**
- `routes/gigs.py`: new `_sweep_expired_gigs()` helper (debounced to once per 60s module-wide) that flips gigs with `scheduled_at < now` and status ∈ {open, coming_soon, filled} to `status="completed"` with an `auto_completed_at` audit stamp. Fires lazily at the top of `GET /gigs` and `GET /gigs/{gig_id}`. Verified on preview: cut open-gig count from 72 → 23; 54 past-date gigs marked with `auto_completed_at`, 0 past-date gigs remained in bookable statuses.
- `routes/gigs.py`: `accept_gig` gained an explicit past-date guard (`_is_past(gig.scheduled_at)`) so even a race between fetch and click can't book a passed assignment. Returns 400 with a friendly message.
- `routes/customer_threads.py`: extended `_is_thread_active()` — for `scope_type=project` threads, checks `_project_has_active_gigs()` (any gig on the project that's open/coming_soon/filled OR has future `scheduled_at`); when none remain the thread is auto-flipped to `closed` with reason `"Project completed — no remaining active gigs"`. Gig-scoped auto-close on gig `completed` still works (unchanged behaviour, now triggered by the sweep too).
- `routes/customer_threads.py`: `/crew/customer-threads/mine` now filters `status != "closed"` at the query level AND runs `_is_thread_active()` per candidate — so a project that just completed drops out of the worker's inbox on the very next poll.

**Frontend:**
- New shared component `components/NotificationBell.jsx` — polls `GET /notifications` every 30s + on `window` event `hcob:notifications-changed`. Renders a bell icon with a red unread badge, popover of the latest 15 items (bullet + title + body + relative timestamp), "Mark all read" bulk action, per-item optimistic mark-read on click. Click routing: `n.url` → `n.project_id` → `n.gig_id` → home fallback. Empty state: "You&apos;re all caught up."
- Wired into `WorkerLayout.jsx` (top-right of the sticky header, next to sign-out) and `AdminLayout.jsx` (mobile: in the top bar next to sign-out; desktop: new sticky top-right action bar inside `<main>`).
- `WorkerCustomerChatsInbox.jsx`: removed the now-dead "Ended" pill + `active/total` split (server already excludes closed threads), simplified counter to `N live`.

**Testing:** Backend curl verified sweep results (0 past-date bookable gigs; 54 past-date + `auto_completed_at` populated). Screenshots verified: worker feed shows bell with 99+ badge + open popover with real notifications; admin desktop shows sticky top-right bar with bell (93 badge); admin mobile bar shows bell next to sign-out. Lint clean.



## 2026-07-03 — BUGFIX: Admin Network Referrals page showed 0 items + "Referral not found" — DONE
**Symptom (reported on production):** Admin `/ops/referrals` showed "ALL (0)", a red "Referral not found" banner, and no worker-submitted leads, even though submissions succeeded.
**Root cause:** In `routes/referrals.py`, `GET /admin/referrals/settings` was registered AFTER `GET /admin/referrals/{referral_id}`, so FastAPI matched the literal string "settings" as a referral_id → 404 "Referral not found". `AdminReferrals.jsx` fetches list + settings via `Promise.all`, so the settings 404 rejected the whole load and the list never rendered (data was intact in the DB the whole time).
**Fix:** Moved the settings GET/PUT route definitions above the `{referral_id}` routes (with a comment noting the ordering constraint). No frontend change needed.
**Verified (preview):** curl — settings returns `{"commission_rate":0.1}`, detail-by-id works, list returns all items. Screenshot — admin referrals page renders full list (149 items incl. fresh worker submission), status pills, no error banner.
**NOTE:** Fix exists in PREVIEW only — user must REDEPLOY for production (hcobnetwork.com) to pick it up.


## 2026-07-03 — P0 SECURITY FIXES (SEC-001, SEC-002, SEC-003) — DONE, VERIFIED 12/12
**SEC-001 — CORS + CSRF:**
- `server.py`: replaced `allow_origins=["*"] + allow_credentials=True` with env-driven allowlist (`CORS_ORIGINS`, comma-separated) + `CORS_ORIGIN_REGEX` (covers *.preview.emergentagent.com, *.emergent.host, hcobnetwork.com/www). Evil origins now get NO CORS headers.
- `backend/.env`: `CORS_ORIGINS` set to explicit preview + production origins; `CORS_ORIGIN_REGEX` added.
- `auth_deps.py cookie_kwargs()`: session cookie `SameSite=None` → `SameSite=Lax` (frontend + API are same-origin in both preview and prod) — native CSRF defense. HttpOnly + Secure kept.
**SEC-002 — token leak via file URLs:**
- `routes/profile.py download_file`: removed `?auth=<token>` query-param auth entirely; endpoint now uses `Depends(get_current_user)` (cookie or Authorization Bearer). Frontend never used ?auth= (uses `fetch(..., credentials:'include')` / same-site cookies) so no client change needed. Session-expiry check now enforced on file GETs too (was previously missing).
**SEC-003 — stored XSS via uploads:**
- `storage.py`: new `validate_upload(data, filename, allow_pdf)` — magic-byte sniffing via `filetype` lib; allowlist jpg/png/webp/gif (+pdf where allowed); returns the SNIFFED content-type which is what gets stored, so declared-CT spoofing is dead.
- Applied to ALL storage-backed uploads: profile avatar/ID (`_upload_user_image`, was completely unvalidated + now 10MB cap), bookkeeping receipts, badge documents, message attachments. Removed now-dead declared-CT allowlist constants (RECEIPT_TYPES, ALLOWED_DOC_TYPES).
- `download_file` serving: always sends `X-Content-Type-Options: nosniff`; `Content-Disposition: inline` only for image/jpeg,png,webp,gif + application/pdf; anything else forced to `application/octet-stream` + `attachment` (legacy pre-fix files can never execute).
- Installed `filetype==1.2.0`; requirements.txt refreshed via pip freeze.
**Testing:** iteration_71 — 12/12 backend pytest (cookie flags, CORS allow/deny, ?auth=401, HTML-as-jpg 400, real PNG 200, nosniff, cookie+bearer) + frontend E2E (worker+admin login with Lax cookie, logout/re-login, ProtectedImg renders, /ops/referrals 148 items regression pass). Test file: `/app/backend/tests/test_iter71_p0_security.py`.
**NOTE:** Fixes live in PREVIEW — REDEPLOY required for production. Production deploy env should carry the updated CORS_ORIGINS/.env values.
**Remaining (P3 hardening, not yet done):** seeded passwords in startup.py, login rate-limiting, unescaped $regex in admin worker search.


## 2026-07-03 — BUGFIX: Production login broken after deploy ("Something went wrong") — DONE
**Root cause:** Production frontend bundle was built with `REACT_APP_BACKEND_URL=https://www.hcobnetwork.com`, but Cloudflare 308-redirects all www traffic to apex `hcobnetwork.com`. Browsers forbid redirects on CORS preflight (login POST is preflighted), so every API call failed as a network error → frontend generic "Something went wrong." Deployed backend itself was healthy (verified via curl: 401 on bad creds, correct CORS echo + allow-credentials on apex).
**Fix:** `lib/api.js` now exports `BACKEND_URL` via `computeBackendBase()` — if the page is served over https from a different host than the env URL (and not localhost), it uses `window.location.origin` (frontend + backend always share a domain behind the ingress). Preview/localhost behavior unchanged. Also pointed the 4 stray direct users of `process.env.REACT_APP_BACKEND_URL` (CustomerChatDialog, QuoteRequestForm, CustomerChat, Landing) at the shared lib.
**Verified:** node unit-check of all 4 host scenarios (prod apex→origin FIX, preview→env, localhost→env, www→env) + preview admin login E2E screenshot (dashboard loads).
**NOTE:** REDEPLOY required for production. Long-term: user should set the deployment custom domain / REACT_APP_BACKEND_URL to the apex `https://hcobnetwork.com` (contact Emergent Support if domain config needs changing).
