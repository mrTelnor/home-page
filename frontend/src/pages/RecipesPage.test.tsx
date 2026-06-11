import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecipesPage } from "./RecipesPage";
import { useAuthStore } from "@/store/auth";
import { createWrapper, makeRecipe, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const recipes = [
  makeRecipe({
    id: "r1",
    title: "Борщ",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-05T00:00:00Z",
    description: "Классический",
  }),
  makeRecipe({
    id: "r2",
    title: "Азу",
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
    description: null,
  }),
];

function renderPage() {
  const { Wrapper } = createWrapper({ route: "/recipes" });
  return render(<RecipesPage />, { wrapper: Wrapper });
}

function cardTitles() {
  return screen.getAllByRole("link").flatMap((link) => {
    const heading = within(link).queryByText(/Борщ|Азу/);
    return heading ? [heading.textContent] : [];
  });
}

describe("RecipesPage", () => {
  it("показывает загрузку", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("показывает заглушку, если рецептов нет", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: [] }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Рецептов пока нет")).toBeInTheDocument());
  });

  it("гость не видит кнопку добавления, пользователь видит", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Добавить рецепт" })).not.toBeInTheDocument();

    useAuthStore.setState({ user: makeUser() });
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Добавить рецепт" })).toBeInTheDocument()
    );
  });

  it("по умолчанию сортирует по алфавиту по возрастанию", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(cardTitles()).toEqual(["Азу", "Борщ"]);
    // счётчики порций и ингредиентов (текст разбит на узлы — матчим по textContent)
    expect(
      screen.getAllByText((_, el) => el?.tagName === "SPAN" && el.textContent === "1 ингр.")
    ).toHaveLength(2);
  });

  it("переключение направления сортировки переворачивает порядок и сохраняется", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "↑ По возрастанию" }));

    expect(cardTitles()).toEqual(["Борщ", "Азу"]);
    expect(screen.getByRole("button", { name: "↓ По убыванию" })).toBeInTheDocument();
    expect(localStorage.getItem("recipes:sortDir")).toBe("desc");
  });

  it("сортировка по дате добавления", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Сортировка:"), "created_at");

    // Борщ создан раньше Азу
    expect(cardTitles()).toEqual(["Борщ", "Азу"]);
    expect(localStorage.getItem("recipes:sortField")).toBe("created_at");
  });

  it("показывает дату изменения, только если она отличается", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    // у Борща updated_at != created_at
    expect(screen.getByText(/Изменён:/)).toBeInTheDocument();
    expect(screen.getAllByText(/Изменён:/)).toHaveLength(1);
    expect(screen.getByText("Классический")).toBeInTheDocument();
  });

  it("читает сохранённую сортировку из localStorage", async () => {
    localStorage.setItem("recipes:sortField", "updated_at");
    localStorage.setItem("recipes:sortDir", "desc");
    fetchMock.mockResolvedValue(mockResponse({ body: recipes }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(screen.getByLabelText("Сортировка:")).toHaveValue("updated_at");
    // Борщ изменён позже — при desc он первый
    expect(cardTitles()).toEqual(["Борщ", "Азу"]);
  });
});
