import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { checkAuth } = useAuth();
  const [error, setError] = useState("");
  const hasProcessed = React.useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const run = async () => {
      const hash = location.hash || window.location.hash;
      const m = hash.match(/session_id=([^&]+)/);
      if (!m) {
        setError("Missing session_id");
        return;
      }
      try {
        const { data } = await api.post("/auth/google/session", {
          session_id: m[1],
        });
        // Clear hash
        window.history.replaceState(null, "", window.location.pathname);
        await checkAuth();
        navigate(data.role === "admin" ? "/admin" : "/app", { replace: true });
      } catch (e) {
        setError(e?.response?.data?.detail || "Login failed");
      }
    };
    run();
  }, [location.hash, navigate, checkAuth]);

  return (
    <div className="flex h-screen items-center justify-center bg-white" data-testid="auth-callback">
      <div className="text-center">
        <div className="font-mono-label mb-2">Authenticating</div>
        <div className="font-display text-3xl">Signing you in…</div>
        {error && <div className="mt-4 text-sm text-red-600">{error}</div>}
      </div>
    </div>
  );
}
