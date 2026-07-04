import React, { useEffect, useState } from "react";
import { api, getErr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Tag, Plus, PencilSimple, Trash, Eye, EyeSlash } from "@phosphor-icons/react";

const EMPTY = {
  name: "",
  category: "physical",
  description: "",
  price_display: "",
  sort_order: 0,
  active: true,
};

function ServiceDialog({ open, onClose, initial, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const editing = Boolean(initial?.service_id);

  useEffect(() => {
    if (open) setForm(initial ? { ...EMPTY, ...initial } : EMPTY);
  }, [open, initial]);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        category: form.category,
        description: form.description || "",
        price_display: form.price_display || "",
        sort_order: Number(form.sort_order) || 0,
        active: Boolean(form.active),
      };
      if (editing) {
        await api.put(`/admin/services/catalog/${initial.service_id}`, payload);
      } else {
        await api.post("/admin/services/catalog", payload);
      }
      toast.success(editing ? "Service updated" : "Service added");
      onSaved();
      onClose();
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="service-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black">
            {editing ? "Edit service" : "Add service"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Name</Label>
            <Input
              data-testid="service-form-name"
              value={form.name}
              onChange={(e) => upd("name", e.target.value)}
              placeholder="e.g. Gutter Cleaning"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Category</Label>
              <select
                data-testid="service-form-category"
                value={form.category}
                onChange={(e) => upd("category", e.target.value)}
                className="h-10 w-full border border-input bg-white px-3 text-sm"
              >
                <option value="physical">Physical</option>
                <option value="digital">Digital</option>
              </select>
            </div>
            <div>
              <Label>Price display</Label>
              <Input
                data-testid="service-form-price"
                value={form.price_display}
                onChange={(e) => upd("price_display", e.target.value)}
                placeholder="e.g. $99 – $250"
              />
            </div>
          </div>
          <div>
            <Label>Description (the VA's pitch)</Label>
            <Textarea
              data-testid="service-form-description"
              value={form.description}
              onChange={(e) => upd("description", e.target.value)}
              rows={3}
              placeholder="One or two lines a VA can say out loud to a prospect."
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Sort order</Label>
              <Input
                data-testid="service-form-sort"
                type="number"
                value={form.sort_order}
                onChange={(e) => upd("sort_order", e.target.value)}
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
                <input
                  data-testid="service-form-active"
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => upd("active", e.target.checked)}
                />
                Visible to VAs
              </label>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-testid="service-form-save"
            onClick={save}
            disabled={saving}
            className="bg-[#0044FF] text-white hover:bg-[#0033CC]"
          >
            {saving ? "Saving…" : editing ? "Save changes" : "Add service"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Row({ svc, onEdit, onToggle, onDelete }) {
  return (
    <div
      data-testid={`admin-service-row-${svc.service_id}`}
      className={`flex items-start gap-3 border border-[#E5E7EB] bg-white p-4 ${
        !svc.active ? "opacity-50" : ""
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-display text-sm font-black">{svc.name}</span>
          {svc.price_display && (
            <span className="border border-[#0044FF] bg-[#F0F4FF] px-1.5 py-0.5 text-[10px] font-bold text-[#0044FF]">
              {svc.price_display}
            </span>
          )}
          {!svc.active && (
            <span className="bg-[#9CA3AF] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
              Hidden
            </span>
          )}
        </div>
        {svc.description && (
          <p className="mt-1 line-clamp-2 text-xs text-[#4B5563]">{svc.description}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          data-testid={`service-toggle-${svc.service_id}`}
          onClick={() => onToggle(svc)}
          title={svc.active ? "Hide from VAs" : "Show to VAs"}
          className="grid h-8 w-8 place-items-center border border-[#E5E7EB] text-[#4B5563] hover:bg-[#F3F4F6]"
        >
          {svc.active ? <Eye size={14} /> : <EyeSlash size={14} />}
        </button>
        <button
          type="button"
          data-testid={`service-edit-${svc.service_id}`}
          onClick={() => onEdit(svc)}
          className="grid h-8 w-8 place-items-center border border-[#E5E7EB] text-[#4B5563] hover:bg-[#F3F4F6]"
        >
          <PencilSimple size={14} />
        </button>
        <button
          type="button"
          data-testid={`service-delete-${svc.service_id}`}
          onClick={() => onDelete(svc)}
          className="grid h-8 w-8 place-items-center border border-[#E5E7EB] text-red-600 hover:bg-red-50"
        >
          <Trash size={14} />
        </button>
      </div>
    </div>
  );
}

export default function AdminServicesCatalog() {
  const [items, setItems] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/services/catalog");
      setItems(data.items || []);
    } catch (e) {
      toast.error(getErr(e));
      setItems([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async (svc) => {
    try {
      await api.put(`/admin/services/catalog/${svc.service_id}`, {
        name: svc.name,
        category: svc.category,
        description: svc.description || "",
        price_display: svc.price_display || "",
        sort_order: svc.sort_order || 0,
        active: !svc.active,
      });
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const remove = async (svc) => {
    if (!window.confirm(`Delete "${svc.name}"? This can't be undone.`)) return;
    try {
      await api.delete(`/admin/services/catalog/${svc.service_id}`);
      toast.success("Service deleted");
      load();
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const physical = (items || []).filter((s) => s.category === "physical");
  const digital = (items || []).filter((s) => s.category === "digital");

  return (
    <div className="mx-auto max-w-4xl" data-testid="admin-services-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
            <Tag size={14} weight="fill" /> GROWTH · SERVICE CATALOG
          </div>
          <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
            Service catalog
          </h1>
          <p className="mt-2 max-w-xl text-sm text-[#4B5563]">
            Everything VAs can pitch — name, pitch line, and price range. Edits
            show up in the VA portal instantly.
          </p>
        </div>
        <Button
          data-testid="add-service-btn"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
          className="bg-[#030712] text-white hover:bg-[#1f2937]"
        >
          <Plus size={16} className="mr-1" /> Add service
        </Button>
      </div>

      {items === null ? (
        <div className="mt-10 text-sm text-[#4B5563]">Loading…</div>
      ) : (
        <>
          <h2 className="font-display mt-8 text-lg font-black">
            Physical <span className="text-sm text-[#9CA3AF]">({physical.length})</span>
          </h2>
          <div className="mt-3 space-y-2">
            {physical.map((s) => (
              <Row
                key={s.service_id}
                svc={s}
                onEdit={(x) => {
                  setEditing(x);
                  setDialogOpen(true);
                }}
                onToggle={toggle}
                onDelete={remove}
              />
            ))}
          </div>
          <h2 className="font-display mt-8 text-lg font-black">
            Digital <span className="text-sm text-[#9CA3AF]">({digital.length})</span>
          </h2>
          <div className="mt-3 space-y-2">
            {digital.map((s) => (
              <Row
                key={s.service_id}
                svc={s}
                onEdit={(x) => {
                  setEditing(x);
                  setDialogOpen(true);
                }}
                onToggle={toggle}
                onDelete={remove}
              />
            ))}
          </div>
        </>
      )}

      <ServiceDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        initial={editing}
        onSaved={load}
      />
    </div>
  );
}
