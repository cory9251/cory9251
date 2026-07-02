import React, { useState } from "react";
import { ChartPieSlice, ListBullets, ArrowsClockwise } from "@phosphor-icons/react";
import { BookOverview } from "@/components/admin/bookkeeping/BookOverview";
import { BookTransactions } from "@/components/admin/bookkeeping/BookTransactions";
import { BookRecurring } from "@/components/admin/bookkeeping/BookRecurring";

const TABS = [
  { key: "overview", label: "Overview", icon: ChartPieSlice },
  { key: "transactions", label: "Transactions", icon: ListBullets },
  { key: "recurring", label: "Recurring", icon: ArrowsClockwise },
];

export default function AdminBookkeeping() {
  const [tab, setTab] = useState("overview");

  return (
    <div className="p-6 md:p-10" data-testid="admin-bookkeeping">
      <div className="mb-6">
        <div className="font-mono-label">Finance</div>
        <h1 className="font-display text-4xl font-black tracking-tight">Bookkeeping</h1>
        <p className="mt-2 text-sm text-[#4B5563]">
          Track expenses &amp; income, attach receipts, and see profit &amp; loss across projects.
        </p>
      </div>

      <div className="mb-6 flex border-b border-[#E5E7EB]">
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`book-tab-${t.key}`}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
              tab === t.key
                ? "border-[#0044FF] text-[#030712]"
                : "border-transparent text-[#4B5563] hover:text-[#030712]"
            }`}
          >
            <t.icon size={16} weight="duotone" /> {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <BookOverview />}
      {tab === "transactions" && <BookTransactions />}
      {tab === "recurring" && <BookRecurring />}
    </div>
  );
}
