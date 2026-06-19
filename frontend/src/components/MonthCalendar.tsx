import { Link } from "react-router-dom";
import { type Menu } from "@/api/types";
import { monthMatrix, monthName, toDateKey } from "@/lib/calendar";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function statusLabel(menu: Menu): string {
  if (menu.status === "collecting") return "Сбор";
  if (menu.status === "voting") return "Голосование";
  return "Без победителя";
}

interface Props {
  year: number;
  month: number; // 0-11
  byDay: Map<number, Menu>;
}

export function MonthCalendar({ year, month, byDay }: Readonly<Props>) {
  const weeks = monthMatrix(year, month);

  return (
    <section className="space-y-2">
      <h2 className="text-xl font-semibold">
        {monthName(month)} {year}
      </h2>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
        {WEEKDAYS.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {weeks.flat().map((day, i) => {
          if (day === null) return <div key={`e-${i}`} className="aspect-square" />;
          const menu = byDay.get(day);
          if (!menu) {
            return (
              <div
                key={day}
                className="aspect-square rounded-md border border-border/50 p-1 text-xs text-muted-foreground/50"
              >
                {day}
              </div>
            );
          }
          const dateKey = toDateKey(year, month, day);
          const winner = menu.recipes.find((r) => r.recipe_id === menu.winner_recipe_id);
          const contenders = menu.recipes
            .filter((r) => r.recipe_id !== menu.winner_recipe_id)
            .sort((a, b) => a.title.localeCompare(b.title, "ru"));
          return (
            <Link
              key={day}
              to={`/vote/history/${dateKey}`}
              data-testid={`day-${dateKey}`}
              className="aspect-square overflow-hidden rounded-md border border-border bg-card p-1 hover:bg-accent transition-colors flex flex-col"
            >
              <span className="text-xs text-muted-foreground">{day}</span>
              <div className="hidden md:flex md:min-h-0 md:flex-1 md:flex-col md:overflow-hidden">
                {menu.status === "closed" && winner ? (
                  <>
                    <span data-testid="winner" className="truncate text-sm font-bold">
                      {winner.title}
                    </span>
                    <div data-testid="contenders" className="min-h-0 flex-1 overflow-hidden">
                      {contenders.map((c) => (
                        <div key={c.id} className="truncate text-xs text-foreground/70">
                          {c.title}
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <span className="truncate text-xs text-muted-foreground">{statusLabel(menu)}</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
