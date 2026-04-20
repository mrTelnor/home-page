import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthAwareRoute } from "@/components/AuthAwareRoute";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { HomePage } from "@/pages/HomePage";
import { VotePage } from "@/pages/VotePage";
import { VoteHistoryPage } from "@/pages/VoteHistoryPage";
import { RecipesPage } from "@/pages/RecipesPage";
import { RecipeNewPage } from "@/pages/RecipeNewPage";
import { RecipeDetailPage } from "@/pages/RecipeDetailPage";
import { RecipeEditPage } from "@/pages/RecipeEditPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
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
              <Route path="/recipes/new" element={<RecipeNewPage />} />
              <Route path="/recipes/:id/edit" element={<RecipeEditPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
