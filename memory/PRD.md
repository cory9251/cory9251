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

## Backlog
### P1
- [ ] Worker push/email notification preferences (opt-in per channel)
- [ ] Geo-fenced / city filter for gig feed
- [ ] Email + SMS provider keys collection UI (admin settings)
- [ ] Calendar view for admin (upcoming scheduled gigs)
- [ ] Rich gig templates per category (cleaning checklist, labor PPE notes, ride pickup address)

### P2
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

## Next steps
1. Wire real Resend + Twilio keys (admin to provide), then enable per-blast email/SMS
2. Add worker mobile-app PWA install prompt OR convert via Emergent Mobile Agent (Expo/React Native)
3. Google Auth (optional social login)
4. Worker reliability/rating system (auto-compute from punctuality, completion, no-shows)
