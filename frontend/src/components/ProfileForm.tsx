import { type FormEvent, useState } from "react";
import { useUpdateProfile } from "@/hooks/useProfile";
import { type User } from "@/api/types";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  user: User;
}

export function ProfileForm({ user }: Readonly<Props>) {
  const [firstName, setFirstName] = useState(user.first_name ?? "");
  const [birthday, setBirthday] = useState(user.birthday ?? "");
  const [isVolkov, setIsVolkov] = useState(user.is_volkov);
  const [gender, setGender] = useState<"male" | "female" | "">(user.gender ?? "");
  const [email, setEmail] = useState(user.email ?? "");
  const [notificationsEnabled, setNotificationsEnabled] = useState(user.notifications_enabled);
  const [calendarEnabled, setCalendarEnabled] = useState(user.calendar_notifications_enabled);
  // Уведомления календаря бот шлёт только админам — остальным переключатель не нужен
  const isAdmin = user.role === "admin";
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateProfile();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    setError(null);
    update.mutate(
      {
        first_name: firstName.trim() || null,
        birthday: birthday || null,
        is_volkov: isVolkov,
        gender: gender || null,
        email: email.trim() || null,
        notifications_enabled: notificationsEnabled,
        ...(isAdmin && { calendar_notifications_enabled: calendarEnabled }),
      },
      {
        onSuccess: () => setSaved(true),
        onError: (err) => setError(err instanceof ApiError ? err.message : "Не удалось сохранить"),
      }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="first-name">Имя</Label>
        <Input
          id="first-name"
          value={firstName}
          onChange={(e) => {
            setFirstName(e.target.value);
            setSaved(false);
          }}
          maxLength={50}
          placeholder="Введите имя"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setSaved(false);
          }}
          placeholder="you@example.com"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="birthday">День рождения</Label>
        <Input
          id="birthday"
          type="date"
          value={birthday}
          onChange={(e) => {
            setBirthday(e.target.value);
            setSaved(false);
          }}
        />
      </div>

      <div className="space-y-2">
        <Label>Пол</Label>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="gender"
              value="male"
              checked={gender === "male"}
              onChange={() => {
                setGender("male");
                setSaved(false);
              }}
            />
            <span>Мужской</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="gender"
              value="female"
              checked={gender === "female"}
              onChange={() => {
                setGender("female");
                setSaved(false);
              }}
            />
            <span>Женский</span>
          </label>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="is-volkov"
          type="checkbox"
          checked={isVolkov}
          onChange={(e) => {
            setIsVolkov(e.target.checked);
            setSaved(false);
          }}
        />
        <Label htmlFor="is-volkov" className="cursor-pointer">
          Я Волков{gender === "female" ? "а" : ""}
        </Label>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="notifications-enabled"
          type="checkbox"
          checked={notificationsEnabled}
          onChange={(e) => {
            setNotificationsEnabled(e.target.checked);
            setSaved(false);
          }}
        />
        <Label htmlFor="notifications-enabled" className="cursor-pointer">
          Уведомления бота об ужинах
        </Label>
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2">
          <input
            id="calendar-notifications-enabled"
            type="checkbox"
            checked={calendarEnabled}
            onChange={(e) => {
              setCalendarEnabled(e.target.checked);
              setSaved(false);
            }}
          />
          <Label htmlFor="calendar-notifications-enabled" className="cursor-pointer">
            Уведомления бота о семейном календаре
          </Label>
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? "Сохранение..." : "Сохранить"}
        </Button>
        {saved && <span className="text-sm text-muted-foreground">Сохранено ✓</span>}
        {error && <span className="text-sm text-destructive">{error}</span>}
      </div>
    </form>
  );
}
