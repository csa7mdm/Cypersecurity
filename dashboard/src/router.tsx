import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';

// Pages
import Login from './pages/auth/Login';
import Signup from './pages/auth/Signup';
import OnboardingWizard from './pages/onboarding/Wizard';
import ComponentShowcase from './pages/demo/ComponentShowcase';
import Scans from './pages/Scans';
import Dashboard from './pages/dashboard/Home';

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
    return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppRouter: React.FC = () => {
    return (
        <BrowserRouter>
            <Routes>
                {/* Public routes */}
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
                <Route path="/onboarding" element={<OnboardingWizard />} />
                <Route path="/demo" element={<ComponentShowcase />} />

                {/* Protected routes */}
                <Route
                    path="/dashboard"
                    element={
                        <ProtectedRoute>
                            <Dashboard />
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/scans"
                    element={
                        <ProtectedRoute>
                            <Scans />
                        </ProtectedRoute>
                    }
                />

                {/* Default redirect */}
                <Route path="/" element={<Navigate to="/demo" replace />} />
                <Route path="*" element={<Navigate to="/demo" replace />} />
            </Routes>
        </BrowserRouter>
    );
};

export default AppRouter;
