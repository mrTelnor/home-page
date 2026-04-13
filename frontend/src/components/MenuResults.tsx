import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface Props {
  menu: Menu;
}

export function MenuResults({ menu }: Props) {
  const sorted = [...menu.recipes].sort((a, b) => b.votes_count - a.votes_count);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Результаты</h2>
      <Separator />
      <div className="grid gap-3">
        {sorted.map((r) => {
          const isWinner = r.recipe_id === menu.winner_recipe_id;
          return (
            <Link key={r.id} to={`/recipes/${r.recipe_id}`}>
              <Card className={`hover:shadow-md transition-shadow cursor-pointer ${isWinner ? "border-primary border-2 bg-primary/5" : ""}`}>
                <CardHeader className="py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <CardTitle className="text-lg">{r.title}</CardTitle>
                      {isWinner && <Badge>Победитель</Badge>}
                    </div>
                    <Badge variant="outline">{r.votes_count} гол.</Badge>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
