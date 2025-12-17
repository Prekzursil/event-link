import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
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
    return <Navigate to="/" replace />;
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

      {/* Catch all - redirect to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
