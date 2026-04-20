import { Outlet } from "react-router-dom";
import { useMe } from "@/hooks/useAuth";

export function AuthAwareRoute() {
  const { isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Загрузка...</p>
      </div>
    );
  }

  return <Outlet />;
}
