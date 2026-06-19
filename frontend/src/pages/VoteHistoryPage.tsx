import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useMenuHistory } from "@/hooks/useMenu";
import { Button } from "@/components/ui/button";
import { MonthCalendar } from "@/components/MonthCalendar";
import { groupMenusByMonth } from "@/lib/calendar";

export function VoteHistoryPage() {
  usePageTitle("История голосований");
  const { data: menus, isLoading } = useMenuHistory();

  if (isLoading) {
    return <p className="text-muted-foreground text-center py-8">Загрузка...</p>;
  }

  const groups = groupMenusByMonth(menus ?? []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">История голосований</h1>
        <Button variant="outline" asChild>
          <Link to="/vote">Сегодня</Link>
        </Button>
      </div>

      {groups.length ? (
        groups.map((g) => (
          <MonthCalendar
            key={`${g.year}-${g.month}`}
            year={g.year}
            month={g.month}
            byDay={g.byDay}
          />
        ))
      ) : (
        <p className="text-muted-foreground text-center py-8">История пуста</p>
      )}
    </div>
  );
}
