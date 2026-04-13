import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipesList } from "@/hooks/useRecipes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function RecipesPage() {
  usePageTitle("Рецепты");
  const { data: recipes, isLoading } = useRecipesList();

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Рецепты</h1>
        <Button asChild>
          <Link to="/recipes/new">Добавить рецепт</Link>
        </Button>
      </div>

      {!recipes?.length ? (
        <p className="text-muted-foreground text-center py-8">Рецептов пока нет</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {recipes.map((recipe) => (
            <Link key={recipe.id} to={`/recipes/${recipe.id}`}>
              <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <CardTitle className="text-lg">{recipe.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  {recipe.description && (
                    <p className="text-muted-foreground text-sm line-clamp-2 mb-2">
                      {recipe.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{recipe.servings} порц.</span>
                    <span>{recipe.ingredients.length} ингр.</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
