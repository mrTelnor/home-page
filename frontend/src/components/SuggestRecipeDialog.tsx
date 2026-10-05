import { useMemo, useState } from "react";
import { type Menu } from "@/api/types";
import { useAllRecipes, useSuggestRecipe } from "@/hooks/useMenu";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  menu: Menu;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type SortDir = "asc" | "desc";

// Поиск без учёта регистра; «ё» и «е» считаются одной буквой
const normalize = (s: string) => s.toLowerCase().replaceAll("ё", "е");

export function SuggestRecipeDialog({ menu, open, onOpenChange }: Readonly<Props>) {
  const { data: recipes } = useAllRecipes();
  const suggest = useSuggestRecipe();
  const [query, setQuery] = useState("");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const available = useMemo(() => {
    const menuRecipeIds = new Set(menu.recipes.map((r) => r.recipe_id));
    return recipes?.filter((r) => !menuRecipeIds.has(r.id)) ?? [];
  }, [recipes, menu.recipes]);

  const shown = useMemo(() => {
    const q = normalize(query.trim());
    const filtered = q ? available.filter((r) => normalize(r.title).includes(q)) : [...available];
    filtered.sort((a, b) => {
      const cmp = a.title.localeCompare(b.title, "ru");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return filtered;
  }, [available, query, sortDir]);

  // При закрытии сбрасываем поиск, чтобы диалог открывался с полным списком
  const handleOpenChange = (next: boolean) => {
    if (!next) setQuery("");
    onOpenChange(next);
  };

  const handleSuggest = (recipeId: string) => {
    suggest.mutate({ menuId: menu.id, recipeId }, { onSuccess: () => handleOpenChange(false) });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Предложить рецепт</DialogTitle>
        </DialogHeader>
        {available.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">Все рецепты уже в меню</p>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Поиск по названию"
                aria-label="Поиск рецепта"
              />
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                aria-label={sortDir === "asc" ? "Сортировка: от А до Я" : "Сортировка: от Я до А"}
                onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
              >
                {sortDir === "asc" ? "А → Я" : "Я → А"}
              </Button>
            </div>
            {shown.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">Ничего не найдено</p>
            ) : (
              <div className="grid gap-2">
                {shown.map((r) => (
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
