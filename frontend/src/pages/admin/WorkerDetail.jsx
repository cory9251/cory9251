import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StarsDisplay } from "@/components/admin/RatingDialog";
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
  CurrencyDollar,
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
          <h1 className="mt-2 font-display text-4xl font-black tracking-tight">
            {w.name}
          </h1>
          <div className="mt-1 text-sm text-[#4B5563]">{w.email}</div>
          <div className="mt-3">
            <StarsDisplay value={w.rating_avg} count={w.rating_count} size={14} />
            {w.admin_rating_count > 0 && w.client_rating_count > 0 && (
              <div className="mt-1 text-[10px] text-[#4B5563]">
                Admin: {w.admin_rating_avg?.toFixed(1)} ({w.admin_rating_count})
                {" · "}
                Client: {w.client_rating_avg?.toFixed(1)} ({w.client_rating_count})
              </div>
            )}
          </div>

          <AdminProfileEditor worker={w} onSaved={load} />

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
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Hrs</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Rate</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">Earned</th>
                      <th className="border-b border-[#E5E7EB] px-3 py-2 font-mono-label">TS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {w.accepted_gigs.map((a) => {
                      const rate = a.pay_rate_applied != null ? a.pay_rate_applied : a.pay_rate_effective;
                      const ptype = a.pay_type_applied || a.pay_type_effective;
                      return (
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
                        <td className="border-b border-[#E5E7EB] px-3 py-2 text-xs">
                          {rate != null ? `$${Number(rate).toFixed(2)}${ptype === "hourly" ? "/hr" : " flat"}` : "—"}
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2 font-bold text-[#10B981]">
                          {a.earnings != null ? `$${a.earnings.toFixed(2)}` : "—"}
                        </td>
                        <td className="border-b border-[#E5E7EB] px-3 py-2">
                          {!a.clock_out_at ? (
                            <span className="text-xs text-[#4B5563]">—</span>
                          ) : a.timesheet_approved ? (
                            <span className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                              <CheckCircle size={9} weight="fill" /> OK
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                              PENDING
                            </span>
                          )}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <aside className="bg-[#F9FAFB] p-6 md:p-10">
          <ApplicationStatusCard worker={w} onAction={setStatus} />

          <DefaultPayCard worker={w} onSaved={load} />

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

// Static option lists (mirror /api/profile/options server-side enums)
const ADMIN_SKILLS = [
  { value: "deep_cleaning", label: "Deep cleaning" },
  { value: "routine_cleaning", label: "Routine cleaning" },
  { value: "moveouts", label: "Move-outs" },
  { value: "hourly_labor", label: "Hourly labor" },
  { value: "driving", label: "Driving" },
];
const ADMIN_AVAILABILITY = [
  { value: "weekdays", label: "Weekdays" },
  { value: "weekends", label: "Weekends" },
  { value: "mornings", label: "Mornings" },
  { value: "evenings", label: "Evenings" },
  { value: "overnight", label: "Overnight" },
  { value: "full_time", label: "Full-time" },
];
const ADMIN_EXPERIENCE = [
  { value: "", label: "—" },
  { value: "none", label: "No experience" },
  { value: "0_1_yr", label: "Under 1 year" },
  { value: "1_3_yr", label: "1–3 years" },
  { value: "3_plus_yr", label: "3+ years" },
];
const ADMIN_TSHIRT = ["", "XS", "S", "M", "L", "XL", "XXL", "XXXL"];
const ADMIN_STATUSES = [
  { value: "approved", label: "Approved" },
  { value: "pending", label: "Pending" },
  { value: "rejected", label: "Rejected" },
  { value: "suspended", label: "Suspended" },
];

/**
 * Inline admin editor for a worker's full profile. Mirrors the worker
 * self-serve form (skills, availability, vehicle, contact, etc.) and adds
 * admin-only fields (email, worker_status, id_verified). Saves directly to
 * PUT /admin/workers/{id}/profile.
 */
function AdminProfileEditor({ worker, onSaved }) {
  const [form, setForm] = useState(() => fromWorker(worker));
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Re-sync from props after parent refetch
  useEffect(() => {
    setForm(fromWorker(worker));
    setDirty(false);
  }, [worker.user_id, worker.updated_at]);

  const set = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }));
    setDirty(true);
  };
  const toggleArr = (k, v) => {
    setForm((f) => {
      const arr = f[k] || [];
      return {
        ...f,
        [k]: arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v],
      };
    });
    setDirty(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      // Only send keys that are non-undefined; backend treats Optional fields
      // — but we DO want to send empty strings ("clear bio") so we keep them.
      const payload = { ...form };
      // Normalize ZIP / state
      if (payload.zip_code) payload.zip_code = String(payload.zip_code).trim();
      if (payload.state) payload.state = String(payload.state).toUpperCase().slice(0, 2);
      const { data } = await api.put(
        `/admin/workers/${worker.user_id}/profile`,
        payload
      );
      toast.success("Worker profile saved");
      setDirty(false);
      onSaved && onSaved(data);
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={save}
      className="mt-6 space-y-6"
      data-testid="admin-profile-editor"
    >
      {/* Admin override controls (status + ID verified) */}
      <Section title="Admin overrides">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Worker status">
            <select
              data-testid="admin-edit-worker-status"
              value={form.worker_status || "approved"}
              onChange={(e) => set("worker_status", e.target.value)}
              className="h-10 w-full border border-[#030712] bg-white px-2 text-sm"
            >
              {ADMIN_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </FieldRow>
          <FieldRow label="ID verified">
            <label className="flex h-10 cursor-pointer items-center gap-2 border border-[#030712] bg-white px-3 text-sm">
              <input
                data-testid="admin-edit-id-verified"
                type="checkbox"
                checked={!!form.id_verified}
                onChange={(e) => set("id_verified", e.target.checked)}
                className="accent-[#0044FF]"
              />
              <span>Mark ID as verified</span>
            </label>
          </FieldRow>
        </div>
      </Section>

      {/* Identity */}
      <Section title="Identity">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Full name">
            <Input
              data-testid="admin-edit-name"
              value={form.name || ""}
              onChange={(e) => set("name", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="Email (login)">
            <Input
              data-testid="admin-edit-email"
              type="email"
              value={form.email || ""}
              onChange={(e) => set("email", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="Phone">
            <Input
              data-testid="admin-edit-phone"
              value={form.phone || ""}
              onChange={(e) => set("phone", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="Date of birth">
            <Input
              data-testid="admin-edit-dob"
              type="date"
              value={form.date_of_birth || ""}
              onChange={(e) => set("date_of_birth", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
        </div>
      </Section>

      {/* Location */}
      <Section title="Where they work">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <FieldRow label="ZIP">
            <Input
              data-testid="admin-edit-zip"
              value={form.zip_code || ""}
              onChange={(e) =>
                set(
                  "zip_code",
                  e.target.value.replace(/\D/g, "").slice(0, 5)
                )
              }
              inputMode="numeric"
              maxLength={5}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="City">
            <Input
              data-testid="admin-edit-city"
              value={form.city || ""}
              onChange={(e) => set("city", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="State">
            <Input
              data-testid="admin-edit-state"
              value={form.state || ""}
              onChange={(e) =>
                set("state", e.target.value.toUpperCase().slice(0, 2))
              }
              maxLength={2}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="T-shirt">
            <select
              data-testid="admin-edit-tshirt"
              value={form.tshirt_size || ""}
              onChange={(e) => set("tshirt_size", e.target.value)}
              className="h-10 w-full border border-[#030712] bg-white px-2 text-sm"
            >
              {ADMIN_TSHIRT.map((s) => (
                <option key={s} value={s}>
                  {s || "—"}
                </option>
              ))}
            </select>
          </FieldRow>
        </div>
        <FieldRow label="Street address">
          <Input
            data-testid="admin-edit-address"
            value={form.address || ""}
            onChange={(e) => set("address", e.target.value)}
            className="h-10 rounded-none border-[#030712]"
          />
        </FieldRow>
      </Section>

      {/* Skills (the one users had trouble with) */}
      <Section title="Skills" hint="The bit some workers couldn't update — fix it here on their behalf.">
        <div className="flex flex-wrap gap-1.5">
          {ADMIN_SKILLS.map((s) => (
            <Chip
              key={s.value}
              testId={`admin-edit-skill-${s.value}`}
              active={(form.skills || []).includes(s.value)}
              onClick={() => toggleArr("skills", s.value)}
            >
              {s.label}
            </Chip>
          ))}
        </div>
        <FieldRow label="Experience level">
          <select
            data-testid="admin-edit-experience"
            value={form.experience_level || ""}
            onChange={(e) => set("experience_level", e.target.value)}
            className="h-10 w-full border border-[#030712] bg-white px-2 text-sm"
          >
            {ADMIN_EXPERIENCE.map((e) => (
              <option key={e.value} value={e.value}>
                {e.label}
              </option>
            ))}
          </select>
        </FieldRow>
      </Section>

      {/* Availability */}
      <Section title="Availability">
        <div className="flex flex-wrap gap-1.5">
          {ADMIN_AVAILABILITY.map((a) => (
            <Chip
              key={a.value}
              testId={`admin-edit-avail-${a.value}`}
              active={(form.availability || []).includes(a.value)}
              onClick={() => toggleArr("availability", a.value)}
            >
              {a.label}
            </Chip>
          ))}
        </div>
      </Section>

      {/* Vehicle */}
      <Section title="Vehicle">
        <div className="flex flex-wrap gap-1.5">
          <Chip
            testId="admin-edit-has-car"
            active={!!form.has_car}
            onClick={() => set("has_car", !form.has_car)}
          >
            Car
          </Chip>
          <Chip
            testId="admin-edit-has-truck"
            active={!!form.has_truck}
            onClick={() => set("has_truck", !form.has_truck)}
          >
            Truck
          </Chip>
          <Chip
            testId="admin-edit-has-cdl"
            active={!!form.has_cdl}
            onClick={() => set("has_cdl", !form.has_cdl)}
          >
            CDL
          </Chip>
        </div>
      </Section>

      {/* Emergency contact */}
      <Section title="Emergency contact">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Name">
            <Input
              data-testid="admin-edit-ec-name"
              value={form.emergency_contact_name || ""}
              onChange={(e) => set("emergency_contact_name", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
          <FieldRow label="Phone">
            <Input
              data-testid="admin-edit-ec-phone"
              value={form.emergency_contact_phone || ""}
              onChange={(e) => set("emergency_contact_phone", e.target.value)}
              className="h-10 rounded-none border-[#030712]"
            />
          </FieldRow>
        </div>
      </Section>

      {/* Bio */}
      <Section title="Notes">
        <Textarea
          data-testid="admin-edit-bio"
          rows={3}
          value={form.bio || ""}
          onChange={(e) => set("bio", e.target.value)}
          className="rounded-none border-[#030712] text-sm"
          placeholder="Notes about this worker (only HCOB admins see this)"
        />
      </Section>

      <div className="sticky bottom-0 -mx-6 flex items-center justify-between gap-3 border-t border-[#E5E7EB] bg-white px-6 py-3 md:-mx-10 md:px-10">
        <div className="text-xs text-[#4B5563]">
          {dirty ? (
            <span className="font-bold text-[#F59E0B]">Unsaved changes</span>
          ) : (
            <span>All changes saved</span>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!dirty || saving}
            onClick={() => {
              setForm(fromWorker(worker));
              setDirty(false);
            }}
            className="h-10 rounded-none"
            data-testid="admin-edit-cancel"
          >
            Discard
          </Button>
          <Button
            type="submit"
            disabled={!dirty || saving}
            className="h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            data-testid="admin-edit-save"
          >
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </div>
    </form>
  );
}

function fromWorker(w) {
  return {
    name: w.name || "",
    email: w.email || "",
    phone: w.phone || "",
    address: w.address || "",
    bio: w.bio || "",
    skills: w.skills || [],
    zip_code: w.zip_code || "",
    city: w.city || "",
    state: w.state || "",
    date_of_birth: w.date_of_birth || "",
    has_car: !!w.has_car,
    has_truck: !!w.has_truck,
    has_cdl: !!w.has_cdl,
    experience_level: w.experience_level || "",
    availability: w.availability || [],
    emergency_contact_name: w.emergency_contact_name || "",
    emergency_contact_phone: w.emergency_contact_phone || "",
    tshirt_size: w.tshirt_size || "",
    worker_status: w.worker_status || "approved",
    id_verified: !!w.id_verified,
  };
}

function Section({ title, hint, children }) {
  return (
    <section className="border border-[#E5E7EB] bg-white p-4">
      <div className="font-mono-label">{title}</div>
      {hint && <p className="mt-1 text-[10px] text-[#4B5563]">{hint}</p>}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function FieldRow({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-bold uppercase tracking-widest text-[#4B5563]">
        {label}
      </Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function Chip({ active, onClick, children, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${
        active
          ? "border-[#0044FF] bg-[#0044FF] text-white"
          : "border-[#E5E7EB] bg-white text-[#030712] hover:border-[#0044FF]"
      }`}
    >
      {children}
    </button>
  );
}


function DefaultPayCard({ worker, onSaved }) {
  const [rate, setRate] = useState(
    worker.default_pay_rate != null ? String(worker.default_pay_rate) : ""
  );
  const [type, setType] = useState(worker.default_pay_type || "hourly");
  const [saving, setSaving] = useState(false);

  // Re-sync if worker prop changes (after save)
  useEffect(() => {
    setRate(
      worker.default_pay_rate != null ? String(worker.default_pay_rate) : ""
    );
    setType(worker.default_pay_type || "hourly");
  }, [worker.default_pay_rate, worker.default_pay_type]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {};
      const trimmed = String(rate).trim();
      if (trimmed === "") {
        payload.clear_rate = true;
      } else {
        const n = Number(trimmed);
        if (!Number.isFinite(n) || n < 0) {
          toast.error("Enter a non-negative number for the rate");
          setSaving(false);
          return;
        }
        payload.default_pay_rate = n;
      }
      payload.default_pay_type = type;
      await api.put(`/admin/workers/${worker.user_id}/pay`, payload);
      toast.success("Default pay saved");
      onSaved && onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || err.message);
    } finally {
      setSaving(false);
    }
  };

  const clearAll = async () => {
    if (!confirm("Clear this worker's default pay? Future gigs will use the gig's posted rate.")) return;
    setSaving(true);
    try {
      await api.put(`/admin/workers/${worker.user_id}/pay`, {
        clear_rate: true,
        clear_type: true,
      });
      toast.success("Default pay cleared");
      onSaved && onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      data-testid="default-pay-card"
      className="mt-6 rounded-none border border-[#E5E7EB] bg-white p-4"
    >
      <div className="font-mono-label flex items-center gap-1.5">
        <CurrencyDollar size={12} weight="duotone" /> Default pay
      </div>
      <p className="mt-2 text-xs text-[#4B5563]">
        Used as a fallback when a gig doesn't have a per-gig override for this
        worker. Leave blank to fall back to the posted gig rate.
      </p>

      <form onSubmit={save} className="mt-4 space-y-3">
        <div>
          <Label className="font-mono-label">Rate ($)</Label>
          <Input
            data-testid="worker-default-pay-rate"
            type="number"
            step="0.01"
            min="0"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            placeholder="e.g. 22.50"
            className="mt-1 h-10 rounded-none border-[#030712]"
          />
        </div>
        <div>
          <Label className="font-mono-label">Pay type</Label>
          <div className="mt-1 grid grid-cols-2 gap-2">
            {["hourly", "flat"].map((t) => (
              <button
                key={t}
                type="button"
                data-testid={`worker-default-pay-type-${t}`}
                onClick={() => setType(t)}
                className={`h-10 border text-xs font-bold tracking-widest uppercase ${
                  type === t
                    ? "border-[#0044FF] bg-[#0044FF] text-white"
                    : "border-[#030712] bg-white text-[#030712]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap justify-between gap-2 pt-1">
          <Button
            type="button"
            variant="outline"
            onClick={clearAll}
            disabled={saving}
            className="h-9 rounded-none border-[#4B5563] text-[11px]"
          >
            Clear
          </Button>
          <Button
            type="submit"
            data-testid="save-worker-default-pay"
            disabled={saving}
            className="h-9 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            {saving ? "Saving…" : "Save default pay"}
          </Button>
        </div>
      </form>
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
