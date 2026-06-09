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
  if (loading || user === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="font-mono-label">Loading…</div>
      </div>
    );
  }
  if (user && user !== false) {
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
