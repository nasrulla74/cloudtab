import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/shared/ProtectedRoute";
import { ToastProvider } from "./components/shared/Toast";
import MainLayout from "./components/layout/MainLayout";
import LoginPage from "./pages/LoginPage";
import SetupPage from "./pages/SetupPage";
import DashboardPage from "./pages/DashboardPage";
import ServersPage from "./pages/ServersPage";
import ServerDetailPage from "./pages/ServerDetailPage";
import InstanceDeployPage from "./pages/InstanceDeployPage";
import InstanceDetailPage from "./pages/InstanceDetailPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/servers" element={<ServersPage />} />
              <Route path="/servers/:id" element={<ServerDetailPage />} />
              <Route path="/servers/:id/deploy" element={<InstanceDeployPage />} />
              <Route path="/instances/:id" element={<InstanceDetailPage />} />
            </Route>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
