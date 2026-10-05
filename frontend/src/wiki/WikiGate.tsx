import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useLogout, useMe } from "@/hooks/useAuth";
import { mainSiteUrl } from "@/lib/wikiHost";
import { Button } from "@/components/ui/button";
import { loginPath } from "./paths";

function Centered({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="flex items-center justify-center min-h-screen px-4">{children}</div>;
}

/**
 * Доступ к вики — только role = admin. Гость уходит на вход с возвратом на ту же
 * страницу, обычный пользователь получает отказ. Это удобство интерфейса:
 * настоящая проверка — на бэкенде (401/403 на /api/wiki/*).
 */
export function WikiGate() {
  const { data: user, isLoading, isError } = useMe();
  const location = useLocation();
  const logout = useLogout();
  const siteUrl = mainSiteUrl();

  if (isLoading) {
    return (
      <Centered>
        <p className="text-muted-foreground">Загрузка...</p>
      </Centered>
    );
  }

  // Сетевой сбой/5xx: неизвестно, вошёл ли пользователь, — на вход не выкидываем
  if (isError) {
    return (
      <Centered>
        <p className="text-muted-foreground">Не удалось проверить авторизацию. Обновите страницу.</p>
      </Centered>
    );
  }

  if (!user) {
    return <Navigate to={loginPath(location.pathname + location.search)} replace />;
  }

  if (user.role !== "admin") {
    return (
      <Centered>
        <div className="max-w-md w-full rounded-xl border border-border bg-card p-8 text-center space-y-4">
          <h1 className="text-2xl font-bold">Нет доступа</h1>
          <p className="text-sm text-muted-foreground">
            Вики доступна только администраторам. Вы вошли как {user.username}.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {siteUrl && (
              <Button asChild>
                <a href={siteUrl}>На сайт</a>
              </Button>
            )}
            <Button variant="outline" onClick={() => logout.mutate()} disabled={logout.isPending}>
              Выйти
            </Button>
          </div>
        </div>
      </Centered>
    );
  }

  return <Outlet />;
}
