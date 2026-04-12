import { useState } from "react";
import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useMenuHistory } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function VoteHistoryPage() {
  usePageTitle("История голосований");
  const { data: menus, isLoading } = useMenuHistory();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">История голосований</h1>
        <Button variant="outline" asChild>
          <Link to="/vote">Сегодня</Link>
        </Button>
      </div>

      {!menus?.length ? (
        <p className="text-muted-foreground text-center py-8">История пуста</p>
      ) : (
        <div className="grid gap-3">
          {menus.map((menu) => {
            const winner = menu.recipes.find((r) => r.recipe_id === menu.winner_recipe_id);
            const isExpanded = expandedId === menu.id;

            return (
              <Card
                key={menu.id}
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => setExpandedId(isExpanded ? null : menu.id)}
              >
                <CardHeader className="py-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{formatDate(menu.date)}</CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge variant={menu.status === "closed" ? "default" : "secondary"}>
                        {menu.status === "closed"
                          ? winner?.title ?? "Нет победителя"
                          : menu.status === "voting"
                            ? "Голосование"
                            : "Сбор"}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                {isExpanded && (
                  <CardContent className="pt-0">
                    <div className="space-y-1">
                      {menu.recipes
                        .sort((a, b) => b.votes_count - a.votes_count)
                        .map((r) => (
                          <div key={r.id} className="flex items-center justify-between text-sm py-1">
                            <span className={r.recipe_id === menu.winner_recipe_id ? "font-bold" : ""}>
                              {r.title}
                            </span>
                            <span className="text-muted-foreground">{r.votes_count} гол.</span>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
