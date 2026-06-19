import { describe, expect, it } from "vitest";
import { groupMenusByMonth, monthMatrix, toDateKey } from "./calendar";
import { makeMenu } from "@/test/utils";

describe("monthMatrix", () => {
  it("Июль 2026 начинается со среды — 2 ведущие пустые клетки", () => {
    const weeks = monthMatrix(2026, 6); // month 6 = июль (0-based)
    expect(weeks[0]).toEqual([null, null, 1, 2, 3, 4, 5]);
    expect(weeks.every((w) => w.length === 7)).toBe(true);
    expect(weeks.flat().filter((d) => d !== null)).toHaveLength(31);
    expect(weeks.flat()).toContain(31);
  });

  it("каждая неделя длиной 7, хвост добит null", () => {
    const weeks = monthMatrix(2026, 1); // февраль 2026 (28 дней)
    expect(weeks.flat().filter((d) => d !== null)).toHaveLength(28);
    expect(weeks.every((w) => w.length === 7)).toBe(true);
  });
});

describe("toDateKey", () => {
  it("форматирует с ведущими нулями, без UTC-сдвига", () => {
    expect(toDateKey(2026, 6, 5)).toBe("2026-07-05");
    expect(toDateKey(2026, 11, 31)).toBe("2026-12-31");
  });
});

describe("groupMenusByMonth", () => {
  it("группирует по месяцам, только с данными, новые сверху", () => {
    const menus = [
      makeMenu({ id: "a", date: "2026-05-20" }),
      makeMenu({ id: "b", date: "2026-07-03" }),
      makeMenu({ id: "c", date: "2026-07-15" }),
    ];
    const groups = groupMenusByMonth(menus);
    expect(groups.map((g) => [g.year, g.month])).toEqual([
      [2026, 6], // июль сверху
      [2026, 4], // май
    ]);
    expect(groups[0].byDay.get(3)?.id).toBe("b");
    expect(groups[0].byDay.get(15)?.id).toBe("c");
    expect(groups[1].byDay.get(20)?.id).toBe("a");
  });
});
