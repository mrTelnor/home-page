import { Link, useParams } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipe, useUpdateRecipe } from "@/hooks/useRecipes";
import { RecipeForm } from "@/components/RecipeForm";

export function RecipeEditPage() {
  usePageTitle("Редактирование рецепта");
  const { id = "" } = useParams<{ id: string }>();
  const { data: recipe, isLoading } = useRecipe(id);
  const update = useUpdateRecipe(id);

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  if (!recipe) {
    return <p className="text-muted-foreground text-center py-8">Рецепт не найден</p>;
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link
        to={`/recipes/${recipe.id}`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        ← К рецепту
      </Link>
      <h1 className="text-3xl font-bold">Редактирование рецепта</h1>
      <RecipeForm
        initialData={{
          title: recipe.title,
          description: recipe.description ?? "",
          servings: recipe.servings,
          ingredients: recipe.ingredients,
          glyph_kind: recipe.glyph_kind,
          glyph_color: recipe.glyph_color,
        }}
        onSubmit={(data) => update.mutate(data)}
        isPending={update.isPending}
        submitLabel="Сохранить изменения"
      />
    </div>
  );
}
