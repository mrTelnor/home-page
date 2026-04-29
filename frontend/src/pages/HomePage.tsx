import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { Button } from "@/components/ui/button";
import { VoteWidget } from "@/components/VoteWidget";
import { WolfMark } from "@/components/WolfMark";

export function HomePage() {
  usePageTitle("Главная");
  const user = useAuthStore((s) => s.user);

  if (!user) {
    return (
      <div className="space-y-8 text-center py-12">
        <div className="flex justify-center">
          <WolfMark size={96} className="text-foreground opacity-90" stroke={1.4} />
        </div>
        <h1 className="text-4xl font-bold">Семейная страница Волковых</h1>
        <p className="text-muted-foreground text-lg">
          Добро пожаловать! Вы можете посмотреть нашу базу рецептов.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild>
            <Link to="/recipes">Смотреть рецепты</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/login">Войти</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">
          Привет, {user.first_name || user.username}!
        </h1>
        <WolfMark size={48} className="text-foreground opacity-30 hidden sm:block" stroke={1.4} />
      </div>

      <VoteWidget />
    </div>
  );
}
