import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useCreateRecipe } from "@/hooks/useRecipes";
import { RecipeForm } from "@/components/RecipeForm";

export function RecipeNewPage() {
  usePageTitle("Новый рецепт");
  const create = useCreateRecipe();

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link
        to="/recipes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        ← К списку рецептов
      </Link>
      <h1 className="text-3xl font-bold">Новый рецепт</h1>
      <RecipeForm
        onSubmit={(data) => create.mutate(data)}
        isPending={create.isPending}
        submitLabel="Создать рецепт"
      />
    </div>
  );
}
