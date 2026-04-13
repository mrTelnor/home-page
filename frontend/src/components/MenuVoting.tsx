import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface Props {
  menu: Menu;
  onVote: (recipeId: string) => void;
  onCancelVote: () => void;
  isPending: boolean;
}

export function MenuVoting({ menu, onVote, onCancelVote, isPending }: Props) {
  const userVoted = menu.user_voted_recipe_id !== null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">
          Голосование{" "}
          <span className="text-base font-normal text-muted-foreground">
            (проголосовало: {menu.total_votes} чел., вы {userVoted ? "проголосовали" : "не проголосовали"})
          </span>
        </h2>
      </div>
      <Separator />
      <div className="grid gap-3">
        {menu.recipes.map((r) => {
          const isUserVote = menu.user_voted_recipe_id === r.recipe_id;
          return (
            <Card key={r.id} className={isUserVote ? "border-primary border-2" : ""}>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between">
                  <Link
                    to={`/recipes/${r.recipe_id}`}
                    className="flex items-center gap-3 hover:underline"
                  >
                    <CardTitle className="text-lg">{r.title}</CardTitle>
                    <Badge variant="outline">{r.votes_count} гол.</Badge>
                  </Link>
                  {isUserVote ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onCancelVote}
                      disabled={isPending}
                    >
                      Отменить голос
                    </Button>
                  ) : !userVoted ? (
                    <Button
                      size="sm"
                      onClick={() => onVote(r.recipe_id)}
                      disabled={isPending}
                    >
                      Голосовать
                    </Button>
                  ) : null}
                </div>
              </CardHeader>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
