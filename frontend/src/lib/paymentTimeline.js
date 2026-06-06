// Single source of truth for payment-timeline values, labels, and pill styles
// shown across CreateGigDialog, EditGigDialog, gig detail pages, the worker
// feed, the public landing snippet, and the public share endpoint.
import { Lightning, CalendarBlank, ClockClockwise, Note } from "@phosphor-icons/react";

export const PAYMENT_TIMELINE_OPTIONS = [
  {
    value: "same_day",
    label: "Same-day pay",
    short: "Same day",
    description: "Paid at gig completion (cash, Cash App, Zelle, etc.)",
    icon: Lightning,
    pillClass: "bg-[#10B981] text-white",
    pulse: true,
  },
  {
    value: "2_3_days",
    label: "2–3 day pay",
    short: "2–3 days",
    description: "After admin approves the timesheet",
    icon: CalendarBlank,
    pillClass: "bg-[#0044FF] text-white",
    pulse: false,
  },
  {
    value: "weekly",
    label: "Weekly payout",
    short: "Weekly",
    description: "Bundled into the regular weekly payroll",
    icon: ClockClockwise,
    pillClass: "bg-[#030712] text-white",
    pulse: false,
  },
  {
    value: "custom",
    label: "Custom — see note",
    short: "Custom",
    description: "Use the note field below to spell out payment terms",
    icon: Note,
    pillClass: "bg-[#F59E0B] text-white",
    pulse: false,
  },
];

export const getPaymentTimeline = (value) =>
  PAYMENT_TIMELINE_OPTIONS.find((o) => o.value === value) ||
  PAYMENT_TIMELINE_OPTIONS[1]; // default 2-3 days
