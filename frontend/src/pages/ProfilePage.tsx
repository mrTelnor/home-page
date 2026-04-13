import { useState } from "react";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useAuthStore } from "@/store/auth";
import { useTelegramUnlink } from "@/hooks/useProfile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TelegramLoginButton } from "@/components/TelegramLoginButton";
import { ChangePasswordDialog } from "@/components/ChangePasswordDialog";
import { ProfileForm } from "@/components/ProfileForm";

export function ProfilePage() {
  usePageTitle("Личный кабинет");
  const user = useAuthStore((s) => s.user);
  const unlink = useTelegramUnlink();
  const [pwdOpen, setPwdOpen] = useState(false);

  if (!user) return null;

  const handleUnlink = () => {
    if (!confirm("Отвязать Telegram?")) return;
    unlink.mutate();
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Личный кабинет</h1>

      <Card>
        <CardHeader>
          <CardTitle>Аккаунт</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Имя пользователя</span>
            <span className="font-medium">{user.username}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Роль</span>
            <Badge variant="secondary">{user.role}</Badge>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Зарегистрирован</span>
            <span>{new Date(user.created_at).toLocaleDateString("ru-RU")}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Личные данные</CardTitle>
        </CardHeader>
        <CardContent>
          <ProfileForm user={user} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Telegram</CardTitle>
        </CardHeader>
        <CardContent>
          {user.tg_id ? (
            <div className="space-y-3">
              <p className="text-sm">
                <Badge>Привязан</Badge> <span className="text-muted-foreground ml-2">ID: {user.tg_id}</span>
              </p>
              <Button variant="outline" onClick={handleUnlink} disabled={unlink.isPending}>
                Отвязать Telegram
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Привяжите Telegram, чтобы пользоваться ботом.
              </p>
              <TelegramLoginButton />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Безопасность</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={() => setPwdOpen(true)}>Сменить пароль</Button>
        </CardContent>
      </Card>

      <ChangePasswordDialog open={pwdOpen} onOpenChange={setPwdOpen} />
    </div>
  );
}
