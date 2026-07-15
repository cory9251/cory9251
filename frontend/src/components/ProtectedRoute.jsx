import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export function ProtectedRoute({ children, role }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading || user === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="font-mono-label">Loading…</div>
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (role && user.role !== role) {
    return <Navigate to={roleHomePath(user)} replace />;
  }
  return children;
}

export function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading || user === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="font-mono-label">Loading…</div>
      </div>
    );
  }
  if (user && user !== false) {
    const next = new URLSearchParams(location.search).get("next");
    if (user.role === "worker" && next && next.startsWith("/")) {
      return <Navigate to={next} replace />;
    }
    // Fresh worker accounts (never touched the v2 questionnaire) get the
    // onboarding wizard first.
    if (
      user.role === "worker" &&
      user.questionnaire_version !== 2 &&
      !(user.work_classes || []).length
    ) {
      return <Navigate to="/crew/onboarding" replace />;
    }
    return <Navigate to={roleHomePath(user)} replace />;
  }
  return children;
}

export function roleHomePath(user) {
  if (!user) return "/login";
  if (user.role === "admin") return "/ops";
  if (user.role === "va") return "/va";
  return "/crew";
}
