import { Link, useParams } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useMenuByDate } from "@/hooks/useMenu";
import { Badge } from "@/components/ui/badge";

function formatDateLong(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function VoteDetailPage() {
  const { date } = useParams<{ date: string }>();
  const { menu, isLoading } = useMenuByDate(date);
  usePageTitle("Голосование");

  const back = (
    <Link
      to="/vote/history"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      ← К истории
    </Link>
  );

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }
  if (!menu) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        {back}
        <p className="text-muted-foreground text-center py-8">Голосование не найдено</p>
      </div>
    );
  }

  // Победитель всегда первым, остальные — по алфавиту названия.
  const sorted = [...menu.recipes].sort((a, b) => {
    const aWin = a.recipe_id === menu.winner_recipe_id ? 1 : 0;
    const bWin = b.recipe_id === menu.winner_recipe_id ? 1 : 0;
    if (aWin !== bWin) return bWin - aWin;
    return a.title.localeCompare(b.title, "ru");
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {back}
      <h1 className="text-3xl font-bold">{formatDateLong(menu.date)}</h1>
      <div className="grid gap-2">
        {sorted.map((r) => {
          const isWinner = r.recipe_id === menu.winner_recipe_id;
          return (
            <div
              key={r.id}
              data-testid="vote-row"
              className="flex items-center justify-between rounded-md border border-border px-3 py-2"
            >
              <span className="flex items-center gap-2">
                <Link
                  to={`/recipes/${r.recipe_id}`}
                  className={`hover:underline ${isWinner ? "font-bold" : ""}`}
                >
                  {r.title}
                </Link>
                {isWinner && <Badge>Победитель</Badge>}
              </span>
              <span className="text-muted-foreground">{r.votes_count} гол.</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
