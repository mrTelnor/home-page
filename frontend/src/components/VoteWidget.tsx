import { Link } from "react-router-dom";
import { useTodayMenu } from "@/hooks/useMenu";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function VoteWidget() {
  const { data: menu, isLoading } = useTodayMenu();

  const content = (() => {
    if (isLoading) {
      return <p className="text-muted-foreground">Загрузка...</p>;
    }
    if (!menu) {
      return <p className="text-muted-foreground">Меню появится в 8:00</p>;
    }
    const winner = menu.recipes.find((r) => r.recipe_id === menu.winner_recipe_id);
    if (menu.status === "collecting") {
      return (
        <p className="text-muted-foreground">
          Сбор предложений — {menu.recipes.length} рецептов в меню
        </p>
      );
    }
    if (menu.status === "voting") {
      return <p className="text-muted-foreground">Голосование открыто</p>;
    }
    return (
      <p className="text-muted-foreground">
        Победил: <span className="font-semibold text-foreground">{winner?.title ?? "—"}</span>
      </p>
    );
  })();

  return (
    <Link to="/vote" className="block h-full">
      <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader>
          <CardTitle>Голосование за ужин</CardTitle>
        </CardHeader>
        <CardContent>{content}</CardContent>
      </Card>
    </Link>
  );
}
