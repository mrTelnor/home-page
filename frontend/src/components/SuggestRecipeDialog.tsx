import { type Menu, useAllRecipes, useSuggestRecipe } from "@/hooks/useMenu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  menu: Menu;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SuggestRecipeDialog({ menu, open, onOpenChange }: Readonly<Props>) {
  const { data: recipes } = useAllRecipes();
  const suggest = useSuggestRecipe();

  const menuRecipeIds = new Set(menu.recipes.map((r) => r.recipe_id));
  const available = recipes?.filter((r) => !menuRecipeIds.has(r.id)) ?? [];

  const handleSuggest = (recipeId: string) => {
    suggest.mutate(
      { menuId: menu.id, recipeId },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Предложить рецепт</DialogTitle>
        </DialogHeader>
        {available.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">
            Все рецепты уже в меню
          </p>
        ) : (
          <div className="grid gap-2">
            {available.map((r) => (
              <Card
                key={r.id}
                className="cursor-pointer hover:bg-accent transition-colors"
                onClick={() => handleSuggest(r.id)}
              >
                <CardHeader className="py-3">
                  <CardTitle className="text-base">{r.title}</CardTitle>
                </CardHeader>
              </Card>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
