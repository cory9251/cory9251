export const EXPENSE_CATEGORIES = [
  { value: "supplies", label: "Supplies" },
  { value: "travel_fuel", label: "Travel / Fuel" },
  { value: "equipment", label: "Equipment" },
  { value: "software", label: "Software / Subscriptions" },
  { value: "contractor_pay", label: "Contractor Pay" },
  { value: "payroll", label: "Payroll" },
  { value: "marketing", label: "Marketing" },
  { value: "insurance", label: "Insurance" },
  { value: "rent_utilities", label: "Rent / Utilities" },
  { value: "taxes_fees", label: "Taxes / Fees" },
  { value: "other", label: "Other" },
];

export const INCOME_CATEGORIES = [
  { value: "assignment_income", label: "Assignment Payment" },
  { value: "project_income", label: "Project Payment" },
  { value: "digital_income", label: "Digital Services Payment" },
  { value: "referral_income", label: "Referral Income" },
  { value: "other_income", label: "Other Income" },
];

const ALL = [...EXPENSE_CATEGORIES, ...INCOME_CATEGORIES];

export const categoryLabel = (v) =>
  ALL.find((o) => o.value === v)?.label || v?.replace(/_/g, " ") || "—";

export const money = (n) =>
  `$${Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
