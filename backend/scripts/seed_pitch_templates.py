"""Seed pitch templates from HCOB_VA_Scripts_v2.pdf.

Run once after deploy:
    python -m scripts.seed_pitch_templates

It's idempotent — re-running won't create duplicates. Skips any template
whose `title` already exists (case-insensitive). New templates are inserted
with `created_by_name='HCOB Training (seed)'` for audit clarity.

Categories map to lead.service_type values so VAs can filter the library
by the same buckets they use on the Submit Lead form.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import db, logger  # noqa: E402


# All scripts grouped by service category. Each entry is
# (title, body, category, channel). Channel is one of dm/email/sms/any.
TEMPLATES: list = [
    # ---- Universal — objection handlers --------------------------------------
    ("Objection: How much does it cost?",
     "Great question — pricing depends on the size of the job and a few details. Let me pass your info to the team and they can get you an exact quote, usually within a few hours. Can I grab your name and best number?",
     "universal", "any"),
    ("Objection: I already have someone",
     "Totally understand — a lot of the people we end up working with said the same thing before they tried us. We focus heavily on getting the details right and building custom plans for each job. No pressure at all — would it hurt to get a comparison quote?",
     "universal", "any"),
    ("Objection: I need to think about it",
     "Of course, no rush at all. I can have the team send you more info so you have everything you need when you're ready. What's the best number for them to reach you?",
     "universal", "any"),
    ("Objection: Are you a real company?",
     "Yes — we're a licensed and insured property services company operating throughout Maryland. Residential, commercial, cleaning, maintenance — we do it all. What were you looking to get done?",
     "universal", "any"),
    ("Objection: I'll find someone on my own",
     "Totally fair — there are a lot of options out there. The difference with our team is we build a custom checklist for every single job, so you get exactly what you paid for and nothing gets missed. Might be worth a quick quote before you decide. Want me to pass your info along?",
     "universal", "any"),

    # ---- Residential cleaning (routine + deep) -------------------------------
    ("Residential: Facebook Group — responding to a post",
     "Hey [Name]! Saw you're looking for a cleaner in the area. I coordinate for a local Maryland cleaning team — we do everything from routine maintenance cleans to full deep cleans, and we build a custom checklist for every job so you get exactly what you need. What size is your home?",
     "routine", "dm"),
    ("Residential: Facebook Marketplace — cold post response",
     "Hi! I work with a local property services team covering all of Maryland. We specialize in residential cleaning and every job comes with a custom plan — no generic checklists. Want me to have someone reach out with a quick quote?",
     "routine", "dm"),
    ("Residential: Craigslist — response to 'Cleaner Wanted' ad",
     "Hi [Name], saw your post looking for a cleaning service. I coordinate for a Maryland-based team that handles residential cleans statewide. We do one-time and recurring service and every job is fully customized. Can I grab a few details to get you a quote?",
     "routine", "any"),
    ("Residential: Nextdoor — recommendation request",
     "Hi [Name] - I can help with that! I work with a local Maryland cleaning team. We do routine and deep cleans throughout the area and we're known for being detail-oriented — custom checklist for every job. Want me to pass your info along for a quote?",
     "routine", "dm"),
    ("Residential: Direct message — cold outreach",
     "Hey [Name]! I noticed you mentioned needing help with cleaning. I coordinate for a local Maryland property services team and we do residential cleans all over the state. Would you be open to getting a quick quote? No pressure at all.",
     "routine", "dm"),
    ("Residential: Qualification questions (5 fields)",
     "Awesome — a few quick questions so I can get this to the right person on our team.\n• How many bedrooms and bathrooms does the home have?\n• Is this a one-time clean or are you looking for something recurring?\n• Any specific areas you really want us to focus on — like inside the oven, fridge, baseboards?\n• What's a good date or timeframe to get started?\n• And can I grab your full name and best phone number? The team will follow up directly with pricing.",
     "routine", "any"),
    ("Residential: Follow-up — 24h no response",
     "Hey [Name], just following up on my last message. Still interested in getting a cleaning quote? The team has some availability coming up and I'd hate for you to miss out. Let me know!",
     "routine", "dm"),
    ("Residential: Follow-up — they said 'think about it'",
     "Hi [Name] - just checking back in. No rush at all, but wanted to make sure you had everything you needed to decide. Happy to answer any questions before I send your info over to the team.",
     "routine", "dm"),
    ("Residential: After submitting — confirm with prospect",
     "Great news — I've passed your info along to our scheduling team. Someone will be reaching out shortly to confirm details and pricing. Is there anything specific you want me to flag for them?",
     "routine", "dm"),

    # ---- Commercial cleaning ------------------------------------------------
    ("Commercial: LinkedIn — office manager / facilities director",
     "Hi [Name] - I work with a Maryland-based commercial property services company. We handle office cleaning, medical facilities, retail spaces, and more throughout the state. Do you currently have a cleaning service in place, or is that something you've been looking to get set up?",
     "commercial", "dm"),
    ("Commercial: Facebook Business Group — cold post",
     "Hey everyone — I coordinate commercial cleaning and property services for a Maryland-based team. We work with offices, medical suites, retail stores, and more. If your business is looking for reliable, recurring cleaning coverage, feel free to DM me. Happy to get you a free quote.",
     "commercial", "dm"),
    ("Commercial: Craigslist — commercial cleaning wanted response",
     "Hi [Name], saw your post looking for commercial cleaning. I work with a Maryland-based property services team that specializes in office and facility cleaning. We do recurring and one-time service. Can I grab a few details to get a proposal put together?",
     "commercial", "any"),
    ("Commercial: Direct message — business page / owner",
     "Hi [Name] - I noticed your business is based in [city]. I coordinate commercial cleaning services for a Maryland team that works with offices, retail, and specialty facilities. Would you be open to a quick conversation about your cleaning needs?",
     "commercial", "dm"),
    ("Commercial: Qualification questions (5 fields)",
     "Perfect — a few questions so I can get the right proposal to you.\n• What type of facility is it — office, medical, retail, warehouse?\n• Roughly how large is the space — square footage or number of rooms?\n• How often are you looking for service — daily, weekly, bi-weekly?\n• Do you currently have a cleaning service, or is this a new need?\n• What's the best name and phone number for our team to follow up with a proposal?",
     "commercial", "any"),
    ("Commercial: Follow-up — 48h LinkedIn/Email",
     "Hi [Name] — just circling back on my previous message. I know things get busy. Our team works with a number of businesses in your area and we're currently booking new accounts. Would a quick 5-minute conversation this week work?",
     "commercial", "any"),
    ("Commercial: Follow-up — went quiet",
     "Hey [Name] — wanted to follow up since we last spoke. Our team is still available to put together a proposal for you. It takes about 10 minutes on their end once I send over your details. Still interested?",
     "commercial", "dm"),

    # ---- Move-out cleaning --------------------------------------------------
    ("Move-out: Facebook — 'we're moving' post",
     "Congrats on the move, [Name]! I coordinate for a Maryland cleaning team that specializes in move-out cleans. We go room by room — inside appliances, cabinets, everything — so you can hand the keys back with confidence. Want a quick quote?",
     "moveout", "dm"),
    ("Move-out: Nextdoor — moving announcement",
     "Hey [Name] — best of luck with the move! I work with a local cleaning team and we do move-out cleans all over Maryland. A lot of renters use us specifically to make sure they get their deposit back. Would a quote be helpful?",
     "moveout", "dm"),
    ("Move-out: Craigslist — cold post",
     "Hi [Name] - saw your post. I coordinate for a Maryland property services team that does move-out cleans statewide. We cover everything — inside the oven, fridge, cabinets, all surfaces. Can I get a few details to put a quote together?",
     "moveout", "any"),
    ("Move-out: DM — someone mentioning a move",
     "Hey! Saw you mentioned moving soon. I work with a Maryland cleaning team and we do full move-out cleans that cover everything the landlord checks. Would you like me to get someone to reach out with a quote?",
     "moveout", "dm"),
    ("Move-out: Qualification questions (5 fields)",
     "Quick questions — this helps me get you an accurate quote fast.\n• Will the property be empty when we clean, or will furniture still be there?\n• How many bedrooms and bathrooms?\n• Any specific areas you want us to really hit — oven, fridge, carpets, walls?\n• What's your move-out date? We want to make sure we can fit you in before the deadline.\n• Full name and best phone number so the team can reach you directly?",
     "moveout", "any"),
    ("Move-out: Follow-up — hard deadline urgency",
     "Hey [Name] — just following up because I know you have a move-out date coming up. Our team's schedule fills fast around end-of-month. I'd hate for you to not have a cleaner lined up. Still want me to get a quote over to you?",
     "moveout", "dm"),
    ("Move-out: Follow-up — 24h no response",
     "Hi [Name] - just checking in. Still looking for a move-out clean? Team has some openings this week and next. Takes just 2 minutes for me to get your info over to them.",
     "moveout", "dm"),

    # ---- Apartment turnover / Airbnb ----------------------------------------
    ("Apartment turnover: Facebook landlord group — cold post",
     "Hey landlords — I coordinate apartment turnover cleans for a Maryland property services team. Fast, reliable, fully documented with before and after photos every time. If you manage units in Maryland and are looking for a consistent turnover crew, DM me.",
     "apartment_turnover", "dm"),
    ("Apartment turnover: LinkedIn — property manager cold outreach",
     "Hi [Name] - I work with a Maryland property services company that specializes in apartment turnovers. We focus on fast scheduling, consistency, and documentation — before and after photos on every unit. How many properties are you currently managing?",
     "apartment_turnover", "dm"),
    ("Apartment turnover: DM — Airbnb host",
     "Hey [Name]! Do you host on Airbnb or VRBO in Maryland? I coordinate turnover cleans for a local property services team — we do fast, reliable cleanings between guests. Flexible scheduling and same-day availability in most areas. Want to learn more?",
     "apartment_turnover", "dm"),
    ("Apartment turnover: Qualification questions (5 fields)",
     "Great — a few quick questions to get this to the right person on our team.\n• How many units do you manage?\n• What's the average unit size — studio, 1BR, 2BR?\n• How often are you turning units over — weekly, monthly, as-needed?\n• Are you looking for a one-time clean or an ongoing arrangement?\n• Best name and phone number for our team to follow up?",
     "apartment_turnover", "any"),
    ("Apartment turnover: Follow-up — landlord / PM",
     "Hi [Name] — following up from my last message. I know managing properties keeps you busy. If turnover cleaning is something you're looking to get covered consistently, our team has availability right now. Worth a quick conversation?",
     "apartment_turnover", "dm"),

    # ---- Junk removal -------------------------------------------------------
    ("Junk removal: Facebook Marketplace — free stuff / removal post",
     "Hey [Name]! I coordinate junk removal for a Maryland property services team. We haul away furniture, appliances, yard debris — pretty much anything. Would you like me to have someone reach out with a quick quote?",
     "junk_removal", "dm"),
    ("Junk removal: Nextdoor — recommendation request",
     "Hi [Name] — I can help with that! I work with a local Maryland team that does junk removal throughout the state. Fast turnaround and fair pricing. Want me to pass your info along for a quote?",
     "junk_removal", "dm"),
    ("Junk removal: Craigslist — cold post",
     "I coordinate junk removal services for a Maryland property services team — furniture, appliances, yard waste, construction debris. Residential and commercial. If you're looking to clear something out, reply here and I'll get you a quote.",
     "junk_removal", "any"),
    ("Junk removal: Qualification questions (5 fields)",
     "Quick questions so I can get you an accurate quote.\n• What are you looking to get rid of — furniture, appliances, general clutter, yard debris?\n• Roughly how much are we talking — a truck load, half a truck, just a few items?\n• Is it inside the home, in the garage, or outside?\n• When are you hoping to get this taken care of?\n• Name and best number for our team to follow up?",
     "junk_removal", "any"),
    ("Junk removal: Follow-up — 24h no response",
     "Hey [Name] — just following up! Still need that junk hauled away? Our team has openings this week. Takes two minutes to get you a quote — just let me know.",
     "junk_removal", "dm"),

    # ---- Estate cleanout ----------------------------------------------------
    ("Estate cleanout: Facebook Group — estate / inherited home post",
     "Hi [Name] - I came across your post. I coordinate for a Maryland property services team that handles estate cleanouts regularly. We work with families going through transitions like this all the time and we approach every job with care and respect. Would it be helpful to have someone reach out to walk you through what's involved?",
     "estate_cleanout", "dm"),
    ("Estate cleanout: Nextdoor — estate or probate property",
     "Hi [Name] - I can help connect you with our team. We do full estate cleanouts throughout Maryland — everything from furniture and personal items to full property prep for sale. Fully insured and we handle everything with discretion. Want me to have someone follow up?",
     "estate_cleanout", "dm"),
    ("Estate cleanout: DM — difficult cleanout",
     "Hi [Name] - I saw your post and wanted to reach out. I coordinate for a property services team that handles estate cleanouts across Maryland. I know this kind of project can feel overwhelming — our team takes care of everything so you don't have to. No pressure at all, but happy to get you some information if it would help.",
     "estate_cleanout", "dm"),
    ("Estate cleanout: Qualification questions (5 fields)",
     "Whenever you're ready — just a few questions so I can make sure we get the right people on this.\n• Is the property currently occupied or vacant?\n• Are we talking a full cleanout, or more of a partial — certain rooms or items?\n• How large is the property roughly — number of bedrooms or square footage?\n• Is there a timeline involved — a closing date or a deadline you're working toward?\n• Best name and phone number so our team can reach out directly?",
     "estate_cleanout", "any"),
    ("Estate cleanout: Gentle follow-up — sensitive situation",
     "Hi [Name] - just checking in. I know there's a lot going on and no rush at all. Whenever you're ready, our team is here to help make this part easier. Feel free to reach out whenever the time is right.",
     "estate_cleanout", "dm"),

    # ---- Pressure washing ---------------------------------------------------
    ("Pressure washing: Facebook Group — seasonal push",
     "Hey [Name]! I coordinate pressure washing services for a Maryland property team. Driveways, siding, decks, walkways — great time of year to get ahead of it. Want me to have someone send you a quick quote?",
     "pressure_washing", "dm"),
    ("Pressure washing: Nextdoor — recommendation request",
     "Hi [Name] - I can help with that! I work with a local Maryland team that does pressure washing throughout the state. What are you looking to get done — driveway, siding, deck?",
     "pressure_washing", "dm"),
    ("Pressure washing: Craigslist — cold post",
     "Pressure washing services available throughout Maryland — driveways, siding, decks, fences, commercial surfaces. Fast scheduling and free quote. Reply here if interested.",
     "pressure_washing", "any"),
    ("Pressure washing: Qualification questions (5 fields)",
     "Quick questions to get you an accurate quote.\n• What surfaces are you looking to have washed — driveway, siding, deck, all of the above?\n• Roughly how large is the area?\n• Residential or commercial property?\n• When are you hoping to get it done?\n• Name and best number for our team?",
     "pressure_washing", "any"),
    ("Pressure washing: Follow-up — seasonal urgency",
     "Hey [Name] — just following up! Spring schedule fills up fast for pressure washing. Our team still has some openings but wanted to check in before things get booked out. Still interested in a quote?",
     "pressure_washing", "dm"),

    # ---- Carpet cleaning ----------------------------------------------------
    ("Carpet: Facebook — carpet cleaning request",
     "Hey [Name]! I coordinate for a Maryland property services team that does carpet cleaning throughout the state — steam cleaning, stain treatment, pet odors. Want me to get someone to reach out with a quote?",
     "carpet", "dm"),
    ("Carpet: Cross-sell during any cleaning conversation",
     "One more thing while I have you — do you have any carpets that could use a deep clean while the team is there? We can roll it into the same visit and it saves you from coordinating two separate jobs.",
     "carpet", "any"),
    ("Carpet: Nextdoor — pet stain / odor post",
     "Hi [Name] — I can help with that! I work with a Maryland cleaning team that specializes in carpet cleaning including pet stains and odors. Would you like me to have someone follow up with a quote?",
     "carpet", "dm"),
    ("Carpet: Qualification questions (5 fields)",
     "A few quick questions.\n• How many rooms of carpet are we talking?\n• Any specific problem areas — stains, pet odors, high-traffic spots?\n• Is this residential or commercial?\n• Is this standalone or part of a larger cleaning job?\n• Name and phone number for our team?",
     "carpet", "any"),
    ("Carpet: Follow-up — 24h no response",
     "Hey [Name] — just following up on the carpet cleaning. Our team is booking out this week — want me to go ahead and get your info over to them for a quote?",
     "carpet", "dm"),

    # ---- Landscaping --------------------------------------------------------
    ("Landscaping: Nextdoor — yard / lawn post",
     "Hi [Name]! I coordinate landscaping and yard cleanup services for a Maryland property team. Mowing, leaf removal, bush trimming, mulching — we cover it all. Want me to have someone reach out with a quote?",
     "landscaping", "dm"),
    ("Landscaping: Facebook Group — seasonal post",
     "Spring cleanup time! I coordinate landscaping services for a Maryland property team — lawn care, trimming, seasonal cleanups, mulch. If your yard needs some attention, DM me and I'll get a quote started.",
     "landscaping", "dm"),
    ("Landscaping: Craigslist — cold post",
     "Landscaping and yard cleanup services throughout Maryland. Mowing, leaf removal, hedge and bush trimming, seasonal cleanups. Residential and commercial. Reply for a free quote.",
     "landscaping", "any"),
    ("Landscaping: Qualification questions (5 fields)",
     "Perfect — a few quick questions.\n• What does the yard need — mowing, trimming, leaf cleanup, all of it?\n• How large is the property — front yard, back yard, or both?\n• Is this a one-time cleanup or recurring service?\n• When do you need it done?\n• Name and best number for our team?",
     "landscaping", "any"),
    ("Landscaping: Follow-up — seasonal timing",
     "Hey [Name] — just following up. Spring schedule is filling up fast for yard work. Our team still has some availability but didn't want you to get stuck waiting. Still want a quote?",
     "landscaping", "dm"),

    # ---- Handyman -----------------------------------------------------------
    ("Handyman: Nextdoor — handyman request",
     "Hi [Name] - I can help with that! I coordinate for a Maryland property services team that handles handyman work throughout the state — repairs, installations, general maintenance. What do you need done?",
     "handyman", "dm"),
    ("Handyman: Facebook Marketplace — cold post",
     "Handyman services available throughout Maryland — repairs, furniture assembly, fixture installation, drywall, caulking, and more. Residential and commercial. DM me to get a quote.",
     "handyman", "dm"),
    ("Handyman: Craigslist — handyman wanted",
     "Hi [Name] - saw your post. I coordinate for a Maryland property services team that does general handyman work statewide. What's the job? Happy to get a quote over to you quickly.",
     "handyman", "any"),
    ("Handyman: Qualification questions (5 fields)",
     "Quick questions to get this to the right person.\n• What's the job — repair, installation, or general maintenance?\n• Is it residential or commercial?\n• Is this urgent, or are you planning ahead?\n• Do you have materials, or will the team need to source them?\n• Name and number for our team to follow up with a quote?",
     "handyman", "any"),
    ("Handyman: Follow-up — 24h no response",
     "Hey [Name] — just checking in on the handyman request. Our team has some availability this week. Still need the work done? Takes two minutes to get you a quote.",
     "handyman", "dm"),

    # ---- Painting -----------------------------------------------------------
    ("Painting: Facebook Group — cold outreach",
     "Hi [Name]! I coordinate painting services for a Maryland property team — interior, exterior, full homes, rooms, touch-ups, and commercial spaces. Are you working on a project right now or planning ahead?",
     "painting", "dm"),
    ("Painting: Nextdoor — painter request",
     "Hi [Name] - I can help with that! I work with a Maryland property services team that does interior and exterior painting throughout the state. What's the project — a room, full home, exterior?",
     "painting", "dm"),
    ("Painting: Cross-sell during move-out or estate cleanout",
     "One last question — does the property need any painting done? We can roll that in with the cleanout so you're only coordinating one team for everything.",
     "painting", "any"),
    ("Painting: Qualification questions (5 fields)",
     "A few quick questions.\n• Interior, exterior, or both?\n• How many rooms or roughly how large is the space?\n• Residential or commercial?\n• Do you have a color in mind already, or still figuring that out?\n• Name and number so the team can put a quote together?",
     "painting", "any"),
    ("Painting: Follow-up — 48h no response",
     "Hey [Name] — just following up on the painting project. Our team has some schedule availability right now. Still looking to get it done? Happy to get a quote moving for you.",
     "painting", "dm"),

    # ---- Maintenance bundle (multi-service contracts) ----------------------
    ("Maintenance bundle: LinkedIn — property manager cold outreach",
     "Hi [Name] — I work with a Maryland property services company that offers full maintenance programs for landlords and property managers. Cleaning, repairs, lawn care, painting — all coordinated through one team. How many properties are you currently managing?",
     "maintenance_bundle", "dm"),
    ("Maintenance bundle: Facebook landlord group — cold post",
     "Hey landlords — if you're managing properties in Maryland and tired of coordinating five different vendors, I work with a team that handles it all: cleaning, turnover, repairs, maintenance, landscaping. One point of contact. DM me if you want to hear more.",
     "maintenance_bundle", "dm"),
    ("Maintenance bundle: DM — real estate investor",
     "Hi [Name] — I noticed you're active in real estate in the Maryland area. I coordinate property maintenance programs for a Maryland services team — we bundle cleaning, repairs, and ongoing upkeep for investors who manage multiple properties. Would that kind of setup be useful for your portfolio?",
     "maintenance_bundle", "dm"),
    ("Maintenance bundle: Qualification questions (5 fields)",
     "Great — a few questions to help our team put together the right proposal.\n• How many units or properties do you manage?\n• What does your current maintenance setup look like — do you have vendors, or is it ad hoc?\n• What gives you the most headaches right now — cleaning, repairs, lawn care, all of it?\n• Are you open to a bundled monthly maintenance program?\n• Best contact name and phone number for our team to reach out?",
     "maintenance_bundle", "any"),
    ("Maintenance bundle: Follow-up — LinkedIn / DM",
     "Hi [Name] — just following up from my earlier message. I know managing properties keeps you busy. Our team works with a number of landlords in Maryland and is currently taking on new accounts. Would a quick 10-minute conversation be worth it for you?",
     "maintenance_bundle", "dm"),

    # ---- Specialty: medical / dental ----------------------------------------
    ("Specialty medical: LinkedIn — medical / dental office",
     "Hi [Name] - I work with a Maryland property services company that specializes in cleaning for medical and dental facilities. Waiting rooms, operatories, sterilization areas — everything handled to clinical standards. Do you currently have a cleaning service in place, or is that something you've been looking to establish?",
     "specialty_medical", "dm"),

    # ---- Specialty: funeral homes ------------------------------------------
    ("Specialty funeral: LinkedIn / DM — funeral home",
     "Good [morning/afternoon], [Name]. I work with a Maryland property services company that provides discreet, professional cleaning services for funeral facilities — chapels, viewing rooms, and administrative areas. We understand the environment requires a specific level of care and professionalism. Is facility cleaning something you currently have covered?",
     "specialty_funeral", "dm"),

    # ---- Specialty: post-construction --------------------------------------
    ("Specialty construction: Facebook / DM — post-construction",
     "Hey [Name]! I coordinate post-construction cleanup for a Maryland property services team — dust removal, debris cleanup, surface polishing, sticker removal, final prep before occupancy. Working on anything right now that needs a post-construction clean?",
     "specialty_construction", "dm"),
    ("Specialty: Craigslist — specialty / commercial cold post",
     "Specialty cleaning services for medical offices, dental facilities, funeral homes, and post-construction sites throughout Maryland. Discreet, professional, and fully insured. Reply for a free consultation and quote.",
     "specialty", "any"),
    ("Specialty: Qualification questions (5 fields)",
     "A few questions so I can get this to the right person on our team.\n• What type of facility is it?\n• Roughly how large is the space — square footage or number of rooms?\n• How often would you need service — daily, weekly, after-hours only?\n• Are there any specific requirements we should know about — access restrictions, sanitation standards?\n• Best contact name and phone number for our team to reach out with a proposal?",
     "specialty", "any"),
    ("Specialty: Follow-up — professional",
     "Hi [Name] — following up on my previous message. I understand your schedule is demanding. If facility cleaning is something you'd like to explore, our team is currently available for new accounts in your area. Happy to make the introduction whenever the timing works for you.",
     "specialty", "any"),

    # ---- Universal — daily checklist (special) -----------------------------
    ("Universal: Daily closing checklist",
     "Run through this before you close out every day.\n• Did I send at least 20-30 outreach messages across my platforms today?\n• Do I have at least 5-10 active conversations going?\n• Did I collect all 5 required fields on every qualified prospect?\n• Did I submit every qualified lead through the intake form?\n• Did I avoid mentioning the company name, phone, website, or any brand assets?\n• Did I avoid discussing pricing, timelines, or service guarantees with any prospect?\n• Did I follow up with any prospects who went quiet in the last 24-48 hours?\n\nOne habit separates top performers from everyone else: submitting the form on every single qualified lead, every single time. The form is your commission.",
     "universal", "any"),
]


async def seed():
    now = datetime.now(timezone.utc).isoformat()
    created = 0
    skipped = 0
    for title, body, category, channel in TEMPLATES:
        # Case-insensitive title-uniqueness check so re-runs are idempotent.
        existing = await db.pitch_templates.find_one(
            {"title": {"$regex": f"^{title}$", "$options": "i"}}
        )
        if existing:
            skipped += 1
            continue
        await db.pitch_templates.insert_one({
            "template_id": f"tpl_{uuid.uuid4().hex[:12]}",
            "title": title,
            "body": body,
            "category": category,
            "channel": channel,
            "active": True,
            "created_at": now,
            "created_by": "system_seed",
            "created_by_name": "HCOB Training (seed)",
            "updated_at": now,
            "deleted_at": None,
        })
        created += 1
    print(f"Seed complete: {created} new templates, {skipped} skipped (already existed).")
    logger.info(f"pitch_templates seed: {created} new, {skipped} skipped")
    return created, skipped


if __name__ == "__main__":
    asyncio.run(seed())
