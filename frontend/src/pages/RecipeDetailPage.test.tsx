import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { RecipeDetailPage } from "./RecipeDetailPage";
import { useAuthStore } from "@/store/auth";
import {
  LocationDisplay,
  createQueryClient,
  makeRecipe,
  makeUser,
  mockResponse,
} from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderPage(id = "recipe-1") {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/recipes/${id}`]}>
        <Routes>
          <Route path="/recipes/:id" element={<RecipeDetailPage />} />
          <Route path="/recipes" element={<p>Список рецептов</p>} />
        </Routes>
        <LocationDisplay />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// Количество и единица — отдельные текстовые узлы в одном span, матчим по textContent
function amountSpans(text: string) {
  return screen.queryAllByText((_, el) => el?.tagName === "SPAN" && el.textContent === text);
}

const recipe = makeRecipe({
  description: "Варить час.",
  ingredients: [
    { id: "i1", name: "Свёкла", amount: "2", unit: "шт" },
    { id: "i2", name: "Соль", amount: "по вкусу", unit: null },
  ],
  updated_at: "2026-02-01T00:00:00Z",
});

describe("RecipeDetailPage", () => {
  it("показывает загрузку", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("показывает заглушку, если рецепт не найден", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Рецепт не найден")).toBeInTheDocument());
  });

  it("показывает рецепт: ингредиенты, описание, даты", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Борщ")).toBeInTheDocument());
    expect(screen.getByText("Свёкла")).toBeInTheDocument();
    expect(amountSpans("2 шт")).toHaveLength(1);
    expect(screen.getByText("по вкусу")).toBeInTheDocument();
    expect(screen.getByText("Варить час.")).toBeInTheDocument();
    expect(screen.getByText(/Добавлен:/)).toBeInTheDocument();
    expect(screen.getByText(/Изменён:/)).toBeInTheDocument();
    // гость не видит кнопок редактирования
    expect(screen.queryByText("Редактировать")).not.toBeInTheDocument();
  });

  it("пересчитывает числовые количества при изменении порций", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(amountSpans("2 шт")).toHaveLength(1));

    const input = screen.getByLabelText("Порций:");
    // контролируемый number-инпут: меняем значение одним событием
    fireEvent.change(input, { target: { value: "6" } });

    // 2 * 6/4 = 3
    expect(amountSpans("3 шт")).toHaveLength(1);
    // нечисловое количество не масштабируется
    expect(screen.getByText("по вкусу")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Сбросить" }));
    expect(amountSpans("2 шт")).toHaveLength(1);

    // пустое/нулевое значение откатывает к порциям рецепта
    fireEvent.change(input, { target: { value: "" } });
    expect(amountSpans("2 шт")).toHaveLength(1);
  });

  it("дробный результат выводится с запятой", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(amountSpans("2 шт")).toHaveLength(1));

    fireEvent.change(screen.getByLabelText("Порций:"), { target: { value: "3" } });

    // 2 * 3/4 = 1.5 -> "1,5"
    expect(amountSpans("1,5 шт")).toHaveLength(1);
  });

  it("автор видит кнопки и удаляет рецепт после подтверждения", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    useAuthStore.setState({ user: makeUser({ id: "user-1" }) });
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Редактировать")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Редактировать" })).toHaveAttribute(
      "href",
      "/recipes/recipe-1/edit"
    );

    fetchMock.mockResolvedValue(mockResponse({ status: 204, body: null }));
    await user.click(screen.getByRole("button", { name: "Удалить" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/recipes"));
    const deleteCall = fetchMock.mock.calls.find(
      ([, options]) => (options as RequestInit)?.method === "DELETE"
    );
    expect(deleteCall).toBeDefined();
  });

  it("не удаляет без подтверждения", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    useAuthStore.setState({ user: makeUser({ id: "user-1" }) });
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Удалить")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Удалить" }));

    const deleteCall = fetchMock.mock.calls.find(
      ([, options]) => (options as RequestInit)?.method === "DELETE"
    );
    expect(deleteCall).toBeUndefined();
  });

  it("админ тоже может редактировать чужой рецепт", async () => {
    useAuthStore.setState({ user: makeUser({ id: "other", role: "admin" }) });
    fetchMock.mockResolvedValue(mockResponse({ body: recipe }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Редактировать")).toBeInTheDocument());
  });

  it("показывает заглушку без ингредиентов и без описания", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({ body: makeRecipe({ ingredients: [], description: null }) })
    );
    renderPage();

    await waitFor(() => expect(screen.getByText("Нет ингредиентов")).toBeInTheDocument());
    expect(screen.queryByText("Описание / Как готовить")).not.toBeInTheDocument();
  });
});
