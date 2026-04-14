import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipe, useDeleteRecipe } from "@/hooks/useRecipes";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

function scaleAmount(amount: string, factor: number): string {
  const normalized = amount.replace(",", ".").trim();
  if (!Number.isFinite(Number(normalized))) {
    return amount;
  }
  const num = Number(normalized);
  const scaled = num * factor;
  const rounded = Math.round(scaled * 100) / 100;
  return String(rounded).replace(".", ",");
}

export function RecipeDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { data: recipe, isLoading } = useRecipe(id);
  const deleteRecipe = useDeleteRecipe();
  const user = useAuthStore((s) => s.user);
  const [servings, setServings] = useState<number | null>(null);

  usePageTitle(recipe?.title ?? "Рецепт");

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  if (!recipe) {
    return <p className="text-muted-foreground text-center py-8">Рецепт не найден</p>;
  }

  const canEdit = user?.id === recipe.author_id || user?.role === "admin";
  const currentServings = servings ?? recipe.servings;
  const factor = currentServings / recipe.servings;

  const handleDelete = () => {
    if (!confirm("Удалить рецепт? Это действие нельзя отменить.")) return;
    deleteRecipe.mutate(recipe.id);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">{recipe.title}</h1>
        {canEdit && (
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link to={`/recipes/${recipe.id}/edit`}>Редактировать</Link>
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteRecipe.isPending}
            >
              Удалить
            </Button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-4">
        <Badge variant="outline">
          Добавлен: {new Date(recipe.created_at).toLocaleDateString("ru-RU")}
        </Badge>
        {recipe.updated_at !== recipe.created_at && (
          <Badge variant="outline">
            Изменён: {new Date(recipe.updated_at).toLocaleDateString("ru-RU")}
          </Badge>
        )}
      </div>

      <Separator />

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Ингредиенты</h2>
          <div className="flex items-center gap-2">
            <Label htmlFor="portion-input" className="text-sm">
              Порций:
            </Label>
            <Input
              id="portion-input"
              type="number"
              min={1}
              max={999}
              value={currentServings}
              onChange={(e) => {
                const val = Number(e.target.value);
                setServings(val > 0 ? val : null);
              }}
              className="w-20"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setServings(null)}
              disabled={currentServings === recipe.servings}
            >
              Сбросить
            </Button>
          </div>
        </div>
        {recipe.ingredients.length === 0 ? (
          <p className="text-muted-foreground">Нет ингредиентов</p>
        ) : (
          <div className="grid gap-2">
            {recipe.ingredients.map((ing) => (
              <Card key={ing.id}>
                <CardContent className="py-3 flex items-center justify-between">
                  <span className="font-medium">{ing.name}</span>
                  <span className="text-muted-foreground">
                    {scaleAmount(ing.amount, factor)}
                    {ing.unit ? ` ${ing.unit}` : ""}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {recipe.description && (
        <>
          <Separator />
          <div className="space-y-3">
            <h2 className="text-xl font-semibold">Описание / Как готовить</h2>
            <p className="text-muted-foreground whitespace-pre-wrap">{recipe.description}</p>
          </div>
        </>
      )}
    </div>
  );
}
