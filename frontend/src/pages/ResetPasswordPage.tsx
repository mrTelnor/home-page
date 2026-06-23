import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useConfirmReset } from "@/hooks/usePasswordReset";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export function ResetPasswordPage() {
  usePageTitle("Новый пароль");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const confirm = useConfirmReset();

  const validation = useQuery({
    queryKey: ["reset-validate", token],
    queryFn: () => api.get<{ valid: boolean }>(endpoints.passwordReset.validate(token)),
    enabled: token.length > 0,
    retry: false,
  });

  const loading = token.length > 0 && validation.isLoading;
  const invalid = !token || validation.data?.valid === false;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== repeat) {
      setError("Пароли не совпадают.");
      return;
    }
    confirm.mutate(
      { token, new_password: password },
      {
        onSuccess: () => navigate("/login"),
        onError: () => setError("Ссылка недействительна или устарела."),
      }
    );
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh]">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl text-center">Новый пароль</CardTitle>
        </CardHeader>
        {loading ? (
          <CardContent className="space-y-4">
            <p className="text-sm text-center text-muted-foreground">
              Проверка ссылки...
            </p>
          </CardContent>
        ) : invalid ? (
          <CardContent className="space-y-4">
            <p className="text-sm text-center text-destructive">
              Ссылка недействительна или устарела.
            </p>
            <Link to="/forgot-password" className="text-sm text-primary underline block text-center">
              Запросить новую ссылку
            </Link>
          </CardContent>
        ) : (
          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              {error && <p className="text-sm text-center text-destructive">{error}</p>}
              <div className="space-y-2">
                <Label htmlFor="password">Новый пароль</Label>
                <Input id="password" type="password" minLength={8} required
                  value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="repeat">Повторите пароль</Label>
                <Input id="repeat" type="password" minLength={8} required
                  value={repeat} onChange={(e) => setRepeat(e.target.value)} />
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={confirm.isPending}>
                {confirm.isPending ? "Сохранение..." : "Сменить пароль"}
              </Button>
            </CardFooter>
          </form>
        )}
      </Card>
    </div>
  );
}
