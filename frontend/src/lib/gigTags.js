// Single source of truth for gig pin-tags. Any tag pins a gig to the top of
// the worker feed and the public landing snippet. Order in TAG_PRIORITY
// determines which tag wins the card's border color when multiple are active.
import { Fire, Warning, Lightning, Star } from "@phosphor-icons/react";

export const TAG_PRIORITY = ["rush", "priority_need", "same_day", "top_pay"];

export const TAG_CONFIG = {
  rush: {
    label: "RUSH",
    icon: Fire,
    pillClass: "bg-gradient-to-r from-[#EF4444] to-[#DC2626] text-white",
    borderClass: "border-2 border-[#EF4444] shadow-[0_0_0_4px_rgba(239,68,68,0.10)]",
    pulse: true,
  },
  priority_need: {
    label: "PRIORITY",
    icon: Warning,
    pillClass: "bg-[#F97316] text-white",
    borderClass: "border-2 border-[#F97316] shadow-[0_0_0_4px_rgba(249,115,22,0.10)]",
    pulse: false,
  },
  same_day: {
    label: "SAME DAY",
    icon: Lightning,
    pillClass: "bg-[#EAB308] text-[#030712]",
    borderClass: "border-2 border-[#EAB308] shadow-[0_0_0_4px_rgba(234,179,8,0.12)]",
    pulse: false,
  },
  top_pay: {
    label: "TOP PAY",
    icon: Star,
    pillClass: "bg-[#0044FF] text-white",
    borderClass: "border-2 border-[#0044FF] shadow-[0_0_0_4px_rgba(0,68,255,0.10)]",
    pulse: false,
  },
};

// Return the strongest active tag's border class (or null if no tags)
export const getTagBorderClass = (tags) => {
  if (!tags || tags.length === 0) return null;
  for (const t of TAG_PRIORITY) {
    if (tags.includes(t)) return TAG_CONFIG[t].borderClass;
  }
  return null;
};

// Return the active tags sorted by priority (for rendering pill stacks)
export const getOrderedTags = (tags) => {
  if (!tags || tags.length === 0) return [];
  return TAG_PRIORITY.filter((t) => tags.includes(t));
};
