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
  EnvelopeSimple,
  DeviceMobile,
  Bell,
  CheckCircle,
} from "@phosphor-icons/react";

export default function GigDetail() {
  const { gigId } = useParams();
  const nav = useNavigate();
  const [gig, setGig] = useState(null);
  const [blastOpen, setBlastOpen] = useState(false);
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
            <Item label="Location" value={gig.location} />
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
        <div className="font-mono-label">Roster</div>
        <h2 className="mt-1 font-display text-2xl font-black">
          Accepted workers ({(gig.acceptances || []).length})
        </h2>

        {(!gig.acceptances || gig.acceptances.length === 0) ? (
          <div className="mt-4 border border-dashed border-[#E5E7EB] p-8 text-sm text-[#4B5563]">
            No one has accepted yet. Send a blast to alert your crew.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left">
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Name</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Contact</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Status</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Clock in</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Clock out</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Hours</th>
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
                    ? "ON THE CLOCK"
                    : completed
                    ? "COMPLETED"
                    : "ACCEPTED";
                  return (
                  <tr key={a.acceptance_id} className="hover:bg-[#F9FAFB]">
                    <td className="border-b border-[#E5E7EB] px-4 py-3 font-semibold">{a.worker_name || a.worker_id}</td>
                    <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                      <div>{a.worker_email}</div>
                      {a.worker_phone && <div className="text-[#4B5563]">{a.worker_phone}</div>}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-4 py-3">
                      <span className={`px-2 py-1 text-[10px] font-bold tracking-widest ${statusClass}`}>
                        {statusLabel}
                      </span>
                    </td>
                    <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs text-[#4B5563]">
                      {a.clock_in_at ? new Date(a.clock_in_at).toLocaleString() : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs text-[#4B5563]">
                      {a.clock_out_at ? new Date(a.clock_out_at).toLocaleString() : "—"}
                    </td>
                    <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs font-bold">
                      {a.hours_worked != null ? `${a.hours_worked.toFixed(2)}h` : "—"}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={blastOpen} onOpenChange={setBlastOpen}>
        <DialogContent className="max-w-lg rounded-none border-[#030712]" data-testid="blast-dialog">
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
