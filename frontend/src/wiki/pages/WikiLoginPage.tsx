import { type FormEvent, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { useMe } from "@/hooks/useAuth";
import { mainSiteUrl } from "@/lib/wikiHost";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { WolfMark } from "@/components/WolfMark";
import { useWikiTitle } from "../hooks";
import { safeNextPath } from "../paths";

/**
 * Вход прямо на адресе вики, с возвратом на страницу из `?next=`.
 * Регистрации и гостевого входа здесь нет — вики только для администраторов.
 * Сессия общая с сайтом: cookie ставит и читает API, а не страница.
 */
export function WikiLoginPage() {
  useWikiTitle("Вход");
  const [params] = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useMe();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const siteUrl = mainSiteUrl();

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Уже вошёл (в том числе на основном сайте) — форма не нужна
  if (user) return <Navigate to={next} replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api.post(endpoints.auth.login, { username, password });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate(next, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "Неверный логин или пароль" : err.message);
      } else {
        setError("Не удалось выполнить вход. Проверьте соединение.");
      }
      setPending(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center">
          <div className="flex justify-center mb-2">
            <WolfMark size={40} className="text-foreground" />
          </div>
          <CardTitle className="text-2xl text-center">Вход в вики</CardTitle>
        </CardHeader>
        <form onSubmit={(e) => void handleSubmit(e)}>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-destructive text-center">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="username">Имя пользователя</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <PasswordInput
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Вход..." : "Войти"}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Вики доступна только администраторам.
            </p>
            {siteUrl && (
              <a href={siteUrl} className="text-sm text-primary underline">
                На сайт
              </a>
            )}
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
