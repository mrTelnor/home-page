import { Link } from "react-router-dom";
import { useTodayMenu } from "@/hooks/useMenu";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function VoteWidget() {
  const { data: menu, isLoading } = useTodayMenu();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Голосование за ужин</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Загрузка...</p>
        </CardContent>
      </Card>
    );
  }

  if (!menu) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Голосование за ужин</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Меню появится в 8:00</p>
        </CardContent>
      </Card>
    );
  }

  const winner = menu.recipes.find((r) => r.recipe_id === menu.winner_recipe_id);

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <CardTitle>Голосование за ужин</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {menu.status === "collecting" && (
          <p className="text-muted-foreground">
            Сбор предложений — {menu.recipes.length} рецептов в меню
          </p>
        )}
        {menu.status === "voting" && (
          <p className="text-muted-foreground">Голосование открыто</p>
        )}
        {menu.status === "closed" && (
          <p className="text-muted-foreground">
            Победил: <span className="font-semibold text-foreground">{winner?.title ?? "—"}</span>
          </p>
        )}
        <Button asChild className="w-full">
          <Link to="/vote">
            {menu.status === "voting" ? "Голосовать" : menu.status === "collecting" ? "Перейти" : "Подробнее"}
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
