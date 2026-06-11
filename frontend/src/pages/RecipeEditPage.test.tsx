import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { RecipeEditPage } from "./RecipeEditPage";
import { LocationDisplay, createQueryClient, makeRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={["/recipes/recipe-1/edit"]}>
        <Routes>
          <Route path="/recipes/:id/edit" element={<RecipeEditPage />} />
        </Routes>
        <LocationDisplay />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RecipeEditPage", () => {
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

  it("заполняет форму данными рецепта", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeRecipe() }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Редактирование рецепта")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Борщ")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Варить час.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Свёкла")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /К рецепту/ })).toHaveAttribute(
      "href",
      "/recipes/recipe-1"
    );
  });

  it("сабмит шлёт PUT и ведёт на страницу рецепта", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeRecipe() }));
    renderPage();

    await waitFor(() => expect(screen.getByDisplayValue("Борщ")).toBeInTheDocument());

    const title = screen.getByDisplayValue("Борщ");
    await user.clear(title);
    await user.type(title, "Борщ московский");
    await user.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/recipes/recipe-1")
    );
    const putCall = fetchMock.mock.calls.find(
      ([, options]) => (options as RequestInit)?.method === "PUT"
    ) as [string, RequestInit];
    expect(putCall[0]).toContain("/api/recipes/recipe-1");
    expect(JSON.parse(putCall[1].body as string).title).toBe("Борщ московский");
  });
});
