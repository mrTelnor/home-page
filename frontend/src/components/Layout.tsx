import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { useLogout } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";

export function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(-1)}
              disabled={isHome}
            >
              &larr; Назад
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/">На главную</Link>
            </Button>
            <span className="text-muted-foreground hidden sm:inline">|</span>
            <Link to="/" className="text-xl font-bold hidden sm:inline">
              Семейная страница Волковых
            </Link>
          </div>
          {user ? (
            <div className="flex items-center gap-2 sm:gap-4">
              <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
                <Link to="/profile">{user.username}</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link to="/profile">Профиль</Link>
              </Button>
              <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
                Выйти
              </Button>
            </div>
          ) : (
            <Button variant="outline" size="sm" asChild>
              <Link to="/login">Войти</Link>
            </Button>
          )}
        </div>
      </nav>
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
