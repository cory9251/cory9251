import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  Megaphone,
  Trash,
  Copy,
  PencilSimple,
  EnvelopeSimple,
  DeviceMobile,
  Bell,
  CheckCircle,
  EyeSlash,
  UserPlus,
  UserMinus,
  CurrencyDollar,
  ClipboardText,
} from "@phosphor-icons/react";
import EditGigDialog from "@/components/admin/EditGigDialog";
import AssignWorkerDialog from "@/components/admin/AssignWorkerDialog";
import PayOverrideDialog from "@/components/admin/PayOverrideDialog";
import ApproveTimesheetDialog from "@/components/admin/ApproveTimesheetDialog";

export default function GigDetail() {
  const { gigId } = useParams();
  const nav = useNavigate();
  const [gig, setGig] = useState(null);
  const [blastOpen, setBlastOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [payDialog, setPayDialog] = useState(null); // { acceptance }
  const [approveDialog, setApproveDialog] = useState(null); // { acceptance }
  const [duplicating, setDuplicating] = useState(false);
  const [channels, setChannels] = useState({ in_app: true, email: false, sms: false });
  const [blasting, setBlasting] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/gigs/${gigId}`);
      setGig(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [gigId]);

  const remove = async () => {
    try {
      await api.delete(`/gigs/${gigId}`);
      toast.success("Gig deleted");
      nav("/admin/gigs");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const duplicate = async () => {
    setDuplicating(true);
    try {
      const { data } = await api.post(`/gigs/${gigId}/duplicate`);
      toast.success("Gig duplicated");
      nav(`/admin/gigs/${data.gig_id}`);
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setDuplicating(false);
    }
  };

  const removeWorker = async (a) => {
    if (!confirm(`Remove ${a.worker_name || "this worker"} from this gig?`)) return;
    try {
      await api.delete(`/gigs/${gigId}/acceptances/${a.acceptance_id}`);
      toast.success(`${a.worker_name || "Worker"} removed`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const sendBlast = async () => {
    const arr = Object.entries(channels)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (arr.length === 0) {
      toast.error("Select at least one channel");
      return;
    }
    setBlasting(true);
    try {
      const { data } = await api.post(`/gigs/${gigId}/blast`, { channels: arr });
      const c = data.counts;
      toast.success(
        `Blast sent — in-app ${c.in_app}, email ${c.email}, SMS ${c.sms}`
      );
      setBlastOpen(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBlasting(false);
    }
  };

  if (!gig) {
    return (
      <div className="p-10 font-mono-label" data-testid="gig-loading">Loading gig…</div>
    );
  }

  return (
    <div data-testid="admin-gig-detail">
      <div className="border-b border-[#E5E7EB] px-6 py-6 md:px-10">
        <button
          onClick={() => nav("/admin/gigs")}
          className="font-mono-label flex items-center gap-2 text-[#4B5563] hover:text-[#030712]"
        >
          <ArrowLeft size={14} /> All gigs
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 border-b border-[#E5E7EB]">
        <div className="lg:col-span-2 border-r border-[#E5E7EB] p-6 md:p-10">
          <div className="font-mono-label">
            {gig.category.toUpperCase()} · {gig.subcategory || "general"}
          </div>
          <h1 className="mt-2 font-display text-4xl font-black tracking-tight">
            {gig.title}
          </h1>
          <p className="mt-4 text-[#4B5563] leading-relaxed">{gig.description}</p>

          <dl className="mt-8 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <Item label="Public location" value={gig.location} />
            <Item label="When" value={gig.scheduled_date} />
            <Item
              label="Pay"
              value={`$${Number(gig.pay_rate).toFixed(2)} ${
                gig.pay_type === "hourly" ? "/hr" : "flat"
              }`}
            />
            <Item label="Slots" value={`${gig.slots_filled}/${gig.slots}`} />
            <Item label="Duration" value={gig.duration_hours ? `${gig.duration_hours} hrs` : "—"} />
            <Item label="Contact" value={gig.contact_phone || "—"} />
            <Item label="Status" value={gig.status.toUpperCase()} />
            <Item label="Blasts" value={String(gig.blast_count || 0)} />
          </dl>

          {gig.address_line && (
            <div className="mt-6 border border-[#0044FF]/30 bg-[#F0F4FF] p-4">
              <div className="font-mono-label flex items-center gap-2 text-[#0044FF]">
                <EyeSlash size={12} weight="duotone" /> Full address (workers only see after approval)
              </div>
              <div className="mt-2 font-display text-base font-bold text-[#030712]">
                {gig.address_line}
              </div>
            </div>
          )}
        </div>

        <aside className="bg-[#F9FAFB] p-6 md:p-10">
          <div className="font-mono-label">Actions</div>
          <h2 className="mt-2 font-display text-2xl font-black">Blast & manage</h2>

          <Button
            data-testid="open-blast-btn"
            onClick={() => setBlastOpen(true)}
            className="mt-6 h-12 w-full rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
          >
            <Megaphone size={18} className="mr-2" weight="fill" /> Blast to workers
          </Button>

          <Button
            data-testid="edit-gig-btn"
            onClick={() => setEditOpen(true)}
            variant="outline"
            className="mt-3 h-12 w-full rounded-none border-[#030712]"
          >
            <PencilSimple size={18} className="mr-2" /> Edit gig
          </Button>

          <Button
            data-testid="duplicate-gig-btn"
            onClick={duplicate}
            disabled={duplicating}
            variant="outline"
            className="mt-3 h-12 w-full rounded-none border-[#030712]"
          >
            <Copy size={18} className="mr-2" /> {duplicating ? "Duplicating…" : "Duplicate"}
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                data-testid="delete-gig-btn"
                variant="outline"
                className="mt-3 h-12 w-full rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
              >
                <Trash size={18} className="mr-2" /> Delete gig
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="rounded-none">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this gig?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes the gig and clears all worker acceptances.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="rounded-none">Cancel</AlertDialogCancel>
                <AlertDialogAction
                  data-testid="confirm-delete-gig"
                  className="rounded-none bg-[#EF4444]"
                  onClick={remove}
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {gig.last_blast_at && (
            <div className="mt-6 text-xs text-[#4B5563]">
              Last blast: {new Date(gig.last_blast_at).toLocaleString()}
            </div>
          )}
        </aside>
      </div>

      <div className="px-6 py-8 md:px-10">
        {/* Pending requests — admin reviews before accepting */}
        {(gig.pending_requests || []).length > 0 && (
          <div className="mb-8">
            <div className="font-mono-label">Pending requests</div>
            <div className="mt-1">
              <div className="font-display text-2xl font-black">
                {gig.pending_requests.length} worker
                {gig.pending_requests.length === 1 ? " wants" : "s want"} to claim this gig
              </div>
            </div>
            <div className="mt-4 overflow-x-auto border border-[#F59E0B]/30">
              <table className="w-full text-sm">
                <thead className="bg-[#FFFBEB]">
                  <tr className="text-left">
                    <th className="border-b border-[#F59E0B]/30 px-4 py-3 font-mono-label">Worker</th>
                    <th className="border-b border-[#F59E0B]/30 px-4 py-3 font-mono-label">Contact</th>
                    <th className="border-b border-[#F59E0B]/30 px-4 py-3 font-mono-label">ID</th>
                    <th className="border-b border-[#F59E0B]/30 px-4 py-3 font-mono-label">Requested at</th>
                    <th className="border-b border-[#F59E0B]/30 px-4 py-3 text-right"></th>
                  </tr>
                </thead>
                <tbody>
                  {gig.pending_requests.map((r) => (
                    <tr key={r.acceptance_id} data-testid={`request-row-${r.acceptance_id}`} className="hover:bg-[#FFFBEB]/50">
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 font-semibold">{r.worker_name || r.worker_id}</td>
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 text-xs">
                        <div>{r.worker_email}</div>
                        {r.worker_phone && <div className="text-[#4B5563]">{r.worker_phone}</div>}
                      </td>
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 text-xs">
                        {r.worker_id_verified ? (
                          <span className="inline-flex items-center gap-1 text-[#065F46]">
                            <CheckCircle size={12} weight="fill" /> Verified
                          </span>
                        ) : (
                          <span className="text-[#92400E]">Not verified</span>
                        )}
                      </td>
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 text-xs text-[#4B5563]">
                        {r.requested_at ? new Date(r.requested_at).toLocaleString() : "—"}
                      </td>
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            data-testid={`approve-request-${r.acceptance_id}`}
                            onClick={async () => {
                              try {
                                await api.post(`/gigs/${gigId}/requests/${r.acceptance_id}/approve`);
                                toast.success(`${r.worker_name || "Worker"} approved`);
                                load();
                              } catch (e) {
                                toast.error(getErr(e));
                              }
                            }}
                            className="h-9 rounded-none bg-[#10B981] px-3 text-white hover:bg-[#0e9971]"
                          >
                            Approve
                          </Button>
                          <Button
                            data-testid={`reject-request-${r.acceptance_id}`}
                            onClick={async () => {
                              try {
                                await api.post(`/gigs/${gigId}/requests/${r.acceptance_id}/reject`);
                                toast.success("Request rejected");
                                load();
                              } catch (e) {
                                toast.error(getErr(e));
                              }
                            }}
                            variant="outline"
                            className="h-9 rounded-none border-[#EF4444] px-3 text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                          >
                            Reject
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="font-mono-label">Roster</div>
            <h2 className="mt-1 font-display text-2xl font-black">
              Approved workers ({(gig.acceptances || []).length})
            </h2>
          </div>
          <Button
            data-testid="add-worker-btn"
            onClick={() => setAssignOpen(true)}
            className="h-10 rounded-none bg-[#030712] text-white hover:bg-[#1f2937]"
          >
            <UserPlus size={16} className="mr-2" /> Add a worker
          </Button>
        </div>

        {(!gig.acceptances || gig.acceptances.length === 0) ? (
          <div className="mt-4 border border-dashed border-[#E5E7EB] p-8 text-sm text-[#4B5563]">
            No one has accepted yet. Send a blast to alert your crew.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left">
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Name</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Status</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">In</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Out</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Hrs</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Rate</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Earned</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label">Timesheet</th>
                  <th className="border-b border-[#E5E7EB] px-3 py-3 font-mono-label"></th>
                </tr>
              </thead>
              <tbody>
                {gig.acceptances.map((a) => {
                  const onClock = a.clock_in_at && !a.clock_out_at;
                  const completed = !!a.clock_out_at;
                  const statusClass = onClock
                    ? "bg-[#F59E0B] text-white"
                    : completed
                    ? "bg-[#10B981] text-white"
                    : "bg-[#0044FF] text-white";
                  const statusLabel = onClock
                    ? "ON CLOCK"
                    : completed
                    ? "COMPLETED"
                    : "ACCEPTED";
                  const rate = a.pay_rate_applied != null ? a.pay_rate_applied : a.pay_rate_effective;
                  const ptype = a.pay_type_applied || a.pay_type_effective;
                  const rateSrc = a.pay_rate_source;
                  const hasOverride = a.pay_rate_override != null || a.pay_type_override != null;
                  return (
                  <tr key={a.acceptance_id} className="hover:bg-[#F9FAFB]">
                    <td className="border-b border-[#E5E7EB] px-3 py-3 font-semibold">
                      {a.worker_name || a.worker_id}
                      <div className="text-[10px] font-normal text-[#4B5563]">{a.worker_email}</div>
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3">
                      <span className={`px-2 py-1 text-[10px] font-bold tracking-widest ${statusClass}`}>
                        {statusLabel}
                      </span>
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3 text-xs text-[#4B5563]">
                      {a.clock_in_at ? new Date(a.clock_in_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3 text-xs text-[#4B5563]">
                      {a.clock_out_at ? new Date(a.clock_out_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3 text-xs font-bold">
                      {a.hours_worked != null ? `${a.hours_worked.toFixed(2)}h` : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3 text-xs">
                      {rate != null ? (
                        <div>
                          <div className="font-semibold">
                            ${Number(rate).toFixed(2)}
                            {ptype === "hourly" ? "/hr" : " flat"}
                          </div>
                          <div className="text-[9px] uppercase tracking-widest text-[#4B5563]">
                            {hasOverride
                              ? "OVERRIDE"
                              : rateSrc === "worker_default"
                              ? "WORKER DEFAULT"
                              : "GIG POSTED"}
                          </div>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3 text-xs font-bold text-[#10B981]">
                      {a.earnings != null
                        ? `$${a.earnings.toFixed(2)}`
                        : a.projected_earnings != null
                        ? <span className="text-[#92400E]">${a.projected_earnings.toFixed(2)} <span className="font-mono-label text-[#92400E]">PROJ</span></span>
                        : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3">
                      {!completed ? (
                        <span className="text-xs text-[#4B5563]">—</span>
                      ) : a.timesheet_approved ? (
                        <span className="inline-flex items-center gap-1 bg-[#10B981] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                          <CheckCircle size={9} weight="fill" /> APPROVED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 bg-[#F59E0B] px-2 py-0.5 text-[9px] font-bold tracking-widest text-white">
                          PENDING
                        </span>
                      )}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-3 py-3">
                      <div className="flex flex-wrap justify-end gap-1.5">
                        <Button
                          data-testid={`pay-override-${a.acceptance_id}`}
                          onClick={() => setPayDialog({ acceptance: a })}
                          variant="outline"
                          className="h-7 rounded-none border-[#030712] px-2 text-[10px]"
                          title="Override pay for this gig"
                        >
                          <CurrencyDollar size={10} className="mr-1" weight="duotone" /> Pay
                        </Button>
                        {completed && !a.timesheet_approved && (
                          <Button
                            data-testid={`approve-timesheet-${a.acceptance_id}`}
                            onClick={() => setApproveDialog({ acceptance: a })}
                            className="h-7 rounded-none bg-[#10B981] px-2 text-[10px] text-white hover:bg-[#0e9971]"
                          >
                            <ClipboardText size={10} className="mr-1" /> Approve
                          </Button>
                        )}
                        {completed && a.timesheet_approved && (
                          <Button
                            data-testid={`unapprove-timesheet-${a.acceptance_id}`}
                            onClick={async () => {
                              if (!confirm("Reverse this timesheet approval?")) return;
                              try {
                                await api.post(`/gigs/${gigId}/acceptances/${a.acceptance_id}/unapprove-timesheet`);
                                toast.success("Timesheet un-approved");
                                load();
                              } catch (e) {
                                toast.error(getErr(e));
                              }
                            }}
                            variant="outline"
                            className="h-7 rounded-none border-[#F59E0B] px-2 text-[10px] text-[#92400E]"
                          >
                            Un-approve
                          </Button>
                        )}
                        <Button
                          data-testid={`remove-worker-${a.acceptance_id}`}
                          onClick={() => removeWorker(a)}
                          variant="outline"
                          className="h-7 rounded-none border-[#EF4444] px-2 text-[10px] text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                        >
                          <UserMinus size={10} className="mr-1" /> Remove
                        </Button>
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={blastOpen} onOpenChange={setBlastOpen}>        <DialogContent className="max-w-lg rounded-none border-[#030712]" data-testid="blast-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-black">
              Blast this gig
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="font-mono-label">Channels</div>
            <ChannelToggle
              testId="channel-in_app"
              icon={Bell}
              title="In-app notification"
              desc="Workers see it in their feed instantly."
              checked={channels.in_app}
              onChange={(v) => setChannels((c) => ({ ...c, in_app: v }))}
            />
            <ChannelToggle
              testId="channel-email"
              icon={EnvelopeSimple}
              title="Email"
              desc="Sends via Resend (requires RESEND_API_KEY)."
              checked={channels.email}
              onChange={(v) => setChannels((c) => ({ ...c, email: v }))}
            />
            <ChannelToggle
              testId="channel-sms"
              icon={DeviceMobile}
              title="SMS"
              desc="Sends via Twilio (requires Twilio credentials)."
              checked={channels.sms}
              onChange={(v) => setChannels((c) => ({ ...c, sms: v }))}
            />
            <Button
              data-testid="confirm-blast"
              onClick={sendBlast}
              disabled={blasting}
              className="mt-4 h-12 w-full rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              {blasting ? (
                "Sending blast…"
              ) : (
                <>
                  <CheckCircle weight="fill" className="mr-2" size={18} /> Send blast
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <EditGigDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        gig={gig}
        onSaved={load}
      />

      <AssignWorkerDialog
        open={assignOpen}
        onOpenChange={setAssignOpen}
        gig={gig}
        onAssigned={load}
      />

      <PayOverrideDialog
        open={!!payDialog}
        onOpenChange={(o) => !o && setPayDialog(null)}
        gigId={gigId}
        acceptance={payDialog?.acceptance}
        onSaved={() => {
          setPayDialog(null);
          load();
        }}
      />

      <ApproveTimesheetDialog
        open={!!approveDialog}
        onOpenChange={(o) => !o && setApproveDialog(null)}
        gigId={gigId}
        acceptance={approveDialog?.acceptance}
        onSaved={() => {
          setApproveDialog(null);
          load();
        }}
      />
    </div>
  );
}

const Item = ({ label, value }) => (
  <div className="border-l-2 border-[#0044FF] pl-3">
    <div className="font-mono-label">{label}</div>
    <div className="mt-1 font-semibold">{value}</div>
  </div>
);

const ChannelToggle = ({ icon: Icon, title, desc, checked, onChange, testId }) => (
  <label
    data-testid={testId}
    className={`flex cursor-pointer items-start gap-3 border p-4 ${
      checked ? "border-[#0044FF] bg-[#F0F4FF]" : "border-[#E5E7EB]"
    }`}
  >
    <Checkbox checked={checked} onCheckedChange={onChange} className="mt-1" />
    <div className="flex-1">
      <div className="flex items-center gap-2 font-semibold">
        <Icon size={16} weight="duotone" /> {title}
      </div>
      <div className="mt-1 text-xs text-[#4B5563]">{desc}</div>
    </div>
  </label>
);
