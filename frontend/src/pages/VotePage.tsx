import { useState } from "react";
import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useTodayMenu, useVote } from "@/hooks/useMenu";
import { useAuthStore } from "@/store/auth";
import { MenuCollecting } from "@/components/MenuCollecting";
import { MenuVoting } from "@/components/MenuVoting";
import { MenuResults } from "@/components/MenuResults";
import { SuggestRecipeDialog } from "@/components/SuggestRecipeDialog";
import { Button } from "@/components/ui/button";

export function VotePage() {
  usePageTitle("Голосование за ужин");
  const { data: menu, isLoading } = useTodayMenu();
  const user = useAuthStore((s) => s.user);
  const vote = useVote();
  const [suggestOpen, setSuggestOpen] = useState(false);

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  if (!menu) {
    return (
      <div className="text-center py-16 space-y-4">
        <p className="text-xl text-muted-foreground">Меню появится в 8:00</p>
      </div>
    );
  }

  const userSuggested = menu.recipes.some(
    (r) => r.source === "user" && r.added_by === user?.id
  );
  const canSuggest = user?.role === "admin"
    ? menu.recipes.filter((r) => r.added_by === user?.id && r.source === "user").length < 3
    : !userSuggested;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Голосование за ужин</h1>
        <Button variant="outline" asChild>
          <Link to="/vote/history">История</Link>
        </Button>
      </div>

      {menu.status === "collecting" && (
        <>
          <MenuCollecting menu={menu} onSuggest={() => setSuggestOpen(true)} canSuggest={canSuggest} />
          <SuggestRecipeDialog menu={menu} open={suggestOpen} onOpenChange={setSuggestOpen} />
        </>
      )}

      {menu.status === "voting" && (
        <MenuVoting
          menu={menu}
          onVote={(recipeId) => vote.mutate({ menuId: menu.id, recipeId })}
          votedRecipeId={null}
          isPending={vote.isPending}
        />
      )}

      {menu.status === "closed" && <MenuResults menu={menu} />}
    </div>
  );
}
