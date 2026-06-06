import React from "react";
import { BrowserRouter, Routes, Route, useLocation, Navigate, useParams } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute, PublicOnly } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import CustomersPage from "@/pages/Customers";
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
import AdminCalendar from "@/pages/admin/AdminCalendar";
import AdminRequests from "@/pages/admin/AdminRequests";
import AdminReports from "@/pages/admin/AdminReports";
import AdminProjects from "@/pages/admin/AdminProjects";
import AdminProjectDetail from "@/pages/admin/AdminProjectDetail";
import RatePage from "@/pages/RatePage";
import PublicGigPage from "@/pages/PublicGigPage";
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
      <Route path="/rate/:token" element={<RatePage />} />
      <Route path="/gigs/:gigId" element={<PublicGigPage />} />
      <Route path="/customers" element={<CustomersPage />} />
      <Route path="/services" element={<CustomersPage />} />

      {/* Admin / Ops */}
      <Route
        path="/ops"
        element={
          <ProtectedRoute role="admin">
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="calendar" element={<AdminCalendar />} />
        <Route path="requests" element={<AdminRequests />} />
        <Route path="gigs" element={<AdminGigs />} />
        <Route path="gigs/:gigId" element={<GigDetail />} />
        <Route path="workers" element={<AdminWorkers />} />
        <Route path="workers/:userId" element={<WorkerDetail />} />
        <Route path="projects" element={<AdminProjects />} />
        <Route path="projects/:projectId" element={<AdminProjectDetail />} />
        <Route path="reports" element={<AdminReports />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>

      {/* Legacy /admin/* — redirect to /ops/* so old bookmarks/emails still work */}
      <Route path="/admin" element={<Navigate to="/ops" replace />} />
      <Route path="/admin/calendar" element={<Navigate to="/ops/calendar" replace />} />
      <Route path="/admin/requests" element={<Navigate to="/ops/requests" replace />} />
      <Route path="/admin/gigs" element={<Navigate to="/ops/gigs" replace />} />
      <Route path="/admin/gigs/:gigId" element={<RedirectWithParam to="/ops/gigs" param="gigId" />} />
      <Route path="/admin/workers" element={<Navigate to="/ops/workers" replace />} />
      <Route path="/admin/workers/:userId" element={<RedirectWithParam to="/ops/workers" param="userId" />} />
      <Route path="/admin/reports" element={<Navigate to="/ops/reports" replace />} />
      <Route path="/admin/settings" element={<Navigate to="/ops/settings" replace />} />

      {/* Worker / Crew */}
      <Route
        path="/crew"
        element={
          <ProtectedRoute role="worker">
            <WorkerLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<WorkerFeed />} />
        <Route path="gigs/:gigId" element={<WorkerGigDetail />} />
        <Route path="my-gigs" element={<WorkerAccepted />} />
        <Route path="me" element={<WorkerProfile />} />
      </Route>

      {/* Legacy /app/* — redirect to /crew/* */}
      <Route path="/app" element={<Navigate to="/crew" replace />} />
      <Route path="/app/gigs/:gigId" element={<RedirectWithParam to="/crew/gigs" param="gigId" />} />
      <Route path="/app/accepted" element={<Navigate to="/crew/my-gigs" replace />} />
      <Route path="/app/profile" element={<Navigate to="/crew/me" replace />} />
    </Routes>
  );
}

// Helper to redirect routes with a URL param to the new path
function RedirectWithParam({ to, param }) {
  const params = useParams();
  return <Navigate to={`${to}/${params[param]}`} replace />;
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
