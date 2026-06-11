import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { VoteWidget } from "./VoteWidget";
import { createWrapper, makeMenu, makeMenuRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderWidget() {
  const { Wrapper } = createWrapper();
  return render(<VoteWidget />, { wrapper: Wrapper });
}

describe("VoteWidget", () => {
  it("показывает загрузку, пока данные не пришли", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderWidget();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("показывает заглушку, если меню ещё нет", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderWidget();

    await waitFor(() => expect(screen.getByText("Меню появится в 8:00")).toBeInTheDocument());
  });

  it("в статусе collecting показывает число рецептов", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({
        body: makeMenu({
          status: "collecting",
          recipes: [makeMenuRecipe(), makeMenuRecipe({ id: "mr-2" })],
        }),
      })
    );
    renderWidget();

    await waitFor(() =>
      expect(screen.getByText(/Сбор предложений — 2 рецептов в меню/)).toBeInTheDocument()
    );
  });

  it("в статусе voting показывает, что голосование открыто", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeMenu({ status: "voting" }) }));
    renderWidget();

    await waitFor(() => expect(screen.getByText("Голосование открыто")).toBeInTheDocument());
  });

  it("в статусе closed показывает победителя", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({
        body: makeMenu({
          status: "closed",
          winner_recipe_id: "recipe-1",
          recipes: [makeMenuRecipe({ recipe_id: "recipe-1", title: "Борщ" })],
        }),
      })
    );
    renderWidget();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(screen.getByText(/Победил:/)).toBeInTheDocument();
  });

  it("в статусе closed без победителя показывает прочерк", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({ body: makeMenu({ status: "closed", winner_recipe_id: null }) })
    );
    renderWidget();

    await waitFor(() => expect(screen.getByText("—")).toBeInTheDocument());
  });

  it("весь виджет — ссылка на /vote", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderWidget();

    await waitFor(() => expect(screen.getByRole("link")).toHaveAttribute("href", "/vote"));
  });
});
