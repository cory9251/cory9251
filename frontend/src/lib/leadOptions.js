/**
 * Lead taxonomy — service types and sources.
 *
 * Source of truth for the dropdown options shown on:
 *   • /va/submit (VASubmitLead)
 *   • /ops/va-program/pipeline/:id and /va/leads/:id (LeadDetail)
 *   • /va/templates and /ops/va-program/templates (category filter)
 *
 * Keep values in sync with the Pydantic `LeadServiceType` and `LeadSource`
 * Literals in `/app/backend/va_commission.py`. Backend is authoritative —
 * any value here that the backend doesn't accept will 422 on submit.
 */

export const SERVICE_TYPES = [
  // Residential cleaning
  { value: "routine", label: "Routine cleaning" },
  { value: "deep", label: "Deep cleaning" },
  { value: "moveout", label: "Move-out cleaning" },
  { value: "apartment_turnover", label: "Apartment turnover / Airbnb" },
  { value: "carpet", label: "Carpet cleaning" },
  // Property services
  { value: "junk_removal", label: "Junk removal" },
  { value: "estate_cleanout", label: "Estate cleanout" },
  { value: "pressure_washing", label: "Pressure washing" },
  { value: "landscaping", label: "Landscaping / yard" },
  { value: "handyman", label: "Handyman / repairs" },
  { value: "painting", label: "Painting" },
  { value: "maintenance_bundle", label: "Maintenance bundle (multi-service)" },
  // Commercial / specialty
  { value: "commercial", label: "Commercial cleaning" },
  { value: "specialty_medical", label: "Specialty: Medical / Dental" },
  { value: "specialty_funeral", label: "Specialty: Funeral home" },
  { value: "specialty_construction", label: "Specialty: Post-construction" },
  { value: "specialty", label: "Specialty (other)" },
  { value: "unknown", label: "Unknown / Not sure yet" },
];

export const PROPERTY_SIZES = [
  { value: "studio", label: "Studio" },
  { value: "1br", label: "1 bedroom" },
  { value: "2br", label: "2 bedroom" },
  { value: "3br", label: "3 bedroom" },
  { value: "4br", label: "4 bedroom" },
  { value: "5br", label: "5 bedroom" },
  { value: "commercial", label: "Commercial" },
];

export const LEAD_SOURCES = [
  { value: "facebook_marketplace", label: "Facebook Marketplace" },
  { value: "facebook_groups", label: "Facebook Groups" },
  { value: "craigslist", label: "Craigslist" },
  { value: "nextdoor", label: "Nextdoor" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "reddit", label: "Reddit" },
  { value: "google_maps", label: "Google Maps / Google Business" },
  { value: "cold_email", label: "Cold email" },
  { value: "listing_marketplace", label: "Yelp / Thumbtack / Angi / HomeAdvisor" },
  { value: "direct_message", label: "Direct message" },
  { value: "referral", label: "Referral" },
  { value: "other", label: "Other" },
];

export const DIGITAL_SERVICE_TYPES = [
  { value: "product_sourcing", label: "Source management / product sourcing" },
  { value: "web_development", label: "Website development" },
  { value: "app_development", label: "App development" },
  { value: "social_media_marketing", label: "Social media / marketing" },
  { value: "seo_content", label: "SEO / content writing" },
  { value: "graphic_design", label: "Graphic design / branding" },
  { value: "digital_other", label: "Other digital service" },
];

export const ALL_SERVICE_TYPES = [...SERVICE_TYPES, ...DIGITAL_SERVICE_TYPES];

export const isDigitalService = (v) =>
  DIGITAL_SERVICE_TYPES.some((o) => o.value === v);

/** Reverse-lookup helper used in detail views. */
export const serviceTypeLabel = (v) =>
  ALL_SERVICE_TYPES.find((o) => o.value === v)?.label || v || "—";

export const leadSourceLabel = (v) =>
  LEAD_SOURCES.find((o) => o.value === v)?.label || v?.replace(/_/g, " ") || "—";
