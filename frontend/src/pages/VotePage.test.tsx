import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VotePage } from "./VotePage";
import { useAuthStore } from "@/store/auth";
import { createWrapper, makeMenu, makeMenuRecipe, makeUser, mockResponse } from "@/test/utils";
import { type Menu } from "@/api/types";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: makeUser() });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const { Wrapper } = createWrapper({ route: "/vote" });
  return render(<VotePage />, { wrapper: Wrapper });
}

function mockMenu(menu: Menu | null) {
  fetchMock.mockImplementation((url: string) => {
    if (String(url).includes("/api/menus/today")) {
      return Promise.resolve(
        menu ? mockResponse({ body: menu }) : mockResponse({ ok: false, status: 404, body: {} })
      );
    }
    if (String(url).includes("/api/recipes")) {
      return Promise.resolve(mockResponse({ body: [] }));
    }
    return Promise.resolve(mockResponse({ body: {} }));
  });
}

describe("VotePage", () => {
  it("показывает загрузку", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("показывает заглушку, если меню нет", async () => {
    mockMenu(null);
    renderPage();

    await waitFor(() => expect(screen.getByText("Меню появится в 8:00")).toBeInTheDocument());
  });

  it("в статусе collecting показывает сбор и открывает диалог предложения", async () => {
    const user = userEvent.setup();
    mockMenu(makeMenu({ status: "collecting" }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Сбор предложений")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "История" })).toHaveAttribute("href", "/vote/history");

    await user.click(screen.getByRole("button", { name: "Предложить рецепт" }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });

  it("кнопка предложения заблокирована, если пользователь уже предложил рецепт", async () => {
    mockMenu(
      makeMenu({
        status: "collecting",
        recipes: [makeMenuRecipe({ source: "user", added_by: "user-1" })],
      })
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Предложить рецепт" })).toBeDisabled()
    );
  });

  it("админ может предложить до трёх рецептов", async () => {
    useAuthStore.setState({ user: makeUser({ id: "admin-1", role: "admin" }) });
    mockMenu(
      makeMenu({
        status: "collecting",
        recipes: [
          makeMenuRecipe({ id: "m1", source: "user", added_by: "admin-1" }),
          makeMenuRecipe({ id: "m2", source: "user", added_by: "admin-1" }),
        ],
      })
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Предложить рецепт" })).toBeEnabled()
    );
  });

  it("админ с тремя предложениями больше предлагать не может", async () => {
    useAuthStore.setState({ user: makeUser({ id: "admin-1", role: "admin" }) });
    mockMenu(
      makeMenu({
        status: "collecting",
        recipes: [
          makeMenuRecipe({ id: "m1", source: "user", added_by: "admin-1" }),
          makeMenuRecipe({ id: "m2", source: "user", added_by: "admin-1" }),
          makeMenuRecipe({ id: "m3", source: "user", added_by: "admin-1" }),
        ],
      })
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Предложить рецепт" })).toBeDisabled()
    );
  });

  it("в статусе voting голос уходит на сервер", async () => {
    const user = userEvent.setup();
    mockMenu(makeMenu({ status: "voting", recipes: [makeMenuRecipe({ recipe_id: "r1" })] }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Голосование за ужин")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Голосовать" }));

    await waitFor(() => {
      const voteCall = fetchMock.mock.calls.find(
        ([url, options]) =>
          String(url).includes("/vote") && (options as RequestInit)?.method === "POST"
      );
      expect(voteCall).toBeDefined();
    });
  });

  it("в статусе voting можно отменить свой голос", async () => {
    const user = userEvent.setup();
    mockMenu(
      makeMenu({
        status: "voting",
        user_voted_recipe_id: "recipe-1",
        recipes: [makeMenuRecipe({ recipe_id: "recipe-1" })],
      })
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Отменить голос" })).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: "Отменить голос" }));

    await waitFor(() => {
      const cancelCall = fetchMock.mock.calls.find(
        ([url, options]) =>
          String(url).includes("/vote") && (options as RequestInit)?.method === "DELETE"
      );
      expect(cancelCall).toBeDefined();
    });
  });

  it("в статусе closed показывает результаты", async () => {
    mockMenu(makeMenu({ status: "closed", winner_recipe_id: "recipe-1" }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Результаты")).toBeInTheDocument());
    expect(screen.getByText("Победитель")).toBeInTheDocument();
  });
});
