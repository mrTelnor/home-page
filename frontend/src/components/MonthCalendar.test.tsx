import { expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MonthCalendar } from "./MonthCalendar";
import { type Menu } from "@/api/types";
import { makeMenu, makeMenuRecipe } from "@/test/utils";

function renderCal(byDay: Map<number, Menu>) {
  render(
    <MemoryRouter>
      <MonthCalendar year={2026} month={6} byDay={byDay} />
    </MemoryRouter>
  );
}

it("заголовок месяца и шапка недели", () => {
  renderCal(new Map());
  expect(screen.getByText("Июль 2026")).toBeInTheDocument();
  expect(screen.getByText("Пн")).toBeInTheDocument();
  expect(screen.getByText("Вс")).toBeInTheDocument();
});

it("активная дата — ссылка на детали, с победителем и претендентами (алфавит, без победителя)", () => {
  const menu = makeMenu({
    id: "m",
    date: "2026-07-05",
    status: "closed",
    winner_recipe_id: "r-win",
    recipes: [
      makeMenuRecipe({ id: "1", recipe_id: "r-win", title: "Плов" }),
      makeMenuRecipe({ id: "2", recipe_id: "r-b", title: "Борщ" }),
      makeMenuRecipe({ id: "3", recipe_id: "r-a", title: "Азу" }),
    ],
  });
  renderCal(new Map([[5, menu]]));

  const cell = screen.getByTestId("day-2026-07-05");
  expect(cell.getAttribute("href")).toBe("/vote/history/2026-07-05");
  expect(within(cell).getByTestId("winner").textContent).toBe("Плов");
  const contenders = within(cell).getByTestId("contenders").textContent ?? "";
  expect(contenders.indexOf("Азу")).toBeGreaterThanOrEqual(0);
  expect(contenders.indexOf("Азу")).toBeLessThan(contenders.indexOf("Борщ")); // алфавит
  expect(contenders).not.toContain("Плов"); // победитель не в претендентах
});

it("день без меню — не ссылка", () => {
  renderCal(new Map());
  expect(screen.queryByTestId("day-2026-07-10")).not.toBeInTheDocument();
  expect(screen.getAllByText("10").length).toBeGreaterThan(0);
});

it("незакрытый день показывает ярлык статуса вместо победителя", () => {
  const menu = makeMenu({ id: "m2", date: "2026-07-07", status: "voting", winner_recipe_id: null });
  renderCal(new Map([[7, menu]]));
  const cell = screen.getByTestId("day-2026-07-07");
  expect(within(cell).getByText("Голосование")).toBeInTheDocument();
});
