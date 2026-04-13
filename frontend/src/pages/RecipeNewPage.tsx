import { usePageTitle } from "@/hooks/usePageTitle";
import { useCreateRecipe } from "@/hooks/useRecipes";
import { RecipeForm } from "@/components/RecipeForm";

export function RecipeNewPage() {
  usePageTitle("Новый рецепт");
  const create = useCreateRecipe();

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Новый рецепт</h1>
      <RecipeForm
        onSubmit={(data) => create.mutate(data)}
        isPending={create.isPending}
        submitLabel="Создать рецепт"
      />
    </div>
  );
}
