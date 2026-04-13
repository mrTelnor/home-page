import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipesList } from "@/hooks/useRecipes";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { VoteWidget } from "@/components/VoteWidget";

export function HomePage() {
  usePageTitle("Главная");
  const user = useAuthStore((s) => s.user);
  const { data: recipes } = useRecipesList();

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">
        Привет, {user?.first_name || user?.username}!
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
