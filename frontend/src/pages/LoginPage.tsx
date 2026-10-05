import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useLogin, useMe } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { ApiError } from "@/api/client";
import { redirectTo } from "@/lib/redirect";
import { safeWikiReturnUrl } from "@/lib/wikiReturn";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { WolfMark } from "@/components/WolfMark";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  usePageTitle("Вход");
  const navigate = useNavigate();
  // Гостя вики присылают сюда с адресом возврата в `?next=`. Принимается только адрес
  // вики этого же домена; всё остальное игнорируется — обычный вход с переходом на главную.
  const [params] = useSearchParams();
  const wikiUrl = safeWikiReturnUrl(params.get("next"));
  const leaving = useRef(false);
  const returnToWiki = useCallback(() => {
    if (!wikiUrl || leaving.current) return;
    leaving.current = true;
    // Другой origin: переходим сами, по проверенному адресу, а не через роутер
    redirectTo(wikiUrl);
  }, [wikiUrl]);
  const login = useLogin(wikiUrl ? { onLoggedIn: returnToWiki } : undefined);
  // «Кто я» здесь нужен только для возврата на вики: уже вошедшему форма ни к чему
  const { data: me } = useMe({ enabled: wikiUrl !== null });
  const alreadyIn = wikiUrl !== null && Boolean(me);

  useEffect(() => {
    if (alreadyIn) returnToWiki();
  }, [alreadyIn, returnToWiki]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ username, password });
  };

  let error: string | null = null;
  if (login.error instanceof ApiError) {
    error = login.error.status === 401 ? "Неверный логин или пароль" : login.error.message;
  }

  if (alreadyIn && wikiUrl) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 min-h-[80vh]">
        <p className="text-muted-foreground">Возвращаемся в вики...</p>
        <a href={wikiUrl} className="text-sm text-primary underline">
          Перейти в вики
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[80vh]">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center">
          <div className="flex justify-center mb-2">
            <WolfMark size={40} className="text-foreground" />
          </div>
          <CardTitle className="text-2xl text-center">Вход</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && <p className="text-sm text-destructive text-center">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="username">Имя пользователя</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <PasswordInput
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? "Вход..." : "Войти"}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => navigate("/recipes")}
            >
              Войти как гость
            </Button>
            <Link to="/forgot-password" className="text-sm text-primary underline">
              Забыли пароль?
            </Link>
            <p className="text-sm text-muted-foreground">
              Нет аккаунта?{" "}
              <Link to="/register" className="text-primary underline">
                Зарегистрироваться
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
