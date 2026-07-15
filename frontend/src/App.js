import React from "react";
import { BrowserRouter, Routes, Route, useLocation, Navigate, useParams } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute, PublicOnly } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import CustomersPage from "@/pages/Customers";
import VAsLanding from "@/pages/VAsLanding";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
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
import AdminEmailBlast from "@/pages/admin/AdminEmailBlast";
import AdminSMSConsent from "@/pages/admin/AdminSMSConsent";
import AdminCustomerChat from "@/pages/admin/AdminCustomerChat";
import AdminReferrals from "@/pages/admin/AdminReferrals";
import WorkerReferrals from "@/pages/worker/WorkerReferrals";
import AdminProjects from "@/pages/admin/AdminProjects";
import AdminProjectDetail from "@/pages/admin/AdminProjectDetail";
import AdminQuotes from "@/pages/admin/AdminQuotes";
import AdminVAOverview from "@/pages/admin/AdminVAOverview";
import AdminVAAnalytics from "@/pages/admin/AdminVAAnalytics";
import AdminVAPipeline from "@/pages/admin/AdminVAPipeline";
import LeadDetail from "@/pages/LeadDetail";
import AdminVACommissions from "@/pages/admin/AdminVACommissions";
import AdminVAs from "@/pages/admin/AdminVAs";
import AdminVADetail from "@/pages/admin/AdminVADetail";
import AdminVPApplications from "@/pages/admin/AdminVPApplications";
import AdminTemplates from "@/pages/admin/AdminTemplates";
import AdminCommercialAccounts from "@/pages/admin/AdminCommercialAccounts";
import AdminOwnerPayouts from "@/pages/admin/AdminOwnerPayouts";
import VALayout from "@/components/va/VALayout";
import VADashboard from "@/pages/va/VADashboard";
import VALeaderboard from "@/pages/va/VALeaderboard";
import VATemplates from "@/pages/va/VATemplates";
import VASubmitLead from "@/pages/va/VASubmitLead";
import VAMyLeads from "@/pages/va/VAMyLeads";
import VAEarnings from "@/pages/va/VAEarnings";
import VATraining from "@/pages/va/VATraining";
import VAServices from "@/pages/va/VAServices";
import VAJobs from "@/pages/va/VAJobs";
import VAMyTeam from "@/pages/va/VAMyTeam";
import VAApprovedGuard from "@/components/va/VAApprovedGuard";
import VADigitalServices from "@/pages/va/VADigitalServices";
import AdminVADigital from "@/pages/admin/AdminVADigital";
import AdminVARates from "@/pages/admin/AdminVARates";
import AdminVATeams from "@/pages/admin/AdminVATeams";
import AdminBookkeeping from "@/pages/admin/AdminBookkeeping";
import AdminAnnouncements from "@/pages/admin/AdminAnnouncements";
import AdminAIAssignment from "@/pages/admin/AdminAIAssignment";
import AdminBadges from "@/pages/admin/AdminBadges";
import AdminTrades from "@/pages/admin/AdminTrades";
import AdminServicesCatalog from "@/pages/admin/AdminServicesCatalog";
import AdminVAJobs from "@/pages/admin/AdminVAJobs";
import AdminWorkerPay from "@/pages/admin/AdminWorkerPay";
import WorkerCertifications from "@/pages/worker/WorkerCertifications";
import WorkerProjectPage from "@/pages/worker/WorkerProjectPage";
import Messages from "@/pages/Messages";
import RatePage from "@/pages/RatePage";
import PublicGigPage from "@/pages/PublicGigPage";
import CustomerChat from "@/pages/CustomerChat";
import WorkerLayout from "@/components/worker/WorkerLayout";
import WorkerFeed from "@/pages/worker/WorkerFeed";
import WorkerProfile from "@/pages/worker/WorkerProfile";
import WorkerQuestionnaire from "@/pages/worker/WorkerQuestionnaire";
import WorkerAccepted from "@/pages/worker/WorkerAccepted";
import WorkerGigDetail from "@/pages/worker/WorkerGigDetail";
import PrivacyPolicy from "@/pages/legal/PrivacyPolicy";
import Terms from "@/pages/legal/Terms";
import SmsTerms from "@/pages/legal/SmsTerms";
import "@/App.css";

function RouterShell() {
  const location = useLocation();
  // CRITICAL: handle Emergent OAuth callback synchronously before normal routes
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<CustomersPage />} />
      <Route
        path="/work"
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
      <Route path="/c/:token" element={<CustomerChat />} />
      <Route path="/customers" element={<Navigate to="/" replace />} />
      <Route path="/services" element={<Navigate to="/" replace />} />
      <Route path="/vas" element={<VAsLanding />} />
      <Route path="/earn" element={<VAsLanding />} />
      <Route path="/work-with-us" element={<VAsLanding />} />
      <Route path="/virtual-professionals" element={<VAsLanding />} />
      <Route path="/join" element={<VAsLanding />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Public legal pages — links submitted to Twilio for A2P 10DLC approval */}
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/privacy-policy" element={<Navigate to="/privacy" replace />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/terms-and-conditions" element={<Navigate to="/terms" replace />} />
      <Route path="/sms-terms" element={<SmsTerms />} />
      <Route path="/sms-messaging-terms" element={<Navigate to="/sms-terms" replace />} />

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
        <Route path="assignments" element={<AdminGigs />} />
        <Route path="assignments/:gigId" element={<GigDetail />} />
        {/* Legacy aliases — bookmarks/emails sent before the rename */}
        <Route path="gigs" element={<Navigate to="/ops/assignments" replace />} />
        <Route path="gigs/:gigId" element={<RedirectWithParam to="/ops/assignments" param="gigId" />} />
        <Route path="workers" element={<AdminWorkers />} />
        <Route path="workers/:userId" element={<WorkerDetail />} />
        <Route path="projects" element={<AdminProjects />} />
        <Route path="projects/:projectId" element={<AdminProjectDetail />} />
        <Route path="quotes" element={<AdminQuotes />} />
        <Route path="reports" element={<AdminReports />} />
        <Route path="email-blast" element={<AdminEmailBlast />} />
        <Route path="sms-consent" element={<AdminSMSConsent />} />
        <Route path="customer-chats/:threadId" element={<AdminCustomerChat />} />
        <Route path="referrals" element={<AdminReferrals />} />
        <Route path="settings" element={<AdminSettings />} />
        <Route path="messages" element={<Messages />} />
        {/* VA Commission Program — admin / Program Manager / Owner */}
        <Route path="va-program" element={<AdminVAOverview />} />
        <Route path="va-program/analytics" element={<AdminVAAnalytics />} />
        <Route path="va-program/pipeline" element={<AdminVAPipeline />} />
        <Route path="va-program/digital" element={<AdminVADigital />} />
        <Route path="va-program/jobs" element={<AdminVAJobs />} />
        <Route path="va-program/rates" element={<AdminVARates />} />
        <Route path="va-program/teams" element={<AdminVATeams />} />
        <Route path="bookkeeping" element={<AdminBookkeeping />} />
        <Route path="worker-pay" element={<AdminWorkerPay />} />
        <Route path="announcements" element={<AdminAnnouncements />} />
        <Route path="ai-assignment" element={<AdminAIAssignment />} />
        <Route path="badges" element={<AdminBadges />} />
        <Route path="trades" element={<AdminTrades />} />
        <Route path="services" element={<AdminServicesCatalog />} />
        <Route path="va-program/pipeline/:leadId" element={<LeadDetail scope="admin" />} />
        <Route path="va-program/commissions" element={<AdminVACommissions />} />
        <Route path="va-program/vas" element={<AdminVAs />} />
        <Route path="va-program/vas/:vaUserId" element={<AdminVADetail />} />
        <Route path="va-program/applications" element={<AdminVPApplications />} />
        <Route path="va-program/templates" element={<AdminTemplates />} />
        <Route path="va-program/commercial" element={<AdminCommercialAccounts />} />
        <Route path="payouts" element={<AdminOwnerPayouts />} />
      </Route>

      {/* Legacy /admin/* — redirect to /ops/* so old bookmarks/emails still work */}
      <Route path="/admin" element={<Navigate to="/ops" replace />} />
      <Route path="/admin/calendar" element={<Navigate to="/ops/calendar" replace />} />
      <Route path="/admin/requests" element={<Navigate to="/ops/requests" replace />} />
      <Route path="/admin/gigs" element={<Navigate to="/ops/assignments" replace />} />
      <Route path="/admin/gigs/:gigId" element={<RedirectWithParam to="/ops/assignments" param="gigId" />} />
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
        <Route path="assignments/:gigId" element={<WorkerGigDetail />} />
        <Route path="projects/:projectId" element={<WorkerProjectPage />} />
        <Route path="my-assignments" element={<WorkerAccepted />} />
        {/* Legacy aliases — pre-rename emails / bookmarks / PWA caches */}
        <Route path="gigs/:gigId" element={<RedirectWithParam to="/crew/assignments" param="gigId" />} />
        <Route path="my-gigs" element={<Navigate to="/crew/my-assignments" replace />} />
        <Route path="messages" element={<Messages />} />
        <Route path="refer" element={<WorkerReferrals />} />
        <Route path="certifications" element={<WorkerCertifications />} />
        <Route path="onboarding" element={<WorkerQuestionnaire onboarding />} />
        <Route path="questionnaire" element={<WorkerQuestionnaire />} />
        <Route path="me" element={<WorkerProfile />} />
      </Route>

      {/* VA Commission Program */}
      <Route
        path="/va"
        element={
          <ProtectedRoute role="va">
            <VALayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<VADashboard />} />
        <Route path="submit" element={<VAApprovedGuard featureLabel="Submit Lead"><VASubmitLead /></VAApprovedGuard>} />
        <Route path="leads" element={<VAApprovedGuard featureLabel="My Leads"><VAMyLeads /></VAApprovedGuard>} />
        <Route path="leads/:leadId" element={<VAApprovedGuard featureLabel="Lead detail"><LeadDetail scope="va" /></VAApprovedGuard>} />
        <Route path="digital" element={<VAApprovedGuard featureLabel="Digital Services"><VADigitalServices /></VAApprovedGuard>} />
        <Route path="earnings" element={<VAApprovedGuard featureLabel="Earnings"><VAEarnings /></VAApprovedGuard>} />
        <Route path="leaderboard" element={<VALeaderboard />} />
        <Route path="templates" element={<VATemplates />} />
        <Route path="training" element={<VATraining />} />
        <Route path="services" element={<VAServices />} />
        <Route path="jobs" element={<VAApprovedGuard featureLabel="Digital Jobs"><VAJobs /></VAApprovedGuard>} />
        <Route path="team" element={<VAApprovedGuard featureLabel="My Team"><VAMyTeam /></VAApprovedGuard>} />
        <Route path="messages" element={<VAApprovedGuard featureLabel="Messages"><Messages /></VAApprovedGuard>} />
      </Route>

      {/* Legacy /app/* — redirect to /crew/* */}
      <Route path="/app" element={<Navigate to="/crew" replace />} />
      <Route path="/app/gigs/:gigId" element={<RedirectWithParam to="/crew/assignments" param="gigId" />} />
      <Route path="/app/accepted" element={<Navigate to="/crew/my-assignments" replace />} />
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
