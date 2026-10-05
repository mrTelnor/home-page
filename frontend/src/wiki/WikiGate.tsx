import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useLogout, useMe } from "@/hooks/useAuth";
import { redirectTo } from "@/lib/redirect";
import { mainSiteUrl } from "@/lib/wikiHost";
import { Button } from "@/components/ui/button";
import { siteLoginUrl, wikiReturnPath } from "./paths";

function Centered({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="flex items-center justify-center min-h-screen px-4">{children}</div>;
}

/**
 * Гость: своей формы входа у вики нет — уходим на страницу входа основного сайта,
 * она вернёт на эту же страницу вики. Переход на другой origin делаем сами, не роутером.
 */
function GuestRedirect() {
  const location = useLocation();
  const { refetch, isFetching } = useMe();
  const loginUrl = siteLoginUrl(wikiReturnPath(location));

  useEffect(() => {
    if (loginUrl) redirectTo(loginUrl);
  }, [loginUrl]);

  if (loginUrl) {
    return (
      <Centered>
        <div className="text-center space-y-3">
          <p className="text-muted-foreground">Переходим на страницу входа...</p>
          <a href={loginUrl} className="text-sm text-primary underline">
            Войти на сайте
          </a>
        </div>
      </Centered>
    );
  }

  // Вики открыта не на поддомене wiki. (локально, VITE_WIKI=true): адрес сайта неизвестен,
  // перенаправлять некуда. Сессия общая — достаточно войти на сайте в этом же браузере.
  return (
    <Centered>
      <div className="max-w-md w-full rounded-xl border border-border bg-card p-8 text-center space-y-4">
        <h1 className="text-2xl font-bold">Нужен вход</h1>
        <p className="text-sm text-muted-foreground">
          Вход в вики выполняется на основном сайте. Войдите там в этом же браузере и нажмите
          «Проверить снова».
        </p>
        <Button onClick={() => void refetch()} disabled={isFetching}>
          Проверить снова
        </Button>
      </div>
    </Centered>
  );
}

/**
 * Доступ к вики — только role = admin. Гость уходит на вход основного сайта с возвратом
 * на ту же страницу, обычный пользователь получает отказ. Это удобство интерфейса:
 * настоящая проверка — на бэкенде (401/403 на /api/wiki/*).
 */
export function WikiGate() {
  const { data: user, isLoading, isError } = useMe();
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
    return <GuestRedirect />;
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
