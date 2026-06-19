import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { VoteHistoryPage } from "./VoteHistoryPage";
import { createQueryClient, makeMenu, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <VoteHistoryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("рисует помесячные сетки из списка меню", async () => {
  fetchMock.mockResolvedValue(
    mockResponse({
      body: [
        makeMenu({ id: "a", date: "2026-07-03", status: "closed", winner_recipe_id: "recipe-1" }),
        makeMenu({ id: "b", date: "2026-05-20", status: "closed", winner_recipe_id: "recipe-1" }),
      ],
    })
  );
  renderPage();
  await waitFor(() => expect(screen.getByText("Июль 2026")).toBeInTheDocument());
  expect(screen.getByText("Май 2026")).toBeInTheDocument();
  expect(screen.getByTestId("day-2026-07-03")).toBeInTheDocument();
});

it("пустая история", async () => {
  fetchMock.mockResolvedValue(mockResponse({ body: [] }));
  renderPage();
  await waitFor(() => expect(screen.getByText("История пуста")).toBeInTheDocument());
});
