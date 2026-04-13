import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipesList } from "@/hooks/useRecipes";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { VoteWidget } from "@/components/VoteWidget";

export function HomePage() {
  usePageTitle("Главная");
  const user = useAuthStore((s) => s.user);
  const { data: recipes } = useRecipesList();

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">
        Привет, {user?.username}!
      </h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <VoteWidget />
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle>Рецепты</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-muted-foreground">
              {recipes ? `${recipes.length} рецептов в базе` : "Загрузка..."}
            </p>
            <Button asChild className="w-full">
              <Link to="/recipes">Перейти</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
