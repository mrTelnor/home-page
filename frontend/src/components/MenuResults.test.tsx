import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MenuResults } from "./MenuResults";
import { makeMenu, makeMenuRecipe } from "@/test/utils";

describe("MenuResults", () => {
  const menu = makeMenu({
    status: "closed",
    winner_recipe_id: "r2",
    recipes: [
      makeMenuRecipe({ id: "mr-1", recipe_id: "r1", title: "Борщ", votes_count: 1 }),
      makeMenuRecipe({
        id: "mr-2",
        recipe_id: "r2",
        title: "Пицца",
        votes_count: 3,
        voters: [{ id: "v1", first_name: "Аня", username: "anya" }],
      }),
    ],
  });

  it("сортирует по голосам и помечает победителя", () => {
    render(
      <MemoryRouter>
        <MenuResults menu={menu} />
      </MemoryRouter>
    );

    expect(screen.getByText("Результаты")).toBeInTheDocument();
    expect(screen.getByText("Победитель")).toBeInTheDocument();

    const links = screen.getAllByRole("link");
    // Пицца (3 голоса) выше Борща (1 голос)
    expect(links[0]).toHaveAttribute("href", "/recipes/r2");
    expect(links[1]).toHaveAttribute("href", "/recipes/r1");
    expect(screen.getByTitle("Аня")).toBeInTheDocument();
  });

  it("не показывает бейдж победителя без победителя", () => {
    render(
      <MemoryRouter>
        <MenuResults menu={makeMenu({ status: "closed", winner_recipe_id: null })} />
      </MemoryRouter>
    );

    expect(screen.queryByText("Победитель")).not.toBeInTheDocument();
  });
});
