import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { type ResetChannel, useRequestReset } from "@/hooks/usePasswordReset";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

const SENT_MSG = "Если аккаунт существует, мы отправили инструкции для сброса.";
const NO_CHANNELS_MSG =
  "Не удалось подобрать канал восстановления. Обратитесь к администратору.";

export function ForgotPasswordPage() {
  usePageTitle("Восстановление пароля");
  const [identifier, setIdentifier] = useState("");
  const [choices, setChoices] = useState<ResetChannel[] | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const request = useRequestReset();

  const submit = (channel?: ResetChannel) => {
    request.mutate(
      { identifier: identifier.trim(), channel },
      {
        onSuccess: (res) => {
          if (res.status === "sent") setDone(SENT_MSG);
          else if (res.status === "no_channels") setDone(NO_CHANNELS_MSG);
          else if (res.status === "choose") setChoices(res.channels ?? []);
        },
      }
    );
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setChoices(null);
    setDone(null);
    submit();
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh]">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl text-center">Восстановление пароля</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {done && <p className="text-sm text-center">{done}</p>}
            {!done && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="identifier">Логин или email</Label>
                  <Input
                    id="identifier"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    required
                  />
                </div>
                {choices && (
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Куда отправить ссылку?</p>
                    {choices.includes("telegram") && (
                      <Button type="button" variant="outline" className="w-full"
                        onClick={() => submit("telegram")}>
                        Отправить в Telegram
                      </Button>
                    )}
                    {choices.includes("email") && (
                      <Button type="button" variant="outline" className="w-full"
                        onClick={() => submit("email")}>
                        Отправить на Email
                      </Button>
                    )}
                  </div>
                )}
              </>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            {!done && !choices && (
              <Button type="submit" className="w-full" disabled={request.isPending}>
                {request.isPending ? "Отправка..." : "Отправить ссылку"}
              </Button>
            )}
            <Link to="/login" className="text-sm text-primary underline">
              Вернуться ко входу
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
