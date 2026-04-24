import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AvatarStack } from "@/components/Avatar";

interface Props {
  menu: Menu;
}

export function MenuResults({ menu }: Readonly<Props>) {
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
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <CardTitle className="text-lg truncate">{r.title}</CardTitle>
                      {isWinner && <Badge className="shrink-0">Победитель</Badge>}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {r.voters.length > 0 && <AvatarStack users={r.voters} size={24} />}
                      <Badge variant="outline">{r.votes_count} гол.</Badge>
                    </div>
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
