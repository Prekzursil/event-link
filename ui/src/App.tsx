import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { Toaster } from '@/components/ui/toaster';
import { Layout } from '@/components/layout/Layout';
import { LoadingPage } from '@/components/ui/loading';

// Auth pages
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';

// Main pages
import { EventsPage, EventDetailPage } from '@/pages/events';
import { MyEventsPage } from '@/pages/MyEventsPage';
import { FavoritesPage } from '@/pages/FavoritesPage';
import { StudentProfilePage } from '@/pages/profile';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

// Admin pages
import { AdminDashboardPage } from '@/pages/admin';

// Organizer pages
import {
  OrganizerDashboardPage,
  EventFormPage,
  ParticipantsPage,
  OrganizerProfilePage,
} from '@/pages/organizer';

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// Organizer route wrapper
function OrganizerRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isOrganizer, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!isOrganizer) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}

// Admin route wrapper
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!isAdmin) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}

// Guest only route (login/register)
function GuestRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes with layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<EventsPage />} />
        <Route path="/events/:id" element={<EventDetailPage />} />
        <Route path="/organizers/:id" element={<OrganizerProfilePage />} />
        <Route path="/forbidden" element={<ForbiddenPage />} />
        
        {/* Protected routes */}
        <Route
          path="/my-events"
          element={
            <ProtectedRoute>
              <MyEventsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/favorites"
          element={
            <ProtectedRoute>
              <FavoritesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <StudentProfilePage />
            </ProtectedRoute>
          }
        />

        {/* Organizer routes */}
        <Route
          path="/organizer"
          element={
            <OrganizerRoute>
              <OrganizerDashboardPage />
            </OrganizerRoute>
          }
        />
        <Route
          path="/organizer/events/new"
          element={
            <OrganizerRoute>
              <EventFormPage />
            </OrganizerRoute>
          }
        />
        <Route
          path="/organizer/events/:id/edit"
          element={
            <OrganizerRoute>
              <EventFormPage />
            </OrganizerRoute>
          }
        />
        <Route
          path="/organizer/events/:id/participants"
          element={
            <OrganizerRoute>
              <ParticipantsPage />
            </OrganizerRoute>
          }
        />

        {/* Admin routes */}
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminDashboardPage />
            </AdminRoute>
          }
        />

        {/* Catch all - 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* Auth routes (without main layout) */}
      <Route
        path="/login"
        element={
          <GuestRoute>
            <LoginPage />
          </GuestRoute>
        }
      />
      <Route
        path="/register"
        element={
          <GuestRoute>
            <RegisterPage />
          </GuestRoute>
        }
      />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
          <Toaster />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
