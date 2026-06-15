import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useRecipesList } from "@/hooks/useRecipes";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RecipeImage } from "@/components/RecipeImage";

type SortField = "title" | "created_at" | "updated_at";
type SortDir = "asc" | "desc";

const SORT_LABELS: Record<SortField, string> = {
  title: "По алфавиту",
  created_at: "По дате добавления",
  updated_at: "По дате изменения",
};

const SORT_FIELD_KEY = "recipes:sortField";
const SORT_DIR_KEY = "recipes:sortDir";

// Значения хранятся сырыми строками — совместимо со старым форматом
const rawString = { serialize: (v: string) => v };

export function RecipesPage() {
  usePageTitle("Рецепты");
  const user = useAuthStore((s) => s.user);
  const { data: recipes, isLoading } = useRecipesList();
  const [sortField, setSortField] = useLocalStorage<SortField>(SORT_FIELD_KEY, "title", {
    ...rawString,
    deserialize: (raw) =>
      raw === "title" || raw === "created_at" || raw === "updated_at" ? raw : undefined,
  });
  const [sortDir, setSortDir] = useLocalStorage<SortDir>(SORT_DIR_KEY, "asc", {
    ...rawString,
    deserialize: (raw) => (raw === "desc" ? "desc" : "asc"),
  });

  const handleSortFieldChange = (value: SortField) => {
    setSortField(value);
  };

  const toggleSortDir = () => {
    setSortDir((d) => (d === "asc" ? "desc" : "asc"));
  };

  const sorted = useMemo(() => {
    if (!recipes) return [];
    const copy = [...recipes];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortField === "title") {
        cmp = a.title.localeCompare(b.title, "ru");
      } else {
        cmp = new Date(a[sortField]).getTime() - new Date(b[sortField]).getTime();
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [recipes, sortField, sortDir]);

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Рецепты</h1>
        {user && (
          <Button asChild>
            <Link to="/recipes/new">Добавить рецепт</Link>
          </Button>
        )}
      </div>

      {recipes?.length ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Label htmlFor="sort-field" className="text-sm">
              Сортировка:
            </Label>
            <select
              id="sort-field"
              value={sortField}
              onChange={(e) => handleSortFieldChange(e.target.value as SortField)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {(Object.keys(SORT_LABELS) as SortField[]).map((f) => (
                <option key={f} value={f}>
                  {SORT_LABELS[f]}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={toggleSortDir}>
              {sortDir === "asc" ? "↑ По возрастанию" : "↓ По убыванию"}
            </Button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {sorted.map((recipe) => (
              <Link key={recipe.id} to={`/recipes/${recipe.id}`}>
                <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer overflow-hidden pt-0">
                  <RecipeImage
                    title={recipe.title}
                    kind={recipe.glyph_kind}
                    color={recipe.glyph_color}
                    imageUrl={recipe.image_url}
                  />
                  <CardHeader>
                    <CardTitle className="text-lg">{recipe.title}</CardTitle>
                    <p className="text-xs text-muted-foreground mt-1">
                      Добавлен: {new Date(recipe.created_at).toLocaleDateString("ru-RU")}
                      {recipe.updated_at !== recipe.created_at && (
                        <> · Изменён: {new Date(recipe.updated_at).toLocaleDateString("ru-RU")}</>
                      )}
                    </p>
                  </CardHeader>
                  <CardContent>
                    {recipe.description && (
                      <p className="text-muted-foreground text-sm truncate mb-2">
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
        </>
      ) : (
        <p className="text-muted-foreground text-center py-8">Рецептов пока нет</p>
      )}
    </div>
  );
}
