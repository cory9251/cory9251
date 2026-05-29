import React from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute, PublicOnly } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import AdminLayout from "@/components/admin/AdminLayout";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import AdminGigs from "@/pages/admin/AdminGigs";
import GigDetail from "@/pages/admin/GigDetail";
import AdminWorkers from "@/pages/admin/AdminWorkers";
import WorkerDetail from "@/pages/admin/WorkerDetail";
import AdminSettings from "@/pages/admin/AdminSettings";
import WorkerLayout from "@/components/worker/WorkerLayout";
import WorkerFeed from "@/pages/worker/WorkerFeed";
import WorkerProfile from "@/pages/worker/WorkerProfile";
import WorkerAccepted from "@/pages/worker/WorkerAccepted";
import WorkerGigDetail from "@/pages/worker/WorkerGigDetail";
import "@/App.css";

function RouterShell() {
  const location = useLocation();
  // CRITICAL: handle Emergent OAuth callback synchronously before normal routes
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route
        path="/"
        element={
          <PublicOnly>
            <Landing />
          </PublicOnly>
        }
      />
      <Route
        path="/login"
        element={
          <PublicOnly>
            <Login />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <Register />
          </PublicOnly>
        }
      />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Admin */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute role="admin">
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="gigs" element={<AdminGigs />} />
        <Route path="gigs/:gigId" element={<GigDetail />} />
        <Route path="workers" element={<AdminWorkers />} />
        <Route path="workers/:userId" element={<WorkerDetail />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>

      {/* Worker */}
      <Route
        path="/app"
        element={
          <ProtectedRoute role="worker">
            <WorkerLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<WorkerFeed />} />
        <Route path="gigs/:gigId" element={<WorkerGigDetail />} />
        <Route path="accepted" element={<WorkerAccepted />} />
        <Route path="profile" element={<WorkerProfile />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <RouterShell />
          <Toaster position="top-right" />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
