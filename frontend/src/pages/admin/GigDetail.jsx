import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import WorkerLink from "@/components/admin/WorkerLink";
import MessageUserButton from "@/components/messages/MessageUserButton";
import { formatGigLong, formatGigRelative } from "@/lib/gigDate";
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
  BellRinging,
  CheckCircle,
  EyeSlash,
  UserPlus,
  UserMinus,
  CurrencyDollar,
  ClipboardText,
  Clock,
  Star,
  Share,
  FolderSimple,
  LinkBreak,
  Link as LinkIcon,
} from "@phosphor-icons/react";
import EditGigDialog from "@/components/admin/EditGigDialog";
import AssignWorkerDialog from "@/components/admin/AssignWorkerDialog";
import PickProjectForGigDialog from "@/components/admin/PickProjectForGigDialog";
import PayOverrideDialog from "@/components/admin/PayOverrideDialog";
import ApproveTimesheetDialog from "@/components/admin/ApproveTimesheetDialog";
import EditTimesheetDialog from "@/components/admin/EditTimesheetDialog";
import RatingDialog, { StarsDisplay } from "@/components/admin/RatingDialog";
import { TAG_CONFIG, TAG_PRIORITY, getOrderedTags } from "@/lib/gigTags";
import { getPaymentTimeline } from "@/lib/paymentTimeline";
import MarkdownView from "@/components/MarkdownView";

export default function GigDetail() {
  const { gigId } = useParams();
  const nav = useNavigate();
  const [gig, setGig] = useState(null);
  const [blastOpen, setBlastOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [linkProjectOpen, setLinkProjectOpen] = useState(false);
  const [payDialog, setPayDialog] = useState(null); // { acceptance }
  const [approveDialog, setApproveDialog] = useState(null); // { acceptance }
  const [editTimesheetDialog, setEditTimesheetDialog] = useState(null);
  const [ratingDialog, setRatingDialog] = useState(null); // { acceptance }
  const [duplicating, setDuplicating] = useState(false);
  const [rosterSearch, setRosterSearch] = useState("");
  const [channels, setChannels] = useState({ in_app: true, push: true, email: false, sms: false });
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
      nav("/ops/gigs");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const duplicate = async () => {
    setDuplicating(true);
    try {
      const { data } = await api.post(`/gigs/${gigId}/duplicate`);
      toast.success("Gig duplicated");
      nav(`/ops/gigs/${data.gig_id}`);
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

  const unlinkFromProject = async () => {
    if (!confirm("Unlink this gig from the project? The gig itself stays put.")) return;
    try {
      await api.delete(`/gigs/${gigId}/project`);
      toast.success("Gig unlinked from project");
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
      // When email/SMS/push are checked, the heavy fan-out runs in the
      // background (Resend has a 25 req/s rate limit — sending serially in
      // the request handler would blow past Cloudflare's 100s timeout).
      // The counts shown are the *targeted* totals; the Blasts report shows
      // the actual delivered numbers once the background job finishes.
      if (data.queued) {
        toast.success(
          `Blast queued — in-app ${c.in_app || 0} sent now; ${c.email || 0} emails, ${c.push || 0} push + ${c.sms || 0} SMS delivering in the background.`,
          { duration: 6000 }
        );
      } else {
        toast.success(
          `Blast sent — in-app ${c.in_app || 0}, push ${c.push || 0}, email ${c.email || 0}, SMS ${c.sms || 0}`
        );
      }
      setBlastOpen(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBlasting(false);
    }
  };

  const toggleRush = async () => {
    const next = !gig.is_rush;
    try {
      await api.put(`/gigs/${gigId}/rush`, { is_rush: next });
      toast.success(next ? "RUSH on — gig pinned to top of feed" : "RUSH off — back to normal");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const toggleTag = async (tag) => {
    const current = Array.isArray(gig.tags) ? gig.tags : [];
    const next = current.includes(tag)
      ? current.filter((t) => t !== tag)
      : [...current, tag];
    try {
      const { data } = await api.put(`/gigs/${gigId}/tags`, { tags: next });
      const cfg = TAG_CONFIG[tag];
      toast.success(
        next.includes(tag)
          ? `${cfg.label} on — pinned to top of feed`
          : `${cfg.label} off${data.is_rush ? " — still pinned by other tags" : " — back to normal"}`
      );
      load();
    } catch (e) {
      toast.error(getErr(e));
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
          onClick={() => nav("/ops/gigs")}
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
          {(() => {
            const activeTags = getOrderedTags(gig.tags);
            const pt = getPaymentTimeline(gig.payment_timeline);
            const PI = pt.icon;
            return (
              <div
                data-testid="active-tags-banner"
                className="mt-3 flex flex-wrap items-center gap-2"
              >
                {activeTags.length > 0 && (
                  <span className="font-mono-label text-[10px] text-[#4B5563]">
                    Pinned to top of feed
                  </span>
                )}
                {activeTags.map((t) => {
                  const cfg = TAG_CONFIG[t];
                  const I = cfg.icon;
                  return (
                    <span
                      key={t}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] ${cfg.pillClass}`}
                    >
                      <I
                        size={11}
                        weight="fill"
                        className={cfg.pulse ? "animate-pulse" : ""}
                      />
                      {cfg.label}
                    </span>
                  );
                })}
                <span
                  data-testid="payment-timeline-pill"
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black tracking-[0.18em] ${pt.pillClass}`}
                  title={
                    gig.payment_timeline === "custom" && gig.payment_timeline_note
                      ? gig.payment_timeline_note
                      : pt.description
                  }
                >
                  <PI
                    size={11}
                    weight="fill"
                    className={pt.pulse ? "animate-pulse" : ""}
                  />
                  {pt.label}
                </span>
              </div>
            );
          })()}
          {gig.payment_timeline === "custom" && gig.payment_timeline_note && (
            <p
              data-testid="payment-timeline-note"
              className="mt-2 inline-block bg-[#FFFBEB] px-3 py-1.5 text-xs text-[#92400E]"
            >
              <strong>Payment note:</strong> {gig.payment_timeline_note}
            </p>
          )}

          {/* Project link banner — surfaces when this gig is part of a project,
              or offers a one-click "Link to project" when it isn't. */}
          {gig.project ? (
            <div
              data-testid="project-banner"
              className="mt-4 flex flex-wrap items-center gap-2 border border-[#030712] bg-[#F9FAFB] px-3 py-2.5"
            >
              <FolderSimple size={14} weight="duotone" />
              <span className="font-mono-label text-[10px] text-[#4B5563]">
                Part of project
              </span>
              <button
                data-testid="project-banner-open"
                onClick={() => nav(`/ops/projects/${gig.project.project_id}`)}
                className="font-display text-sm font-black tracking-tight text-[#030712] underline-offset-2 hover:underline"
              >
                {gig.project.title}
              </button>
              {gig.project.client_name && (
                <span className="text-xs text-[#4B5563]">
                  · {gig.project.client_name}
                </span>
              )}
              {(gig.project.sibling_gigs || []).length > 0 && (
                <span className="font-mono-label text-[10px] text-[#4B5563]">
                  · {(gig.project.sibling_gigs || []).length} sibling gig
                  {(gig.project.sibling_gigs || []).length === 1 ? "" : "s"}
                </span>
              )}
              <div className="ml-auto flex items-center gap-2">
                <Button
                  data-testid="project-banner-open-btn"
                  onClick={() => nav(`/ops/projects/${gig.project.project_id}`)}
                  variant="outline"
                  className="h-8 rounded-none border-[#030712] px-2 text-[10px]"
                >
                  Open project →
                </Button>
                <Button
                  data-testid="project-banner-unlink"
                  onClick={unlinkFromProject}
                  variant="outline"
                  className="h-8 rounded-none border-[#EF4444] px-2 text-[10px] text-[#EF4444] hover:bg-[#FEF2F2]"
                >
                  <LinkBreak size={11} className="mr-1" /> Unlink
                </Button>
              </div>
            </div>
          ) : (
            <button
              data-testid="project-link-btn"
              onClick={() => setLinkProjectOpen(true)}
              className="font-mono-label mt-4 inline-flex items-center gap-1 border border-dashed border-[#E5E7EB] bg-white px-2.5 py-1 text-[10px] text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
            >
              <LinkIcon size={11} weight="bold" /> Link to a project
            </button>
          )}

          <div className="mt-4 text-[#4B5563]">
            <MarkdownView text={gig.description} />
          </div>

          <dl className="mt-8 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <Item label="Public location" value={gig.location} />
            <Item label="When" value={formatGigLong(gig)} testId="gig-when-admin" hint={formatGigRelative(gig)} />
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

          <div
            data-testid="tag-toggles"
            className="mt-6 rounded-none border border-[#E5E7EB] bg-white p-4"
          >
            <div className="font-mono-label mb-3 text-[10px] text-[#4B5563]">
              Pin tags · any tag pins the gig to the top of the feed
            </div>
            <div className="grid grid-cols-2 gap-2">
              {TAG_PRIORITY.map((t) => {
                const cfg = TAG_CONFIG[t];
                const I = cfg.icon;
                const on = Array.isArray(gig.tags) && gig.tags.includes(t);
                return (
                  <button
                    key={t}
                    data-testid={`tag-toggle-${t}`}
                    onClick={() => toggleTag(t)}
                    className={`flex items-center justify-center gap-1.5 px-2 py-2 text-[10px] font-black tracking-[0.16em] transition-colors ${
                      on
                        ? cfg.pillClass
                        : "border border-[#E5E7EB] bg-white text-[#4B5563] hover:border-[#030712] hover:text-[#030712]"
                    }`}
                  >
                    <I
                      size={12}
                      weight="fill"
                      className={on && cfg.pulse ? "animate-pulse" : ""}
                    />
                    {cfg.label}
                  </button>
                );
              })}
            </div>
          </div>

          <Button
            data-testid="edit-gig-btn"
            onClick={() => setEditOpen(true)}
            variant="outline"
            className="mt-3 h-12 w-full rounded-none border-[#030712]"
          >
            <PencilSimple size={18} className="mr-2" /> Edit gig
          </Button>

          <Button
            data-testid="open-gig-chat-btn"
            onClick={async () => {
              try {
                const { data } = await api.get(
                  `/messages/threads/gig/${gigId}`
                );
                nav(`/ops/messages?thread=${data.thread_id}`);
              } catch (e) {
                toast.error(getErr(e));
              }
            }}
            variant="outline"
            className="mt-3 h-12 w-full rounded-none border-[#030712]"
          >
            <Megaphone size={18} className="mr-2" /> Open gig group chat
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

          <Button
            data-testid="share-gig-btn"
            onClick={async () => {
              // Use the server-rendered share endpoint so iMessage / Slack /
              // WhatsApp / Facebook unfurl with the gig's title, pay, location
              // and a branded preview image (their crawlers don't run JS).
              const url = `${window.location.origin}/api/share/gigs/${gigId}`;
              try {
                await navigator.clipboard.writeText(url);
                toast.success("Share link copied — paste anywhere");
              } catch {
                // Fallback: select-and-copy via prompt
                window.prompt("Copy this link:", url);
              }
            }}
            variant="outline"
            className="mt-3 h-12 w-full rounded-none border-[#10B981] text-[#065F46] hover:bg-[#10B981] hover:text-white"
          >
            <Share size={18} className="mr-2" weight="duotone" /> Share gig link
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
                      <td className="border-b border-[#F59E0B]/30 px-4 py-3 font-semibold">
                        <div className="flex items-center gap-2">
                          <WorkerLink workerId={r.worker_id} name={r.worker_name || r.worker_id} />
                          <MessageUserButton
                            userId={r.worker_id}
                            name={r.worker_name}
                            variant="icon"
                            testId={`request-message-${r.acceptance_id}`}
                          />
                        </div>
                      </td>
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
                        <div className="flex flex-wrap justify-end gap-2">
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
                          {(gig.backup_slots || 0) > 0 && (gig.backups_filled || 0) < (gig.backup_slots || 0) && (
                            <Button
                              data-testid={`approve-backup-${r.acceptance_id}`}
                              onClick={async () => {
                                try {
                                  await api.post(`/gigs/${gigId}/requests/${r.acceptance_id}/approve-backup`);
                                  toast.success(`${r.worker_name || "Worker"} added as backup`);
                                  load();
                                } catch (e) {
                                  toast.error(getErr(e));
                                }
                              }}
                              variant="outline"
                              className="h-9 rounded-none border-[#0044FF] px-3 text-[#0044FF] hover:bg-[#0044FF] hover:text-white"
                            >
                              Approve as backup
                            </Button>
                          )}
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

        {/* Backup pool */}
        {((gig.backup_slots || 0) > 0 || (gig.backups || []).length > 0) && (
          <div
            data-testid="backups-section"
            className="mb-6 border border-[#0044FF] bg-[#F0F4FF]"
          >
            <div className="border-b border-[#0044FF] bg-[#0044FF] px-4 py-3 text-white">
              <div className="font-mono-label text-white/80">Backup pool</div>
              <div className="font-display text-xl font-black">
                {(gig.backups || []).length}/{gig.backup_slots || 0} backups · 
                {" "}{(gig.slots_filled || 0) >= (gig.slots || 1) && (gig.backups || []).length > 0
                  ? " ready to promote on cancel"
                  : " awaiting primary cancellations"}
              </div>
            </div>
            {(gig.backups || []).length === 0 ? (
              <div className="px-4 py-4 text-sm text-[#4B5563]">
                Approve incoming requests as a backup using the &ldquo;Approve as backup&rdquo;
                button above to populate this pool.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="border-b border-[#0044FF]/30 px-4 py-3 font-mono-label">#</th>
                    <th className="border-b border-[#0044FF]/30 px-4 py-3 font-mono-label">Worker</th>
                    <th className="border-b border-[#0044FF]/30 px-4 py-3 font-mono-label">Contact</th>
                    <th className="border-b border-[#0044FF]/30 px-4 py-3 font-mono-label">Approved at</th>
                    <th className="border-b border-[#0044FF]/30 px-4 py-3 text-right"></th>
                  </tr>
                </thead>
                <tbody>
                  {gig.backups.map((b) => {
                    const canPromote = (gig.slots_filled || 0) < (gig.slots || 1);
                    return (
                      <tr
                        key={b.acceptance_id}
                        data-testid={`backup-row-${b.acceptance_id}`}
                        className="hover:bg-white"
                      >
                        <td className="border-b border-[#0044FF]/30 px-4 py-3 font-mono font-bold">
                          #{b.backup_order || "?"}
                        </td>
                        <td className="border-b border-[#0044FF]/30 px-4 py-3 font-semibold">
                          <div className="flex items-center gap-2">
                            <WorkerLink workerId={b.worker_id} name={b.worker_name || b.worker_id} />
                            <MessageUserButton
                              userId={b.worker_id}
                              name={b.worker_name}
                              variant="icon"
                              testId={`backup-message-${b.acceptance_id}`}
                            />
                          </div>
                        </td>
                        <td className="border-b border-[#0044FF]/30 px-4 py-3 text-xs">
                          <div>{b.worker_email}</div>
                          {b.worker_phone && (
                            <div className="text-[#4B5563]">{b.worker_phone}</div>
                          )}
                        </td>
                        <td className="border-b border-[#0044FF]/30 px-4 py-3 text-xs text-[#4B5563]">
                          {b.accepted_at ? new Date(b.accepted_at).toLocaleString() : "—"}
                        </td>
                        <td className="border-b border-[#0044FF]/30 px-4 py-3 text-right">
                          <div className="flex flex-wrap justify-end gap-2">
                            <Button
                              data-testid={`promote-backup-${b.acceptance_id}`}
                              disabled={!canPromote}
                              title={!canPromote ? "All primary slots are full" : "Promote to primary"}
                              onClick={async () => {
                                if (!window.confirm(`Promote ${b.worker_name || "this worker"} to primary?`)) return;
                                try {
                                  await api.post(`/gigs/${gigId}/acceptances/${b.acceptance_id}/promote`);
                                  toast.success("Promoted to primary");
                                  load();
                                } catch (e) {
                                  toast.error(getErr(e));
                                }
                              }}
                              className="h-9 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc] disabled:opacity-50"
                            >
                              Promote
                            </Button>
                            <Button
                              data-testid={`remove-backup-${b.acceptance_id}`}
                              variant="outline"
                              onClick={async () => {
                                if (!window.confirm(`Remove ${b.worker_name || "this backup"} from the backup pool?`)) return;
                                try {
                                  await api.delete(`/gigs/${gigId}/acceptances/${b.acceptance_id}`);
                                  toast.success("Backup removed");
                                  load();
                                } catch (e) {
                                  toast.error(getErr(e));
                                }
                              }}
                              className="h-9 rounded-none border-[#EF4444] px-3 text-[#EF4444] hover:bg-[#EF4444] hover:text-white"
                            >
                              Remove
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
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

        {(gig.acceptances || []).length > 0 && (
          <div className="mb-3">
            <div className="relative max-w-xs">
              <Input
                data-testid="roster-search"
                value={rosterSearch}
                onChange={(e) => setRosterSearch(e.target.value)}
                placeholder="Search worker (name, email, phone)…"
                className="h-9 rounded-none border-[#030712] pr-7"
              />
              {rosterSearch && (
                <button
                  type="button"
                  data-testid="roster-search-clear"
                  onClick={() => setRosterSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#4B5563] hover:text-[#030712]"
                  aria-label="Clear roster search"
                >
                  ×
                </button>
              )}
            </div>
          </div>
        )}

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
                {(gig.acceptances || [])
                  .filter((a) => {
                    if (!rosterSearch.trim()) return true;
                    const q = rosterSearch.trim().toLowerCase();
                    return (
                      (a.worker_name || "").toLowerCase().includes(q) ||
                      (a.worker_email || "").toLowerCase().includes(q) ||
                      (a.worker_phone || "").toLowerCase().includes(q)
                    );
                  })
                  .map((a) => {
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
                      <div className="flex items-center gap-2">
                        <WorkerLink workerId={a.worker_id} name={a.worker_name || a.worker_id} />
                        <MessageUserButton
                          userId={a.worker_id}
                          name={a.worker_name}
                          variant="icon"
                          testId={`acceptance-message-${a.acceptance_id}`}
                        />
                      </div>
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
                        <select
                          data-testid={`gig-role-${a.acceptance_id}`}
                          value={a.gig_role || "worker"}
                          onChange={async (e) => {
                            const newRole = e.target.value;
                            try {
                              await api.put(
                                `/gigs/${gigId}/acceptances/${a.acceptance_id}/role`,
                                { role: newRole }
                              );
                              const label = newRole.charAt(0).toUpperCase() + newRole.slice(1);
                              toast.success(
                                `${a.worker_name || "Worker"} → ${label}`
                              );
                              load();
                            } catch (err) {
                              toast.error(getErr(err));
                            }
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="h-7 rounded-none border border-[#030712] bg-white px-1.5 text-[10px] font-bold uppercase tracking-widest"
                          title="Set this worker's role on this gig"
                        >
                          <option value="worker">Worker</option>
                          <option value="manager">Manager</option>
                          <option value="lead">Lead</option>
                          <option value="trainer">Trainer</option>
                        </select>
                        <Button
                          data-testid={`edit-timesheet-${a.acceptance_id}`}
                          onClick={() => setEditTimesheetDialog({ acceptance: a })}
                          variant="outline"
                          className="h-7 rounded-none border-[#030712] px-2 text-[10px]"
                          title="Edit clock-in / clock-out times"
                        >
                          <Clock size={10} className="mr-1" weight="duotone" /> Edit times
                        </Button>
                        <Button
                          data-testid={`pay-override-${a.acceptance_id}`}
                          onClick={() => setPayDialog({ acceptance: a })}
                          variant="outline"
                          className="h-7 rounded-none border-[#030712] px-2 text-[10px]"
                          title="Override pay for this gig"
                        >
                          <CurrencyDollar size={10} className="mr-1" weight="duotone" /> Pay
                        </Button>
                        <Button
                          data-testid={`rating-${a.acceptance_id}`}
                          onClick={() => setRatingDialog({ acceptance: a })}
                          variant="outline"
                          className={`h-7 rounded-none px-2 text-[10px] ${
                            a.admin_rating || a.client_rating
                              ? "border-[#F59E0B] text-[#92400E]"
                              : "border-[#030712]"
                          }`}
                          title="Rate worker / share client link"
                        >
                          <Star
                            size={10}
                            weight={a.admin_rating ? "fill" : "duotone"}
                            className="mr-1"
                          />
                          {a.admin_rating ? `${a.admin_rating}★` : "Rate"}
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
              testId="channel-push"
              icon={BellRinging}
              title="Push notification"
              desc="Native lockscreen ping for workers who enabled push. Free."
              checked={channels.push}
              onChange={(v) => setChannels((c) => ({ ...c, push: v }))}
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

      <PickProjectForGigDialog
        open={linkProjectOpen}
        onOpenChange={setLinkProjectOpen}
        gigId={gigId}
        onLinked={load}
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

      <EditTimesheetDialog
        open={!!editTimesheetDialog}
        onOpenChange={(o) => !o && setEditTimesheetDialog(null)}
        gigId={gigId}
        acceptance={editTimesheetDialog?.acceptance}
        onSaved={() => {
          setEditTimesheetDialog(null);
          load();
        }}
      />

      <RatingDialog
        open={!!ratingDialog}
        onOpenChange={(o) => !o && setRatingDialog(null)}
        gigId={gigId}
        acceptance={ratingDialog?.acceptance}
        onSaved={() => {
          load();
        }}
      />
    </div>
  );
}

const Item = ({ label, value, testId, hint }) => (
  <div className="border-l-2 border-[#0044FF] pl-3" data-testid={testId}>
    <div className="font-mono-label">{label}</div>
    <div className="mt-1 font-semibold">{value}</div>
    {hint && <div className="mt-0.5 text-[10px] font-mono-label text-[#4B5563]">{hint}</div>}
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
