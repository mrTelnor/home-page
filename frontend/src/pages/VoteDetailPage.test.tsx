import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { VoteDetailPage } from "./VoteDetailPage";
import { createQueryClient, makeMenu, makeMenuRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(route: string) {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/vote/history/:date" element={<VoteDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("победитель первым, имена — ссылки на рецепты, голоса показаны", async () => {
  fetchMock.mockResolvedValue(
    mockResponse({
      body: [
        makeMenu({
          id: "m",
          date: "2026-07-05",
          status: "closed",
          winner_recipe_id: "r-win",
          recipes: [
            makeMenuRecipe({ id: "1", recipe_id: "r-b", title: "Борщ", votes_count: 1 }),
            makeMenuRecipe({ id: "2", recipe_id: "r-win", title: "Плов", votes_count: 3 }),
          ],
        }),
      ],
    })
  );
  renderAt("/vote/history/2026-07-05");

  const winnerLink = await screen.findByRole("link", { name: "Плов" });
  expect(winnerLink.getAttribute("href")).toBe("/recipes/r-win");
  const rows = screen.getAllByTestId("vote-row");
  expect(within(rows[0]).getByText("Плов")).toBeInTheDocument(); // победитель сверху
  expect(within(rows[0]).getByText(/3/)).toBeInTheDocument();
});

it("победитель первым, остальные по алфавиту названия", async () => {
  fetchMock.mockResolvedValue(
    mockResponse({
      body: [
        makeMenu({
          id: "m0",
          date: "2026-06-19",
          status: "closed",
          winner_recipe_id: "r-win",
          recipes: [
            makeMenuRecipe({ id: "1", recipe_id: "r-a", title: "Шампиньоны", votes_count: 0 }),
            makeMenuRecipe({ id: "2", recipe_id: "r-win", title: "Запеканка", votes_count: 0 }),
            makeMenuRecipe({ id: "3", recipe_id: "r-c", title: "Котлетки", votes_count: 0 }),
          ],
        }),
      ],
    })
  );
  renderAt("/vote/history/2026-06-19");

  await screen.findByText("Запеканка");
  const rows = screen.getAllByTestId("vote-row");
  expect(within(rows[0]).getByText("Запеканка")).toBeInTheDocument(); // победитель
  expect(within(rows[1]).getByText("Котлетки")).toBeInTheDocument(); // далее алфавит
  expect(within(rows[2]).getByText("Шампиньоны")).toBeInTheDocument();
});

it("несуществующая дата — не найдено", async () => {
  fetchMock.mockResolvedValue(mockResponse({ body: [] }));
  renderAt("/vote/history/2099-01-01");
  await waitFor(() => expect(screen.getByText("Голосование не найдено")).toBeInTheDocument());
});
