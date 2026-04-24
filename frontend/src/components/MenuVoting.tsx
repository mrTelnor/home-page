import { Link } from "react-router-dom";
import { type Menu } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AvatarStack } from "@/components/Avatar";

interface Props {
  menu: Menu;
  onVote: (recipeId: string) => void;
  onCancelVote: () => void;
  isPending: boolean;
}

export function MenuVoting({ menu, onVote, onCancelVote, isPending }: Readonly<Props>) {
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
          let actionButton = null;
          if (isUserVote) {
            actionButton = (
              <Button
                variant="outline"
                size="sm"
                onClick={onCancelVote}
                disabled={isPending}
              >
                Отменить голос
              </Button>
            );
          } else if (userVoted === false) {
            actionButton = (
              <Button
                size="sm"
                onClick={() => onVote(r.recipe_id)}
                disabled={isPending}
              >
                Голосовать
              </Button>
            );
          }
          return (
            <Card key={r.id} className={isUserVote ? "border-primary border-2" : ""}>
              <CardHeader className="py-3">
                <div className="flex items-center justify-between gap-3">
                  <Link
                    to={`/recipes/${r.recipe_id}`}
                    className="flex items-center gap-3 hover:underline min-w-0"
                  >
                    <CardTitle className="text-lg truncate">{r.title}</CardTitle>
                    <Badge variant="outline" className="shrink-0">
                      {r.votes_count} гол.
                    </Badge>
                  </Link>
                  <div className="flex items-center gap-3 shrink-0">
                    {r.voters.length > 0 && <AvatarStack users={r.voters} size={24} />}
                    {actionButton}
                  </div>
                </div>
              </CardHeader>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
