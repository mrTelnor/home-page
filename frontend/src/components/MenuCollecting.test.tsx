import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { MenuCollecting } from "./MenuCollecting";
import { makeMenu, makeMenuRecipe } from "@/test/utils";

function renderCollecting(overrides: Partial<Parameters<typeof MenuCollecting>[0]> = {}) {
  const onSuggest = vi.fn();
  const menu = makeMenu({
    status: "collecting",
    recipes: [
      makeMenuRecipe({ id: "mr-1", recipe_id: "r1", title: "Борщ", source: "random" }),
      makeMenuRecipe({ id: "mr-2", recipe_id: "r2", title: "Пицца", source: "user" }),
    ],
  });
  render(
    <MemoryRouter>
      <MenuCollecting menu={menu} onSuggest={onSuggest} canSuggest {...overrides} />
    </MemoryRouter>
  );
  return { onSuggest };
}

describe("MenuCollecting", () => {
  it("показывает рецепты с бейджами источника и ссылками", () => {
    renderCollecting();

    expect(screen.getByText("Сбор предложений")).toBeInTheDocument();
    expect(screen.getByText("Борщ")).toBeInTheDocument();
    expect(screen.getByText("Случайный")).toBeInTheDocument();
    expect(screen.getByText("Предложен")).toBeInTheDocument();
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/recipes/r1");
  });

  it("кнопка предложения зовёт onSuggest", async () => {
    const user = userEvent.setup();
    const { onSuggest } = renderCollecting();

    await user.click(screen.getByRole("button", { name: "Предложить рецепт" }));

    expect(onSuggest).toHaveBeenCalledTimes(1);
  });

  it("кнопка заблокирована при canSuggest=false", () => {
    renderCollecting({ canSuggest: false });

    expect(screen.getByRole("button", { name: "Предложить рецепт" })).toBeDisabled();
  });
});
