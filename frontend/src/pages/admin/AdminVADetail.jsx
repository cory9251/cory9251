import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft,
  Target,
  CurrencyDollar,
  Briefcase,
  CheckCircle,
  ChatCircleDots,
  Plus,
  Trash,
  Pencil,
  X,
  FloppyDisk,
  EyeSlash,
  Eye,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import MessageUserButton from "@/components/messages/MessageUserButton";

function fmtMoney(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

function currentMonth() {
  return new Date().toISOString().slice(0, 7); // YYYY-MM
}

export default function AdminVADetail() {
  const { vaUserId } = useParams();
  const nav = useNavigate();
  const [detail, setDetail] = useState(null);
  const [notes, setNotes] = useState([]);
  const [err, setErr] = useState("");

  // Goal editor state
  const [goalForm, setGoalForm] = useState({ target_leads: "", target_commission: "", note: "" });
  const [savingGoal, setSavingGoal] = useState(false);

  // Note editor state
  const [newNote, setNewNote] = useState("");
  const [newNoteShared, setNewNoteShared] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [editingNote, setEditingNote] = useState(null); // note object or null
  const [editNoteForm, setEditNoteForm] = useState({ text: "", is_shared: false });

  const load = async () => {
    try {
      const [d, n] = await Promise.all([
        api.get(`/pm/vas/${vaUserId}/detail`),
        api.get(`/pm/coaching-notes/${vaUserId}`),
      ]);
      setDetail(d.data);
      setNotes(n.data.items || []);
      setGoalForm({
        target_leads: d.data.month_goal.target_leads ?? "",
        target_commission: d.data.month_goal.target_commission ?? "",
        note: d.data.month_goal.note || "",
      });
    } catch (e) {
      setErr(getErr(e));
    }
  };

  useEffect(() => {
    /* eslint-disable-next-line */
    load();
  }, [vaUserId]);

  const saveGoal = async () => {
    setSavingGoal(true);
    try {
      await api.post(`/pm/va-goals/${vaUserId}`, {
        month: currentMonth(),
        target_leads: goalForm.target_leads === "" ? null : parseInt(goalForm.target_leads, 10),
        target_commission:
          goalForm.target_commission === "" ? null : parseFloat(goalForm.target_commission),
        note: goalForm.note || null,
      });
      toast.success("Goal saved");
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingGoal(false);
    }
  };

  const addNote = async () => {
    if (!newNote.trim()) {
      toast.error("Note cannot be empty");
      return;
    }
    setSavingNote(true);
    try {
      await api.post(`/pm/coaching-notes/${vaUserId}`, {
        text: newNote.trim(),
        is_shared: newNoteShared,
      });
      toast.success(newNoteShared ? "Shared with VA" : "Private note saved");
      setNewNote("");
      setNewNoteShared(false);
      load();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSavingNote(false);
    }
  };

  const startEditNote = (n) => {
    setEditingNote(n);
    setEditNoteForm({ text: n.text, is_shared: n.is_shared });
  };

  const saveEditNote = async () => {
    try {
      await api.patch(`/pm/coaching-notes/${editingNote.note_id}`, {
        text: editNoteForm.text.trim(),
        is_shared: editNoteForm.is_shared,
      });
      toast.success("Note updated");
      setEditingNote(null);
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const deleteNote = async (n) => {
    if (!window.confirm("Delete this note?")) return;
    try {
      await api.delete(`/pm/coaching-notes/${n.note_id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (err) {
    return (
      <div className="p-6 md:p-10">
        <button onClick={() => nav("/ops/va-program/vas")} className="font-mono-label">
          ← Back
        </button>
        <div className="mt-4 border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>
      </div>
    );
  }
  if (!detail) {
    return <div className="p-6 md:p-10 font-mono-label">Loading…</div>;
  }

  const { va, stats, month_goal } = detail;

  return (
    <div className="p-6 md:p-10" data-testid="admin-va-detail">
      <button
        onClick={() => nav("/ops/va-program/vas")}
        data-testid="va-detail-back"
        className="font-mono-label flex items-center gap-1 hover:underline"
      >
        <ArrowLeft size={12} /> Back to VAs
      </button>

      <div className="mt-3 mb-8 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono-label">Admin · VA Detail</div>
          <h1 className="font-display text-4xl font-black tracking-tight">{va.name}</h1>
          <div className="mt-1 text-sm text-[#4B5563]">
            {va.email} · status:{" "}
            <strong className="uppercase tracking-widest">{va.va_status}</strong>
          </div>
        </div>
        <MessageUserButton
          userId={va.user_id}
          name={va.name}
          testId="va-detail-message"
          className="h-10 rounded-none"
        />
      </div>

      {/* Stats */}
      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatBox icon={Briefcase} label="Active leads" value={stats.active_leads} />
        <StatBox icon={CheckCircle} label="Conversion" value={`${stats.conversion_rate}%`} />
        <StatBox icon={CurrencyDollar} label="Paid lifetime" value={fmtMoney(stats.total_paid)} />
        <StatBox icon={Target} label="Paid count" value={stats.paid_count} />
      </div>

      {/* Monthly goal editor */}
      <section className="mb-8 border border-[#E5E7EB] bg-white p-6" data-testid="va-goal-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono-label">
            <Target size={14} weight="duotone" /> Monthly goal · {month_goal.month}
          </div>
          <Button
            data-testid="va-goal-save"
            onClick={saveGoal}
            disabled={savingGoal}
            className="h-9 rounded-none bg-[#030712] text-white text-xs"
          >
            <FloppyDisk size={12} className="mr-1" /> {savingGoal ? "Saving…" : "Save goal"}
          </Button>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div>
            <div className="font-mono-label mb-1">Target leads (this month)</div>
            <Input
              type="number"
              data-testid="va-goal-leads"
              value={goalForm.target_leads}
              onChange={(e) => setGoalForm({ ...goalForm, target_leads: e.target.value })}
              placeholder="e.g. 20"
              className="h-9 rounded-none border-[#030712]"
            />
            <div className="mt-1 text-[10px] text-[#9CA3AF]">
              MTD so far: <strong>{month_goal.mtd_leads}</strong>
            </div>
          </div>
          <div>
            <div className="font-mono-label mb-1">Target commission ($)</div>
            <Input
              type="number"
              data-testid="va-goal-commission"
              value={goalForm.target_commission}
              onChange={(e) => setGoalForm({ ...goalForm, target_commission: e.target.value })}
              placeholder="e.g. 500"
              className="h-9 rounded-none border-[#030712]"
            />
            <div className="mt-1 text-[10px] text-[#9CA3AF]">
              MTD paid: <strong>{fmtMoney(month_goal.mtd_commission)}</strong>
            </div>
          </div>
          <div>
            <div className="font-mono-label mb-1">Note (optional)</div>
            <Input
              data-testid="va-goal-note"
              value={goalForm.note}
              onChange={(e) => setGoalForm({ ...goalForm, note: e.target.value })}
              placeholder="e.g. Focus on commercial leads"
              className="h-9 rounded-none border-[#030712]"
            />
          </div>
        </div>
        <p className="mt-3 text-[10px] text-[#9CA3AF]">
          Tip: leave both targets blank and click Save to clear this month&apos;s goal.
        </p>
      </section>

      {/* Coaching notes */}
      <section className="border border-[#E5E7EB] bg-white p-6" data-testid="va-notes-section">
        <div className="flex items-center gap-2 font-mono-label">
          <ChatCircleDots size={14} weight="duotone" /> Coaching notes · {notes.length}
        </div>
        <div className="mt-4 border border-[#E5E7EB] p-4">
          <Textarea
            data-testid="va-note-new-text"
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            rows={3}
            placeholder="Add a coaching note about this VA…"
            className="rounded-none border-[#030712]"
          />
          <div className="mt-2 flex items-center justify-between">
            <label className="inline-flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                data-testid="va-note-new-shared"
                checked={newNoteShared}
                onChange={(e) => setNewNoteShared(e.target.checked)}
                className="h-3 w-3 accent-[#0044FF]"
              />
              <span className="flex items-center gap-1">
                {newNoteShared ? <Eye size={12} /> : <EyeSlash size={12} />}
                {newNoteShared ? "Shared with VA" : "Private (admin only)"}
              </span>
            </label>
            <Button
              data-testid="va-note-add"
              onClick={addNote}
              disabled={savingNote || !newNote.trim()}
              className="h-9 rounded-none bg-[#030712] text-white text-xs"
            >
              <Plus size={12} className="mr-1" /> Add note
            </Button>
          </div>
        </div>

        <ul className="mt-4 space-y-2">
          {notes.length === 0 && (
            <li className="text-sm text-[#9CA3AF]">No notes yet.</li>
          )}
          {notes.map((n) => (
            <li
              key={n.note_id}
              data-testid={`va-note-${n.note_id}`}
              className={`border-l-4 ${
                n.is_shared ? "border-[#0044FF] bg-[#EFF6FF]" : "border-[#9CA3AF] bg-[#F9FAFB]"
              } p-3`}
            >
              {editingNote?.note_id === n.note_id ? (
                <div className="space-y-2">
                  <Textarea
                    data-testid={`va-note-edit-text-${n.note_id}`}
                    value={editNoteForm.text}
                    onChange={(e) => setEditNoteForm({ ...editNoteForm, text: e.target.value })}
                    rows={3}
                    className="rounded-none border-[#030712]"
                  />
                  <div className="flex items-center justify-between">
                    <label className="inline-flex items-center gap-2 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editNoteForm.is_shared}
                        onChange={(e) =>
                          setEditNoteForm({ ...editNoteForm, is_shared: e.target.checked })
                        }
                        className="h-3 w-3 accent-[#0044FF]"
                      />
                      {editNoteForm.is_shared ? "Shared with VA" : "Private"}
                    </label>
                    <div className="flex gap-1">
                      <button
                        onClick={() => setEditingNote(null)}
                        className="border border-[#E5E7EB] bg-white px-2 py-1 text-xs"
                      >
                        <X size={11} />
                      </button>
                      <button
                        data-testid={`va-note-save-${n.note_id}`}
                        onClick={saveEditNote}
                        className="bg-[#030712] px-2 py-1 text-xs text-white"
                      >
                        <FloppyDisk size={11} />
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <p className="whitespace-pre-wrap text-sm">{n.text}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <div className="text-[10px] uppercase tracking-widest text-[#9CA3AF]">
                      {n.is_shared ? (
                        <span className="text-[#0044FF]">
                          <Eye size={10} className="mr-0.5 inline" /> Shared
                        </span>
                      ) : (
                        <span>
                          <EyeSlash size={10} className="mr-0.5 inline" /> Private
                        </span>
                      )}
                      {" · "}
                      {n.author_name} · {new Date(n.created_at).toLocaleDateString()}
                    </div>
                    <div className="flex gap-1">
                      <button
                        data-testid={`va-note-edit-${n.note_id}`}
                        onClick={() => startEditNote(n)}
                        className="border border-[#E5E7EB] bg-white px-2 py-1 text-xs hover:border-[#030712]"
                      >
                        <Pencil size={10} />
                      </button>
                      <button
                        data-testid={`va-note-delete-${n.note_id}`}
                        onClick={() => deleteNote(n)}
                        className="border border-[#FCA5A5] bg-white px-2 py-1 text-xs text-[#DC2626] hover:bg-[#DC2626] hover:text-white"
                      >
                        <Trash size={10} />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function StatBox({ icon: Icon, label, value }) {
  return (
    <div className="border border-[#E5E7EB] bg-white p-4">
      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
        <Icon size={12} weight="duotone" />
        {label}
      </div>
      <div className="mt-1 font-display text-2xl font-black">{value}</div>
    </div>
  );
}
