import { type Menu } from "@/api/types";

const MONTH_NAMES = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];

export function monthName(month: number): string {
  return MONTH_NAMES[month];
}

export function toDateKey(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** Недели по 7 ячеек, понедельник первый. Пустые клетки = null. month 0-11. */
export function monthMatrix(year: number, month: number): (number | null)[][] {
  const lead = (new Date(year, month, 1).getDay() + 6) % 7; // Mon-first offset
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

export interface MonthGroup {
  year: number;
  month: number; // 0-11
  byDay: Map<number, Menu>;
}

export function groupMenusByMonth(menus: Menu[]): MonthGroup[] {
  const map = new Map<string, MonthGroup>();
  for (const m of menus) {
    const [y, mo, d] = m.date.split("-").map(Number);
    const key = `${y}-${mo}`;
    let g = map.get(key);
    if (!g) {
      g = { year: y, month: mo - 1, byDay: new Map() };
      map.set(key, g);
    }
    g.byDay.set(d, m);
  }
  return [...map.values()].sort((a, b) => b.year - a.year || b.month - a.month);
}
