import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface Props {
  menu: Menu;
  onVote: (recipeId: string) => void;
  votedRecipeId: string | null;
  isPending: boolean;
}

export function MenuVoting({ menu, onVote, votedRecipeId, isPending }: Props) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Голосование</h2>
      <Separator />
      <div className="grid gap-3">
        {menu.recipes.map((r) => {
          const isVoted = votedRecipeId === r.recipe_id;
          return (
            <Card key={r.id} className={isVoted ? "border-primary border-2" : ""}>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <Link
                    to={`/recipes/${r.recipe_id}`}
                    className="flex items-center gap-3 hover:underline"
                  >
                    <CardTitle className="text-lg">{r.title}</CardTitle>
                    <Badge variant="outline">{r.votes_count} гол.</Badge>
                  </Link>
                  {votedRecipeId ? (
                    isVoted && <Badge>Ваш голос</Badge>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => onVote(r.recipe_id)}
                      disabled={isPending}
                    >
                      Голосовать
                    </Button>
                  )}
                </div>
              </CardHeader>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
