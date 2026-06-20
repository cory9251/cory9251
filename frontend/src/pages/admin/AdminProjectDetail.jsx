import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import WorkerLink from "@/components/admin/WorkerLink";
import {
  ArrowLeft,
  Plus,
  Archive,
  Trash,
  PencilSimple,
  Users,
  Briefcase,
  CalendarBlank,
  Note as NoteIcon,
  PaperPlaneRight,
  Megaphone,
  Broom,
  Wrench,
  Car,
  Link as LinkIcon,
  User as UserIcon,
  ChatCircleDots,
} from "@phosphor-icons/react";
import MarkdownView from "@/components/MarkdownView";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import LinkGigToProjectDialog from "@/components/admin/LinkGigToProjectDialog";
import EditProjectDialog from "@/components/admin/EditProjectDialog";
import ProjectCustomerChatDialog from "@/components/admin/ProjectCustomerChatDialog";

const CAT = {
  cleaning: { bg: "bg-[#0044FF]", text: "text-white", icon: Broom },
  labor: { bg: "bg-[#030712]", text: "text-white", icon: Wrench },
  driver: { bg: "bg-[#F59E0B]", text: "text-[#030712]", icon: Car },
};

export default function AdminProjectDetail() {
  const { projectId } = useParams();
  const nav = useNavigate();
  const [project, setProject] = useState(null);
  const [createGigOpen, setCreateGigOpen] = useState(false);
  const [linkGigOpen, setLinkGigOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [blasting, setBlasting] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}`);
      setProject(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const archive = async () => {
    if (!window.confirm("Archive this project? All linked gigs will be unlinked but kept.")) return;
    try {
      await api.delete(`/projects/${projectId}`);
      toast.success("Project archived");
      nav("/ops/projects?archived=true");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const blastProject = async () => {
    if (
      !window.confirm(
        "Blast this project to ALL workers via SMS, email, push, and in-app?"
      )
    ) return;
    setBlasting(true);
    try {
      const { data } = await api.post(`/projects/${projectId}/blast`, {
        channels: ["in_app", "push", "email", "sms"],
      });
      const c = data?.counts || {};
      if (data.queued) {
        toast.success(
          `Project blast queued — ${data.workers_targeted || 0} workers. ` +
            `In-app: ${c.in_app || 0} sent now. Push/Email/SMS (${
              (c.push || 0) + (c.email || 0) + (c.sms || 0)
            } total) delivering in the background.`,
          { duration: 6000 }
        );
      } else {
        toast.success(
          `Project blasted to ${data.workers_targeted || 0} workers · ` +
            `Push: ${c.push || 0} · SMS: ${c.sms || 0} · Email: ${c.email || 0} · In-app: ${c.in_app || 0}`,
          { duration: 5000 }
        );
      }
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setBlasting(false);
    }
  };

  const addNote = async () => {
    if (!noteText.trim()) return;
    setAddingNote(true);
    try {
      await api.post(`/projects/${projectId}/notes`, { text: noteText.trim() });
      setNoteText("");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setAddingNote(false);
    }
  };

  const deleteNote = async (noteId) => {
    if (!window.confirm("Delete this note?")) return;
    try {
      await api.delete(`/projects/${projectId}/notes/${noteId}`);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (!project) {
    return (
      <div className="p-10 font-mono-label text-sm">Loading…</div>
    );
  }

  const totals = (project.gigs || []).reduce(
    (acc, g) => ({
      slots: acc.slots + Number(g.slots || 0),
      filled: acc.filled + Number(g.slots_filled || 0),
    }),
    { slots: 0, filled: 0 }
  );

  return (
    <div data-testid="admin-project-detail">
      {/* Header */}
      <div className="border-b border-[#E5E7EB] px-4 py-5 md:px-10 md:py-8">
        <button
          onClick={() => nav("/ops/projects")}
          className="font-mono-label inline-flex items-center gap-1 text-[10px] text-[#4B5563] hover:text-[#030712]"
        >
          <ArrowLeft size={11} weight="bold" /> All projects
        </button>
        <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="font-mono-label flex items-center gap-1 text-[10px]">
              {project.client_name && (
                <>
                  <UserIcon size={11} weight="duotone" />
                  {project.client_name} ·
                </>
              )}
              Project
            </div>
            <h1 className="mt-1 font-display text-3xl font-black tracking-tight md:text-4xl">
              {project.title}
            </h1>
            {project.archived && (
              <div className="font-mono-label mt-2 inline-block bg-[#F3F4F6] px-2 py-1 text-[10px]">
                Archived
              </div>
            )}
            {project.last_blast_at && (
              <div
                data-testid="proj-last-blast"
                className="font-mono-label mt-2 inline-flex items-center gap-1.5 bg-[#FEF2F2] px-2 py-1 text-[10px] text-[#991B1B]"
                title={`Last blasted ${new Date(project.last_blast_at).toLocaleString()}`}
              >
                <Megaphone size={10} weight="fill" />
                Blasted {timeAgo(project.last_blast_at)} ·{" "}
                {project.blast_count || 1}× total
              </div>
            )}
            {project.description && (
              <div className="mt-4 max-w-2xl text-sm text-[#4B5563]">
                <MarkdownView text={project.description} />
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              data-testid="proj-blast-btn"
              onClick={blastProject}
              disabled={blasting}
              className="h-10 rounded-none bg-[#EF4444] text-white hover:bg-[#dc2626] disabled:opacity-60"
              title="Send SMS + email + in-app notifications about this project to all workers"
            >
              <Megaphone size={14} className="mr-1" weight="fill" />
              {blasting ? "Blasting…" : "Blast project"}
            </Button>
            <Button
              data-testid="proj-add-gig-btn"
              onClick={() => setCreateGigOpen(true)}
              className="h-10 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
            >
              <Plus size={14} className="mr-1" /> Add gig
            </Button>
            <Button
              data-testid="proj-link-gig-btn"
              onClick={() => setLinkGigOpen(true)}
              variant="outline"
              className="h-10 rounded-none border-[#030712]"
            >
              <LinkIcon size={14} className="mr-1" /> Link existing
            </Button>
            <ProjectCustomerChatDialog
              projectId={projectId}
              crew={project.crew || []}
              trigger={
                <Button
                  data-testid="proj-customer-chat-btn"
                  variant="outline"
                  className="h-10 rounded-none border-[#0044FF] text-[#0044FF] hover:bg-[#0044FF] hover:text-white"
                >
                  <ChatCircleDots size={14} className="mr-1" /> Customer chat
                </Button>
              }
            />
            <Button
              data-testid="proj-edit-btn"
              onClick={() => setEditOpen(true)}
              variant="outline"
              className="h-10 rounded-none border-[#030712]"
            >
              <PencilSimple size={14} className="mr-1" /> Edit
            </Button>
            {!project.archived && (
              <Button
                data-testid="proj-archive-btn"
                onClick={archive}
                variant="outline"
                className="h-10 rounded-none border-[#EF4444] text-[#EF4444] hover:bg-[#FEF2F2]"
              >
                <Archive size={14} className="mr-1" /> Archive
              </Button>
            )}
          </div>
        </div>

        {/* Stat strip */}
        <div className="mt-6 grid grid-cols-3 gap-3 border border-[#E5E7EB] bg-[#F9FAFB] p-3 md:max-w-md">
          <Stat icon={Briefcase} value={project.gigs?.length || 0} label="Assignments" />
          <Stat
            icon={Users}
            value={`${totals.filled}/${totals.slots}`}
            label="Slots filled"
          />
          <Stat
            icon={CalendarBlank}
            value={fmtRange(project.gigs)}
            label="When"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-0 lg:grid-cols-3">
        {/* Linked gigs + roster */}
        <div className="border-b border-[#E5E7EB] lg:col-span-2 lg:border-b-0 lg:border-r">
          <Section title="Linked gigs">
            {(project.gigs || []).length === 0 ? (
              <EmptyBlock
                onAddClick={() => setCreateGigOpen(true)}
                onLinkClick={() => setLinkGigOpen(true)}
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {project.gigs.map((g) => {
                  const c = CAT[g.category] || CAT.labor;
                  const Icon = c.icon;
                  return (
                    <button
                      key={g.gig_id}
                      data-testid={`proj-gig-${g.gig_id}`}
                      onClick={() => nav(`/ops/assignments/${g.gig_id}`)}
                      className="group overflow-hidden border border-[#E5E7EB] bg-white text-left transition-all hover:-translate-y-0.5 hover:border-[#030712]"
                    >
                      <div className={`flex items-center gap-2 px-3 py-2 ${c.bg} ${c.text}`}>
                        <Icon size={14} weight="duotone" />
                        <span className="font-mono-label text-[10px]">
                          {g.category} · {g.subcategory || "general"}
                        </span>
                        <span className="font-mono-label ml-auto text-[10px]">
                          {g.slots_filled}/{g.slots}
                        </span>
                      </div>
                      <div className="space-y-1 p-3 text-[11px]">
                        <div className="line-clamp-2 font-display text-sm font-bold leading-tight">
                          {g.title}
                        </div>
                        <div className="text-[10px] text-[#4B5563]">
                          {g.scheduled_date || "Flexible"} · {g.location}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </Section>

          <Section title="Crew across all gigs">
            {(project.crew || []).length === 0 ? (
              <div className="rounded border border-dashed border-[#E5E7EB] bg-[#F9FAFB] p-6 text-center text-xs text-[#4B5563]">
                No workers on any of the linked gigs yet.
              </div>
            ) : (
              <ul className="divide-y divide-[#E5E7EB] border border-[#E5E7EB]">
                {project.crew.map((m) => {
                  const c = CAT[m.gig_category] || CAT.labor;
                  return (
                    <li
                      key={m.acceptance_id}
                      data-testid={`proj-crew-${m.acceptance_id}`}
                      onClick={() => nav(`/ops/assignments/${m.gig_id}`)}
                      className="flex cursor-pointer items-center gap-3 bg-white px-4 py-2.5 hover:bg-[#F9FAFB]"
                    >
                      <span className={`grid h-8 w-8 shrink-0 place-items-center ${c.bg} ${c.text}`}>
                        {(() => {
                          const I = c.icon;
                          return <I size={14} weight="duotone" />;
                        })()}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-display text-sm font-bold">
                            <WorkerLink workerId={m.worker_id} name={m.worker_name || "(no name)"} />
                          </span>
                          <span className="font-mono-label rounded bg-[#F3F4F6] px-1.5 py-0.5 text-[9px]">
                            {m.gig_role}
                          </span>
                        </div>
                        <div className="text-[10px] text-[#4B5563]">
                          {m.gig_title}
                        </div>
                      </div>
                      <span className="font-mono-label text-[9px] text-[#4B5563]">
                        {m.status}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>
        </div>

        {/* Notes thread (admin-only) */}
        <div className="bg-[#F9FAFB] p-4 md:p-6 lg:p-8">
          <div className="font-mono-label flex items-center gap-1">
            <NoteIcon size={12} weight="duotone" />
            Admin notes
          </div>
          <p className="mt-1 text-[10px] text-[#4B5563]">
            Visible to admins only. Workers never see this thread.
          </p>
          <div className="mt-3 flex items-end gap-2">
            <Textarea
              data-testid="proj-note-input"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={2}
              placeholder="Add a note for the team…"
              className="rounded-none border-[#030712]"
            />
            <Button
              data-testid="proj-note-submit"
              onClick={addNote}
              disabled={!noteText.trim() || addingNote}
              className="h-9 shrink-0 rounded-none bg-[#0044FF] px-3 text-white hover:bg-[#0036cc]"
              aria-label="Post note"
            >
              <PaperPlaneRight size={14} weight="fill" />
            </Button>
          </div>
          <ul className="mt-4 space-y-3">
            {(project.notes || []).length === 0 ? (
              <li className="rounded border border-dashed border-[#E5E7EB] bg-white p-4 text-center text-[11px] text-[#4B5563]">
                No notes yet.
              </li>
            ) : (
              [...project.notes].reverse().map((n) => (
                <li
                  key={n.note_id}
                  data-testid={`proj-note-${n.note_id}`}
                  className="border border-[#E5E7EB] bg-white p-3 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-display text-[11px] font-bold text-[#030712]">
                      {n.author_name}
                    </span>
                    <button
                      onClick={() => deleteNote(n.note_id)}
                      data-testid={`proj-note-delete-${n.note_id}`}
                      title="Delete note"
                      aria-label="Delete note"
                      className="text-[#9CA3AF] hover:text-[#EF4444]"
                    >
                      <Trash size={12} />
                    </button>
                  </div>
                  <div className="mt-1 text-[11px] text-[#4B5563]">
                    {fmtDateTime(n.created_at)}
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-[#1F2937]">{n.text}</p>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <CreateGigDialog
        open={createGigOpen}
        onOpenChange={setCreateGigOpen}
        onCreated={load}
        projectId={projectId}
        projectDefaults={project.defaults}
      />
      <LinkGigToProjectDialog
        open={linkGigOpen}
        onOpenChange={setLinkGigOpen}
        projectId={projectId}
        projectDefaults={project.defaults}
        onLinked={load}
      />
      <EditProjectDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        project={project}
        onSaved={load}
      />
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="px-4 py-5 md:px-10 md:py-6">
      <div className="font-mono-label mb-3 text-[10px]">{title}</div>
      {children}
    </section>
  );
}

function Stat({ icon: Icon, value, label }) {
  return (
    <div className="leading-tight">
      <div className="font-mono-label flex items-center gap-1 text-[9px] text-[#4B5563]">
        {Icon && <Icon size={10} weight="bold" />} {label}
      </div>
      <div className="mt-1 font-display text-base font-black">{value}</div>
    </div>
  );
}

function EmptyBlock({ onAddClick, onLinkClick }) {
  return (
    <div className="border border-dashed border-[#E5E7EB] bg-[#F9FAFB] p-8 text-center">
      <div className="font-display text-base font-bold">No gigs linked yet.</div>
      <p className="mt-1 text-xs text-[#4B5563]">
        Add a new assignment under this project, or link an existing one.
      </p>
      <div className="mt-4 flex justify-center gap-2">
        <Button
          onClick={onAddClick}
          className="h-9 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
        >
          <Plus size={14} className="mr-1" /> Add new assignment
        </Button>
        <Button
          onClick={onLinkClick}
          variant="outline"
          className="h-9 rounded-none border-[#030712]"
        >
          <LinkIcon size={14} className="mr-1" /> Link existing
        </Button>
      </div>
    </div>
  );
}

function fmtRange(gigs = []) {
  const dates = gigs.map((g) => g.scheduled_at).filter(Boolean).sort();
  if (dates.length === 0) return "—";
  const first = new Date(dates[0]).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  if (dates.length === 1) return first;
  const last = new Date(dates[dates.length - 1]).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  return first === last ? first : `${first} – ${last}`;
}

function fmtDateTime(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}


function timeAgo(iso) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return "";
  }
}
