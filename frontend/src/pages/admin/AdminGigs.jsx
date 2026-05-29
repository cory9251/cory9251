import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import CreateGigDialog from "@/components/admin/CreateGigDialog";
import { Plus, Megaphone, Broom, Wrench, Car } from "@phosphor-icons/react";

const CAT_ICON = { cleaning: Broom, labor: Wrench, driver: Car };

export default function AdminGigs() {
  const [gigs, setGigs] = useState([]);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState(false);
  const nav = useNavigate();

  const load = async () => {
    try {
      const params = {};
      if (category !== "all") params.category = category;
      if (status !== "all") params.status = status;
      const { data } = await api.get("/gigs", { params });
      setGigs(data);
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [category, status]);

  return (
    <div data-testid="admin-gigs">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E5E7EB] px-6 py-8 md:px-10">
        <div>
          <div className="font-mono-label">Manage</div>
          <h1 className="mt-1 font-display text-4xl font-black tracking-tight">
            Gigs
          </h1>
        </div>
        <Button
          data-testid="open-create-gig"
          onClick={() => setOpen(true)}
          className="h-11 rounded-none bg-[#0044FF] text-white hover:bg-[#0036cc]"
        >
          <Plus size={16} className="mr-2" /> New gig
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E7EB] px-6 py-4 md:px-10">
        <span className="font-mono-label">Filters</span>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="h-9 w-44 rounded-none border-[#030712]" data-testid="filter-category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            <SelectItem value="cleaning">Cleaning</SelectItem>
            <SelectItem value="labor">Labor</SelectItem>
            <SelectItem value="driver">Driver / Ride</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-9 w-40 rounded-none border-[#030712]" data-testid="filter-status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="filled">Filled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="px-6 md:px-10 py-6">
        {gigs.length === 0 ? (
          <div className="border border-dashed border-[#E5E7EB] p-12 text-center text-sm text-[#4B5563]">
            No gigs match. Try a different filter or post a new gig.
          </div>
        ) : (
          <div className="overflow-x-auto border border-[#E5E7EB]">
            <table className="w-full text-sm">
              <thead className="bg-[#F9FAFB]">
                <tr className="text-left">
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Title</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Category</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">When</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Pay</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Slots</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Status</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3 font-mono-label">Blasts</th>
                  <th className="border-b border-[#E5E7EB] px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {gigs.map((g) => {
                  const Icon = CAT_ICON[g.category];
                  return (
                    <tr
                      key={g.gig_id}
                      data-testid={`gig-row-${g.gig_id}`}
                      className="hover:bg-[#F9FAFB]"
                    >
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <button
                          onClick={() => nav(`/admin/gigs/${g.gig_id}`)}
                          className="font-display text-base font-bold hover:text-[#0044FF]"
                        >
                          {g.title}
                        </button>
                        <div className="text-xs text-[#4B5563]">{g.location}</div>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <span className="inline-flex items-center gap-2">
                          <Icon size={16} weight="duotone" />
                          <span className="text-xs uppercase tracking-wider">{g.category}</span>
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">{g.scheduled_date}</td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        ${Number(g.pay_rate).toFixed(2)} {g.pay_type === "hourly" ? "/hr" : "flat"}
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        {g.slots_filled}/{g.slots}
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3">
                        <span
                          className={`px-2 py-1 text-[10px] font-bold tracking-widest ${
                            g.status === "open"
                              ? "bg-[#0044FF] text-white"
                              : "bg-[#030712] text-white"
                          }`}
                        >
                          {g.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-xs">
                        <span className="inline-flex items-center gap-1">
                          <Megaphone size={12} /> {g.blast_count || 0}
                        </span>
                      </td>
                      <td className="border-b border-[#E5E7EB] px-4 py-3 text-right">
                        <button
                          data-testid={`open-gig-${g.gig_id}`}
                          onClick={() => nav(`/admin/gigs/${g.gig_id}`)}
                          className="text-xs font-semibold text-[#0044FF] hover:underline"
                        >
                          Manage →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateGigDialog open={open} onOpenChange={setOpen} onCreated={load} />
    </div>
  );
}
