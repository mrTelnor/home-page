import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoteHistoryPage } from "./VoteHistoryPage";
import { createWrapper, makeMenu, makeMenuRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const { Wrapper } = createWrapper({ route: "/vote/history" });
  return render(<VoteHistoryPage />, { wrapper: Wrapper });
}

describe("VoteHistoryPage", () => {
  it("показывает загрузку", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("показывает заглушку при пустой истории", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: [] }));
    renderPage();

    await waitFor(() => expect(screen.getByText("История пуста")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Сегодня" })).toHaveAttribute("href", "/vote");
  });

  it("показывает бейджи по статусам: победитель, голосование, сбор", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({
        body: [
          makeMenu({
            id: "m1",
            date: "2026-06-10",
            status: "closed",
            winner_recipe_id: "recipe-1",
            recipes: [makeMenuRecipe({ recipe_id: "recipe-1", title: "Борщ" })],
          }),
          makeMenu({ id: "m2", date: "2026-06-09", status: "voting" }),
          makeMenu({ id: "m3", date: "2026-06-08", status: "collecting" }),
          makeMenu({ id: "m4", date: "2026-06-07", status: "closed", winner_recipe_id: null }),
        ],
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(screen.getByText("Голосование")).toBeInTheDocument();
    expect(screen.getByText("Сбор")).toBeInTheDocument();
    expect(screen.getByText("Нет победителя")).toBeInTheDocument();
    expect(screen.getByText("10 июня 2026 г.")).toBeInTheDocument();
  });

  it("клик раскрывает меню с рецептами по убыванию голосов, повторный — сворачивает", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({
        body: [
          makeMenu({
            id: "m1",
            status: "closed",
            winner_recipe_id: "r2",
            recipes: [
              makeMenuRecipe({ id: "mr-1", recipe_id: "r1", title: "Борщ", votes_count: 1 }),
              makeMenuRecipe({ id: "mr-2", recipe_id: "r2", title: "Пицца", votes_count: 3 }),
            ],
          }),
        ],
      })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Пицца")).toBeInTheDocument());
    expect(screen.queryByText("3 гол.")).not.toBeInTheDocument();

    await user.click(screen.getAllByText("Пицца")[0]);

    expect(screen.getByText("3 гол.")).toBeInTheDocument();
    expect(screen.getByText("1 гол.")).toBeInTheDocument();
    expect(screen.getByText("Борщ")).toBeInTheDocument();

    await user.click(screen.getAllByText("Пицца")[0]);

    expect(screen.queryByText("3 гол.")).not.toBeInTheDocument();
  });
});
