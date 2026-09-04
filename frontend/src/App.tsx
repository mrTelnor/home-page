import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthAwareRoute } from "@/components/AuthAwareRoute";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";

// Code splitting: каждая страница — отдельный чанк (пейджи — named exports,
// поэтому оборачиваем в { default }). Гость ради списка рецептов больше не
// качает админку, формы и календарь.
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const HomePage = lazy(() => import("@/pages/HomePage").then((m) => ({ default: m.HomePage })));
const VotePage = lazy(() => import("@/pages/VotePage").then((m) => ({ default: m.VotePage })));
const VoteHistoryPage = lazy(() => import("@/pages/VoteHistoryPage").then((m) => ({ default: m.VoteHistoryPage })));
const VoteDetailPage = lazy(() => import("@/pages/VoteDetailPage").then((m) => ({ default: m.VoteDetailPage })));
const RecipesPage = lazy(() => import("@/pages/RecipesPage").then((m) => ({ default: m.RecipesPage })));
const RecipeNewPage = lazy(() => import("@/pages/RecipeNewPage").then((m) => ({ default: m.RecipeNewPage })));
const RecipeDetailPage = lazy(() => import("@/pages/RecipeDetailPage").then((m) => ({ default: m.RecipeDetailPage })));
const RecipeEditPage = lazy(() => import("@/pages/RecipeEditPage").then((m) => ({ default: m.RecipeEditPage })));
const ProfilePage = lazy(() => import("@/pages/ProfilePage").then((m) => ({ default: m.ProfilePage })));
const AdminUsersPage = lazy(() => import("@/pages/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import("@/pages/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

function RouteFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-muted-foreground">Загрузка...</p>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route element={<AuthAwareRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<HomePage />} />
                <Route path="/recipes" element={<RecipesPage />} />
                <Route path="/recipes/:id" element={<RecipeDetailPage />} />
              </Route>
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/vote" element={<VotePage />} />
                <Route path="/vote/history" element={<VoteHistoryPage />} />
                <Route path="/vote/history/:date" element={<VoteDetailPage />} />
                <Route path="/recipes/new" element={<RecipeNewPage />} />
                <Route path="/recipes/:id/edit" element={<RecipeEditPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/admin/users" element={<AdminUsersPage />} />
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
