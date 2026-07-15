import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { HandWaving, SealCheck, Eye } from "@phosphor-icons/react";

// FRD Addendum B — per-gig "I'm Interested" queue (read view; offers = Phase 3).
export default function GigInterestsCard({ gigId, viewCount = 0, interestCount = 0 }) {
  const [interests, setInterests] = useState(null);
  useEffect(() => {
    api
      .get(`/admin/gigs/${gigId}/interests`)
      .then(({ data }) => setInterests(data.interests || []))
      .catch((e) => toast.error(getErr(e)));
  }, [gigId]);

  return (
    <div className="mt-4 border border-[#E5E7EB] bg-white" data-testid="gig-interests-card">
      <div className="flex items-center gap-2 border-b border-[#E5E7EB] bg-[#F9FAFB] px-4 py-3">
        <HandWaving size={16} weight="duotone" className="text-[#0044FF]" />
        <span className="font-display text-sm font-black tracking-tight">
          Interested contractors ({interests ? interests.length : interestCount})
        </span>
        <span className="ml-auto inline-flex items-center gap-1 font-mono-label text-[10px] text-[#4B5563]">
          <Eye size={12} /> {viewCount} views
        </span>
      </div>
      {!interests || interests.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-[#9CA3AF]" data-testid="gig-interests-empty">
          No hands raised yet. Interests land here as workers tap "I'm Interested".
        </div>
      ) : (
        <div className="divide-y divide-[#E5E7EB]">
          {interests.map((i) => (
            <div key={i.interest_id} className="px-4 py-3" data-testid={`interest-row-${i.worker.user_id}`}>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/ops/workers/${i.worker.user_id}`}
                  className="text-sm font-bold text-[#0044FF] hover:underline"
                >
                  {i.worker.name || i.worker.email}
                </Link>
                {i.worker.badge_count > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#10B981] px-2 py-0.5 text-[9px] font-bold text-white">
                    <SealCheck size={10} weight="fill" /> {i.worker.badge_count} cert{i.worker.badge_count === 1 ? "" : "s"}
                  </span>
                )}
                {(i.worker.verified_trades || []).map((t) => (
                  <span key={t} className="rounded-full bg-[#7C3AED] px-2 py-0.5 text-[9px] font-bold uppercase text-white">
                    {t.replace(/_/g, " ")}
                  </span>
                ))}
                <span className="ml-auto text-[10px] text-[#4B5563]">
                  {i.worker.completions} completed · ZIP {i.worker.zip_code || "—"} ·{" "}
                  {new Date(i.created_at).toLocaleDateString()}
                </span>
              </div>
              {(i.note || i.availability) && (
                <div className="mt-1.5 text-xs text-[#4B5563]">
                  {i.note && <span>"{i.note}"</span>}
                  {i.availability && (
                    <span className="ml-2 font-semibold text-[#030712]">Available: {i.availability}</span>
                  )}
                </div>
              )}
              {i.worker.phone && (
                <div className="mt-1 text-[11px] text-[#4B5563]">{i.worker.phone}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
