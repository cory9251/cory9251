import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  CheckCircle,
  Phone,
  EnvelopeSimple,
  MapPin,
} from "@phosphor-icons/react";

export default function WorkerDetail() {
  const { userId } = useParams();
  const nav = useNavigate();
  const [w, setW] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get(`/admin/workers/${userId}`);
      setW(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [userId]);

  const verify = async () => {
    try {
      await api.post(`/admin/workers/${userId}/verify-id`);
      toast.success("ID verified");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (!w) return <div className="p-10 font-mono-label">Loading…</div>;

  return (
    <div data-testid="worker-detail">
      <div className="border-b border-[#E5E7EB] px-6 py-6 md:px-10">
        <button
          onClick={() => nav("/admin/workers")}
          className="font-mono-label flex items-center gap-2 text-[#4B5563] hover:text-[#030712]"
        >
          <ArrowLeft size={14} /> All workers
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 border-b border-[#E5E7EB]">
        <div className="lg:col-span-2 border-r border-[#E5E7EB] p-6 md:p-10">
          <div className="font-mono-label">Worker profile</div>
          <h1 className="mt-2 font-display text-4xl font-black tracking-tight">{w.name}</h1>

          <div className="mt-6 space-y-2 text-sm">
            <div className="flex items-center gap-3"><EnvelopeSimple size={16} /> {w.email}</div>
            {w.phone && <div className="flex items-center gap-3"><Phone size={16} /> {w.phone}</div>}
            {w.address && <div className="flex items-center gap-3"><MapPin size={16} /> {w.address}</div>}
          </div>

          {w.bio && (
            <div className="mt-6">
              <div className="font-mono-label">Bio</div>
              <p className="mt-2 text-sm text-[#4B5563]">{w.bio}</p>
            </div>
          )}

          {w.skills && w.skills.length > 0 && (
            <div className="mt-6">
              <div className="font-mono-label">Skills</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {w.skills.map((s) => (
                  <span key={s} className="border border-[#030712] px-2 py-1 text-xs font-semibold">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-10">
            <div className="font-mono-label">Accepted gigs ({(w.accepted_gigs || []).length})</div>
            {(!w.accepted_gigs || w.accepted_gigs.length === 0) ? (
              <div className="mt-3 text-sm text-[#4B5563]">None yet.</div>
            ) : (
              <ul className="mt-3 divide-y divide-[#E5E7EB] border border-[#E5E7EB]">
                {w.accepted_gigs.map((a) => (
                  <li
                    key={a.acceptance_id}
                    className="flex items-center justify-between px-4 py-3"
                  >
                    <span className="text-sm font-semibold">{a.gig_id}</span>
                    <span className="text-xs text-[#4B5563]">
                      {new Date(a.accepted_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <aside className="bg-[#F9FAFB] p-6 md:p-10">
          <div className="font-mono-label">Verification</div>
          {w.id_image_path ? (
            <>
              <div className="mt-3 overflow-hidden border border-[#E5E7EB] bg-white">
                <ProtectedImg path={w.id_image_path} alt="Worker ID" />
              </div>
              <div className="mt-4 text-xs text-[#4B5563]">
                Status:{" "}
                <span className={`font-bold ${w.id_verified ? "text-[#10B981]" : "text-[#F59E0B]"}`}>
                  {w.id_verified ? "VERIFIED" : "PENDING REVIEW"}
                </span>
              </div>
              {!w.id_verified && (
                <Button
                  data-testid="verify-id-btn"
                  onClick={verify}
                  className="mt-4 h-11 w-full rounded-none bg-[#10B981] text-white hover:bg-[#0e9971]"
                >
                  <CheckCircle weight="fill" size={16} className="mr-2" /> Mark ID verified
                </Button>
              )}
            </>
          ) : (
            <div className="mt-3 border border-dashed border-[#E5E7EB] p-6 text-sm text-[#4B5563]">
              Worker has not uploaded an ID yet.
            </div>
          )}

          {w.avatar_path && (
            <div className="mt-8">
              <div className="font-mono-label">Profile photo</div>
              <div className="mt-3 overflow-hidden border border-[#E5E7EB] bg-white">
                <ProtectedImg path={w.avatar_path} alt="Profile" />
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function ProtectedImg({ path, alt }) {
  const [blob, setBlob] = useState(null);
  useEffect(() => {
    let url = null;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        setBlob(url);
      } catch {}
    })();
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!blob) return <div className="h-48 w-full animate-pulse bg-[#F0F4FF]" />;
  return <img src={blob} alt={alt} className="w-full" />;
}
