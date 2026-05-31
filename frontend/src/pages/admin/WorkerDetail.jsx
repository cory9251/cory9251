import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft,
  CheckCircle,
  Phone,
  EnvelopeSimple,
  MapPin,
  Key,
  Trash,
  Copy,
  Warning,
  ClockCounterClockwise,
  Prohibit,
  PauseCircle,
  ThumbsUp,
} from "@phosphor-icons/react";

export default function WorkerDetail() {
  const { userId } = useParams();
  const nav = useNavigate();
  const [w, setW] = useState(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [resetResult, setResetResult] = useState(null);
  const [resetting, setResetting] = useState(false);

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

  const doReset = async () => {
    setResetting(true);
    try {
      const { data } = await api.post(
        `/admin/workers/${userId}/reset-password`,
        { new_password: newPassword || null }
      );
      setResetResult(data.new_password);
      setNewPassword("");
      toast.success("Password reset — share it with the worker");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setResetting(false);
    }
  };

  const closeReset = () => {
    setResetOpen(false);
    setResetResult(null);
    setNewPassword("");
  };

  const copyPassword = async () => {
    if (!resetResult) return;
    try {
      await navigator.clipboard.writeText(resetResult);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Copy failed — select the text manually");
    }
  };

  const remove = async () => {
    try {
      await api.delete(`/admin/workers/${userId}`);
      toast.success("Worker deleted");
      nav("/admin/workers");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const setStatus = async (action) => {
    try {
      await api.post(`/admin/workers/${userId}/${action}`, {});
      toast.success(
        {
          approve: "Worker approved",
          reject: "Worker rejected",
          suspend: "Worker suspended",
          reinstate: "Worker reinstated",
        }[action]
      );
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
            <div className="font-mono-label">Gig history ({(w.accepted_gigs || []).length})</div>
            {(!w.accepted_gigs || w.accepted_gigs.length === 0) ? (
              <div className="mt-3 text-sm text-[#4B5563]">None yet.</div>
            ) : (
              <div className="mt-3 overflow-x-auto border border-[#E5E7EB]">
                <table className="w-full text-sm">
                  <thead className="bg-[#F9FAFB]">
                    <tr className="text-left">
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Gig</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Status</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">In</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Out</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Hours</th>
                    </tr>
                  </thead>
                  <tbody>
                    {w.accepted_gigs.map((a) => (
                      <tr key={a.acceptance_id} className="hover:bg-[#F9FAFB]">
                        <td className="border-b border-[#E5E7EB] px-3 py-2 font-semibold">
                          {a.gig_title || a.gig_id}
                          {a.gig_scheduled_date && (
                            <div className="text-[10px] font-normal text-[#4B5563]">
                              {a.gig_scheduled_date}
                            </div>
                          )}
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2">
                          <StatusPill s={a.status} />
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                          {a.clock_in_at ? new Date(a.clock_in_at).toLocaleString() : "—"}
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                          {a.clock_out_at ? new Date(a.clock_out_at).toLocaleString() : "—"}
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2 font-bold">
                          {a.hours_worked != null ? `${a.hours_worked.toFixed(2)}h` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <aside className="bg-[#F9FAFB] p-6 md:p-10">
          <ApplicationStatusCard worker={w} onAction={setStatus} />

          <div className="mt-8 font-mono-label">Verification</div>
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

          <div className="mt-10 border-t border-[#E5E7EB] pt-6">
            <div className="font-mono-label">Account management</div>
            <Button
              data-testid="reset-password-btn"
              onClick={() => setResetOpen(true)}
              variant="outline"
              className="mt-3 h-11 w-full rounded-none border-[#030712]"
            >
              <Key size={16} className="mr-2" /> Reset password
            </Button>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  data-testid="delete-worker-btn"
                  variant="outline"
                  className="mt-3 h-11 w-full rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                >
                  <Trash size={16} className="mr-2" /> Delete worker
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="rounded-none">
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this worker?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Permanently removes <span className="font-semibold">{w.name}</span> ({w.email})
                    along with all of their gig acceptances, sessions, and uploaded files.
                    Slots on currently accepted gigs will be released back to open.
                    This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="rounded-none">Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    data-testid="confirm-delete-worker"
                    className="rounded-none bg-[#EF4444]"
                    onClick={remove}
                  >
                    Delete permanently
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </aside>
      </div>

      {/* Reset-password dialog */}
      <Dialog open={resetOpen} onOpenChange={(o) => (o ? setResetOpen(true) : closeReset())}>
        <DialogContent
          className="max-w-md rounded-none border-[#030712]"
          data-testid="reset-password-dialog"
        >
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-black">
              Reset password
            </DialogTitle>
          </DialogHeader>

          {resetResult ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2 border border-[#F59E0B] bg-[#FFFBEB] p-3 text-xs text-[#92400E]">
                <Warning size={16} weight="fill" className="mt-0.5 shrink-0" />
                <div>
                  This password is shown <strong>once</strong>. Copy it and send it
                  to the worker now — you won't be able to see it again.
                </div>
              </div>
              <div>
                <div className="font-mono-label">New password</div>
                <div className="mt-2 flex items-center gap-2">
                  <code
                    data-testid="new-password-value"
                    className="flex-1 select-all break-all border border-[#030712] bg-[#F9FAFB] px-3 py-2 font-mono text-lg font-bold"
                  >
                    {resetResult}
                  </code>
                  <Button
                    data-testid="copy-password-btn"
                    onClick={copyPassword}
                    className="h-11 rounded-none bg-[#030712] text-white"
                  >
                    <Copy size={14} className="mr-1" /> Copy
                  </Button>
                </div>
              </div>
              <Button
                data-testid="reset-done-btn"
                onClick={closeReset}
                className="h-11 w-full rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
              >
                Done
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-[#4B5563]">
                Set a new password for <strong>{w.name}</strong>. Leave blank to
                auto-generate a short, easy-to-share temp password. The worker's
                existing sessions will be force-signed-out.
              </p>
              <div>
                <Label className="font-mono-label">New password (optional)</Label>
                <Input
                  data-testid="reset-password-input"
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Leave blank to auto-generate"
                  className="mt-2 h-11 rounded-none border-[#030712] font-mono"
                />
                <div className="mt-1 text-[11px] text-[#4B5563]">
                  Minimum 6 characters if you set it manually.
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-none"
                  onClick={closeReset}
                >
                  Cancel
                </Button>
                <Button
                  data-testid="confirm-reset-btn"
                  onClick={doReset}
                  disabled={resetting}
                  className="rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
                >
                  {resetting ? "Resetting…" : "Reset password"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatusPill({ s }) {
  const map = {
    accepted: { bg: "bg-[#0044FF]", label: "ACCEPTED" },
    on_the_clock: { bg: "bg-[#F59E0B]", label: "ON THE CLOCK" },
    completed: { bg: "bg-[#10B981]", label: "COMPLETED" },
  };
  const m = map[s] || { bg: "bg-[#4B5563]", label: (s || "").toUpperCase() };
  return (
    <span className={`inline-block px-2 py-0.5 text-[10px] font-bold tracking-widest text-white ${m.bg}`}>
      {m.label}
    </span>
  );
}

function ApplicationStatusCard({ worker, onAction }) {
  const status = worker.worker_status || "approved";
  const meta = {
    pending: {
      bg: "bg-[#FFFBEB]",
      border: "border-[#F59E0B]/40",
      icon: ClockCounterClockwise,
      title: "Application pending",
      desc: "This worker registered and is waiting for you to review them.",
      tone: "text-[#92400E]",
    },
    approved: {
      bg: "bg-[#ECFDF5]",
      border: "border-[#10B981]/30",
      icon: CheckCircle,
      title: "Approved",
      desc: "Approved to claim gigs (subject to ID verification).",
      tone: "text-[#065F46]",
    },
    rejected: {
      bg: "bg-[#FEF2F2]",
      border: "border-[#EF4444]/30",
      icon: Prohibit,
      title: "Rejected",
      desc: "Cannot claim gigs. Reinstate to re-enable.",
      tone: "text-[#991B1B]",
    },
    suspended: {
      bg: "bg-[#F3F4F6]",
      border: "border-[#9CA3AF]/40",
      icon: PauseCircle,
      title: "Suspended",
      desc: "Account is suspended. Reinstate to re-enable.",
      tone: "text-[#374151]",
    },
  }[status] || {
    bg: "bg-[#F9FAFB]",
    border: "border-[#E5E7EB]",
    icon: CheckCircle,
    title: status.toUpperCase(),
    desc: "",
    tone: "text-[#030712]",
  };
  const Icon = meta.icon;
  return (
    <div
      data-testid="application-status-card"
      className={`rounded-none border ${meta.border} ${meta.bg} p-4`}
    >
      <div className="font-mono-label">Application status</div>
      <div className={`mt-2 flex items-center gap-2 ${meta.tone}`}>
        <Icon size={20} weight="fill" />
        <div className="font-display text-lg font-black">{meta.title}</div>
      </div>
      <p className={`mt-2 text-xs ${meta.tone}/90`}>{meta.desc}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {status !== "approved" && (
          <Button
            data-testid="approve-btn"
            onClick={() => onAction(status === "rejected" || status === "suspended" ? "reinstate" : "approve")}
            className="h-9 rounded-none bg-[#10B981] text-white hover:bg-[#0e9971]"
          >
            <ThumbsUp size={14} className="mr-1" weight="fill" />
            {status === "rejected" || status === "suspended" ? "Reinstate" : "Approve"}
          </Button>
        )}
        {status !== "rejected" && (
          <Button
            data-testid="reject-btn"
            onClick={() => onAction("reject")}
            variant="outline"
            className="h-9 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
          >
            <Prohibit size={14} className="mr-1" /> Reject
          </Button>
        )}
        {status === "approved" && (
          <Button
            data-testid="suspend-btn"
            onClick={() => onAction("suspend")}
            variant="outline"
            className="h-9 rounded-none border-[#4B5563] text-[#4B5563] hover:bg-[#4B5563] hover:text-white"
          >
            <PauseCircle size={14} className="mr-1" /> Suspend
          </Button>
        )}
      </div>
      {worker.worker_status_at && (
        <div className="mt-3 font-mono-label text-[10px]">
          Updated {new Date(worker.worker_status_at).toLocaleString()}
          {worker.worker_status_by ? ` by ${worker.worker_status_by}` : ""}
        </div>
      )}
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
