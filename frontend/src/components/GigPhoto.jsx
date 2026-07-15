import React, { useEffect, useState } from "react";
import { API } from "@/lib/api";

// Authenticated image loader for gig photos (served via /api/files).
export default function GigPhoto({ path, className = "", testId, alt = "" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, { credentials: "include" });
        if (!res.ok || !alive) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        if (alive) setSrc(url);
      } catch {}
    })();
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!src) return <div data-testid={testId} className={`animate-pulse bg-[#E5E7EB] ${className}`} />;
  return <img data-testid={testId} src={src} alt={alt} className={className} />;
}
