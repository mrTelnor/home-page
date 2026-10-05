import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SuggestRecipeDialog } from "./SuggestRecipeDialog";
import { createWrapper, makeMenu, makeMenuRecipe, makeRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const menu = makeMenu({
  status: "collecting",
  recipes: [makeMenuRecipe({ recipe_id: "r1", title: "Борщ" })],
});

function renderDialog() {
  const onOpenChange = vi.fn();
  const { Wrapper } = createWrapper();
  render(<SuggestRecipeDialog menu={menu} open onOpenChange={onOpenChange} />, {
    wrapper: Wrapper,
  });
  return { onOpenChange };
}

describe("SuggestRecipeDialog", () => {
  it("показывает только рецепты, которых ещё нет в меню", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({
        body: [makeRecipe({ id: "r1", title: "Борщ" }), makeRecipe({ id: "r2", title: "Пицца" })],
      })
    );
    renderDialog();

    await waitFor(() => expect(screen.getByText("Пицца")).toBeInTheDocument());
    expect(screen.queryByText("Борщ")).not.toBeInTheDocument();
  });

  it("показывает заглушку, если все рецепты уже в меню", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: [makeRecipe({ id: "r1" })] }));
    renderDialog();

    await waitFor(() => expect(screen.getByText("Все рецепты уже в меню")).toBeInTheDocument());
  });

  const titles = () => screen.getAllByText(/^(Айва|Ёжики|Пицца|Яблоки)$/).map((el) => el.textContent);

  const manyRecipes = [
    makeRecipe({ id: "r2", title: "Пицца" }),
    makeRecipe({ id: "r3", title: "Яблоки" }),
    makeRecipe({ id: "r4", title: "Айва" }),
    makeRecipe({ id: "r5", title: "Ёжики" }),
  ];

  it("по умолчанию сортирует по алфавиту, кнопка разворачивает порядок", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: manyRecipes }));
    renderDialog();

    await waitFor(() => expect(screen.getByText("Пицца")).toBeInTheDocument());
    expect(titles()).toEqual(["Айва", "Ёжики", "Пицца", "Яблоки"]);

    await user.click(screen.getByRole("button", { name: "Сортировка: от А до Я" }));

    expect(titles()).toEqual(["Яблоки", "Пицца", "Ёжики", "Айва"]);
    expect(screen.getByRole("button", { name: "Сортировка: от Я до А" })).toBeInTheDocument();
  });

  it("поиск фильтрует по названию без учёта регистра и ё/е", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: manyRecipes }));
    renderDialog();

    await waitFor(() => expect(screen.getByText("Пицца")).toBeInTheDocument());

    const search = screen.getByRole("searchbox", { name: "Поиск рецепта" });
    await user.type(search, "ежи");
    expect(titles()).toEqual(["Ёжики"]);

    await user.clear(search);
    await user.type(search, "ПИЦ");
    expect(titles()).toEqual(["Пицца"]);

    await user.clear(search);
    await user.type(search, "нет такого");
    expect(screen.getByText("Ничего не найдено")).toBeInTheDocument();
  });

  it("клик по рецепту предлагает его и закрывает диалог", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: [makeRecipe({ id: "r2", title: "Пицца" })] }));
    const { onOpenChange } = renderDialog();

    await waitFor(() => expect(screen.getByText("Пицца")).toBeInTheDocument());

    fetchMock.mockResolvedValue(mockResponse({ body: {} }));
    await user.click(screen.getByText("Пицца"));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    const suggestCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/suggest")) as [
      string,
      RequestInit,
    ];
    expect(suggestCall[0]).toContain("/api/menus/menu-1/suggest");
    expect(JSON.parse(suggestCall[1].body as string)).toEqual({ recipe_id: "r2" });
  });
});
