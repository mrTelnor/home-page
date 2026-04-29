import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { useLogout } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useTodayMenu } from "@/hooks/useMenu";
import { Button } from "@/components/ui/button";
import { WolfMark } from "@/components/WolfMark";

export function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useLogout();
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { data: menu } = useTodayMenu();
  const isHome = location.pathname === "/";

  let voteLabel = "Меню дня";
  if (menu?.status === "voting") voteLabel = "Проголосовать";
  else if (menu?.status === "collecting") voteLabel = "Предложить рецепт";

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(-1)}
              disabled={isHome}
            >
              &larr; Назад
            </Button>
            <Link to="/" className="flex items-center gap-2 group">
              <WolfMark size={24} className="text-foreground" />
              <span className="text-xl font-bold hidden sm:inline">
                Волковы
              </span>
            </Link>
          </div>

          {user && (
            <div className="hidden md:flex items-center gap-1">
              <Link
                to="/vote"
                className="px-3 py-1.5 text-xl font-normal text-foreground/80 hover:text-foreground rounded-md hover:bg-accent transition-colors"
              >
                {voteLabel}
              </Link>
              <Link
                to="/recipes/new"
                className="px-3 py-1.5 text-xl font-normal text-foreground/80 hover:text-foreground rounded-md hover:bg-accent transition-colors"
              >
                Добавить рецепт
              </Link>
              <Link
                to="/recipes"
                className="px-3 py-1.5 text-xl font-normal text-foreground/80 hover:text-foreground rounded-md hover:bg-accent transition-colors"
              >
                Открыть книгу
              </Link>
            </div>
          )}

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
              title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            >
              {theme === "dark" ? "☀" : "☾"}
            </Button>
            {user ? (
              <>
                <Button variant="ghost" size="sm" asChild className="hidden lg:inline-flex">
                  <Link to="/profile">{user.username}</Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link to="/profile">Профиль</Link>
                </Button>
                <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
                  Выйти
                </Button>
              </>
            ) : (
              <Button variant="outline" size="sm" asChild>
                <Link to="/login">Войти</Link>
              </Button>
            )}
          </div>
        </div>
      </nav>
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
