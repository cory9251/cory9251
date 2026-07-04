import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import {
  MagnifyingGlass,
  Broom,
  Monitor,
  Tag,
} from "@phosphor-icons/react";

function ServiceCard({ svc }) {
  return (
    <div
      data-testid={`service-card-${svc.service_id}`}
      className="flex flex-col border border-[#E5E7EB] bg-white p-5 transition-colors hover:border-[#0044FF]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="font-display text-base font-black tracking-tight text-[#030712]">
          {svc.name}
        </div>
        {svc.price_display && (
          <span
            data-testid={`service-price-${svc.service_id}`}
            className="shrink-0 border border-[#0044FF] bg-[#F0F4FF] px-2 py-1 text-[11px] font-bold text-[#0044FF]"
          >
            {svc.price_display}
          </span>
        )}
      </div>
      {svc.description && (
        <p className="mt-2 text-sm leading-relaxed text-[#4B5563]">{svc.description}</p>
      )}
    </div>
  );
}

export default function VAServices() {
  const [items, setItems] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api
      .get("/services/catalog")
      .then((r) => setItems(r.data.items || []))
      .catch(() => setItems([]));
  }, []);

  const filtered = useMemo(() => {
    if (!items) return [];
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (s) =>
        s.name.toLowerCase().includes(needle) ||
        (s.description || "").toLowerCase().includes(needle)
    );
  }, [items, q]);

  const physical = filtered.filter((s) => s.category === "physical");
  const digital = filtered.filter((s) => s.category === "digital");

  return (
    <div className="mx-auto max-w-5xl" data-testid="va-services-page">
      <div className="font-mono-label flex items-center gap-2 text-[#4B5563]">
        <Tag size={14} weight="fill" /> SERVICE CATALOG
      </div>
      <h1 className="font-display mt-1 text-3xl font-black tracking-tight sm:text-4xl">
        What we offer
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-[#4B5563]">
        Every service you can pitch — with starting prices so you can talk
        numbers on the spot. Any of these can become a lead you submit.
      </p>

      <div className="relative mt-6 max-w-md">
        <MagnifyingGlass
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]"
        />
        <Input
          data-testid="services-search-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search services…"
          className="pl-9"
        />
      </div>

      {items === null ? (
        <div className="mt-10 text-sm text-[#4B5563]">Loading…</div>
      ) : (
        <>
          <section className="mt-8">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center bg-[#030712] text-white">
                <Broom size={16} weight="fill" />
              </div>
              <h2 className="font-display text-lg font-black tracking-tight">
                Physical services{" "}
                <span className="text-sm font-bold text-[#9CA3AF]">
                  ({physical.length})
                </span>
              </h2>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {physical.map((s) => (
                <ServiceCard key={s.service_id} svc={s} />
              ))}
              {physical.length === 0 && (
                <div className="text-sm text-[#9CA3AF]">No matches.</div>
              )}
            </div>
          </section>

          <section className="mt-10">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center bg-[#0044FF] text-white">
                <Monitor size={16} weight="fill" />
              </div>
              <h2 className="font-display text-lg font-black tracking-tight">
                Digital services{" "}
                <span className="text-sm font-bold text-[#9CA3AF]">
                  ({digital.length})
                </span>
              </h2>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {digital.map((s) => (
                <ServiceCard key={s.service_id} svc={s} />
              ))}
              {digital.length === 0 && (
                <div className="text-sm text-[#9CA3AF]">No matches.</div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
