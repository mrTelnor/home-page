import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecipeNewPage } from "./RecipeNewPage";
import { createWrapper, makeRecipe, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecipeNewPage", () => {
  it("показывает форму создания и ссылку назад", () => {
    const { Wrapper } = createWrapper({ route: "/recipes/new" });
    render(<RecipeNewPage />, { wrapper: Wrapper });

    expect(screen.getByText("Новый рецепт")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /К списку рецептов/ })).toHaveAttribute(
      "href",
      "/recipes"
    );
    expect(screen.getByRole("button", { name: "Создать рецепт" })).toBeInTheDocument();
  });

  it("сабмит формы создаёт рецепт и ведёт на его страницу", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeRecipe({ id: "recipe-9" }) }));
    const { Wrapper } = createWrapper({ route: "/recipes/new" });
    render(<RecipeNewPage />, { wrapper: Wrapper });

    await user.type(screen.getByPlaceholderText("Введите название блюда"), "Борщ");
    await user.type(screen.getByPlaceholderText("Сколько порций получится"), "4");
    await user.type(screen.getByPlaceholderText("Опишите процесс приготовления..."), "Варить час.");
    // Поля ингредиента: название и количество — внутри карточки строки
    const card = document.querySelector('[data-slot="card"]') as HTMLElement;
    const rowInputs = within(card).getAllByRole("textbox");
    await user.type(rowInputs[0], "Свёкла");
    await user.type(rowInputs[1], "2");

    await user.click(screen.getByRole("button", { name: "Создать рецепт" }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/recipes/recipe-9")
    );
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/recipes");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string).title).toBe("Борщ");
  });
});
