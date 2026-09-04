import { Navigate, Outlet } from "react-router-dom";
import { useMe } from "@/hooks/useAuth";

export function ProtectedRoute() {
  const { data: user, isLoading, isError } = useMe();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    );
  }

  // Сетевой сбой/5xx: не выкидываем на /login (мы не знаем, авторизован ли),
  // а предлагаем обновить страницу — сессия сохраняется
  if (isError) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">
          Не удалось проверить авторизацию. Обновите страницу.
        </p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
