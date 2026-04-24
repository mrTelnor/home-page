import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipesList } from "@/hooks/useRecipes";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { VoteWidget } from "@/components/VoteWidget";
import { WolfMark } from "@/components/WolfMark";

export function HomePage() {
  usePageTitle("Главная");
  const user = useAuthStore((s) => s.user);
  const { data: recipes } = useRecipesList();

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
      <h1 className="text-3xl font-bold">
        Привет, {user.first_name || user.username}!
      </h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <VoteWidget />
        <Link to="/recipes" className="block h-full">
          <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
            <CardHeader>
              <CardTitle>Рецепты</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                {recipes ? `${recipes.length} рецептов в базе` : "Загрузка..."}
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
