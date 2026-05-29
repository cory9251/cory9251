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

## Backlog
### P1
- [ ] Worker push/email notification preferences (opt-in per channel)
- [ ] Geo-fenced / city filter for gig feed
- [ ] Email + SMS provider keys collection UI (admin settings)
- [ ] Calendar view for admin (upcoming scheduled gigs)
- [ ] Rich gig templates per category (cleaning checklist, labor PPE notes, ride pickup address)

### P2
- [ ] Worker ratings + reliability score after gig completion
- [ ] Recurring gigs (auto-blast weekly)
- [ ] Stripe payouts for completed gigs
- [ ] Worker chat / direct message admin
- [ ] CSV export of acceptances per gig

## Next steps
1. Wire real Resend + Twilio keys (admin to provide), then enable per-blast email/SMS
2. Add worker mobile-app PWA install prompt
3. Add admin settings page for managing channel credentials
