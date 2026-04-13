import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface Props {
  menu: Menu;
  onSuggest: () => void;
  canSuggest: boolean;
}

export function MenuCollecting({ menu, onSuggest, canSuggest }: Props) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Сбор предложений</h2>
        <button
          onClick={onSuggest}
          disabled={!canSuggest}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:pointer-events-none"
        >
          Предложить рецепт
        </button>
      </div>
      <Separator />
      <div className="grid gap-3">
        {menu.recipes.map((r) => (
          <Link key={r.id} to={`/recipes/${r.recipe_id}`}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer">
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{r.title}</CardTitle>
                  <Badge variant={r.source === "random" ? "secondary" : "default"}>
                    {r.source === "random" ? "Случайный" : "Предложен"}
                  </Badge>
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
