"""Pure value constants shared across the codebase.

No I/O, no env vars — only strings, lists, and lookup tables. Safe to import
from anywhere (no side effects).
"""

# Canonical worker skill tags. Workers select these on their profile; admins
# filter on them. Sub-category strings on gigs use the same values.
WORKER_SKILLS = [
    # Cleaning
    "deep_cleaning",
    "routine_cleaning",
    "moveouts",
    "detailing",
    "window_cleaning",
    "carpet_cleaning",
    "post_construction",
    # Labor
    "hourly_labor",
    "heavy_lifting",
    "forklift",
    "moving",
    "warehouse",
    "landscaping",
    "painting",
    "pressure_washing",
    "carpentry",
    "handyman",
    "junk_removal",
    "plumbing",
    "electrical",
    # Driver / transport
    "driving",
    "delivery",
    "cdl",
    # Soft skills HCOB cares about
    "fast_learner",
    "bilingual",
    "team_lead",
]

SKILL_LABELS = {
    "deep_cleaning": "Deep cleaning",
    "routine_cleaning": "Routine cleaning",
    "moveouts": "Move-outs",
    "detailing": "Detailing",
    "window_cleaning": "Window cleaning",
    "carpet_cleaning": "Carpet cleaning",
    "post_construction": "Post-construction",
    "hourly_labor": "Hourly labor",
    "heavy_lifting": "Heavy lifting",
    "forklift": "Forklift",
    "moving": "Moving",
    "warehouse": "Warehouse",
    "landscaping": "Landscaping",
    "painting": "Painting",
    "pressure_washing": "Pressure washing",
    "carpentry": "Carpentry",
    "handyman": "Handyman",
    "junk_removal": "Junk removal / hauling",
    "plumbing": "Plumbing (licensed)",
    "electrical": "Electrical (licensed)",
    "driving": "Driving",
    "delivery": "Delivery",
    "cdl": "CDL",
    "fast_learner": "Fast learner",
    "bilingual": "Bilingual",
    "team_lead": "Team lead",
}

# Map a gig's category → which skill tags qualify a worker for it
GIG_CATEGORY_TO_SKILLS = {
    "cleaning": [
        "deep_cleaning", "routine_cleaning", "moveouts", "detailing",
        "window_cleaning", "carpet_cleaning", "post_construction",
    ],
    "labor": [
        "hourly_labor", "heavy_lifting", "forklift", "moving",
        "warehouse", "landscaping", "painting", "pressure_washing",
        "carpentry", "handyman", "junk_removal", "plumbing", "electrical",
    ],
    "driver": ["driving", "delivery", "cdl"],
}

AVAILABILITY_OPTIONS = [
    "weekdays", "weekends", "mornings", "evenings", "overnight", "full_time",
]
EXPERIENCE_OPTIONS = ["none", "0_1_yr", "1_3_yr", "3_plus_yr"]
TSHIRT_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]

# ============================================================================
# Worker questionnaire v2 (FRD Addendum A) — classes, trades, attributes
# ============================================================================
WORK_CLASSES = ["general_labor", "specialist"]

GENERAL_CLEANING_SKILLS = [
    "deep_cleaning", "routine_cleaning", "moveouts", "detailing",
    "window_cleaning", "post_construction",
]
GENERAL_LABOR_SKILLS = [
    "hourly_labor", "heavy_lifting", "moving", "warehouse", "driving", "delivery",
]
GENERAL_SKILLS = GENERAL_CLEANING_SKILLS + GENERAL_LABOR_SKILLS

SPECIALIST_TRADES = [
    "painting", "landscaping", "carpet_cleaning", "pressure_washing",
    "carpentry", "handyman", "junk_removal", "plumbing", "electrical",
]
TRADE_LABELS = {
    "painting": "Painting",
    "landscaping": "Landscaping",
    "carpet_cleaning": "Carpet Cleaning",
    "pressure_washing": "Pressure Washing",
    "carpentry": "Carpentry",
    "handyman": "Handyman",
    "junk_removal": "Junk Removal / Hauling",
    "plumbing": "Plumbing (Licensed)",
    "electrical": "Electrical (Licensed)",
}
LICENSED_TRADES = ["plumbing", "electrical"]

WORK_ATTRIBUTES = ["fast_learner", "bilingual", "team_lead"]
ATTRIBUTE_LABELS = {
    "fast_learner": "Fast learner",
    "bilingual": "Bilingual",
    "team_lead": "Team lead experience",
}

# Certification tags that map badge approvals into dispatch skills.
CERT_TAGS = ["forklift", "cdl"]

# Fields required for a worker profile to be considered "complete" — gates the
# ability to request gigs together with id_verified.
REQUIRED_PROFILE_FIELDS = [
    "phone",
    "zip_code",
    "date_of_birth",
    "skills",        # at least 1
    "availability",  # at least 1
    "emergency_contact_name",
    "emergency_contact_phone",
]

# Allowed pin-tag values on a gig. Any active tag pins the gig to the top of
# the worker feed and the public landing snippet. Multiple can be active.
GIG_TAG_VALUES = ("rush", "priority_need", "same_day", "top_pay")
