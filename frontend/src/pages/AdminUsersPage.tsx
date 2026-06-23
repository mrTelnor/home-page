import { useState } from "react";
import { Navigate } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAuthStore } from "@/store/auth";
import { useAdminResetLink, useAdminUsers } from "@/hooks/useAdminUsers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AdminUsersPage() {
  usePageTitle("Пользователи");
  const user = useAuthStore((s) => s.user);
  const { data: users, isLoading } = useAdminUsers();
  const resetLink = useAdminResetLink();
  const [links, setLinks] = useState<Record<string, string>>({});

  if (user && user.role !== "admin") return <Navigate to="/" replace />;

  const generate = (id: string) => {
    resetLink.mutate(id, {
      onSuccess: (res) => setLinks((prev) => ({ ...prev, [id]: res.link })),
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Пользователи</h1>
      {isLoading && <p className="text-muted-foreground">Загрузка...</p>}
      {users?.map((u) => (
        <Card key={u.id}>
          <CardHeader>
            <CardTitle className="text-lg">{u.username}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Telegram: {u.has_telegram ? "да" : "нет"} · Email: {u.has_email ? "да" : "нет"}
            </p>
            <Button onClick={() => generate(u.id)} disabled={resetLink.isPending}>
              Сбросить пароль
            </Button>
            {links[u.id] && (
              <Input readOnly value={links[u.id]} onFocus={(e) => e.currentTarget.select()} />
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
