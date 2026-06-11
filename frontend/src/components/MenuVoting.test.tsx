import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { MenuVoting } from "./MenuVoting";
import { makeMenu, makeMenuRecipe } from "@/test/utils";

const recipes = [
  makeMenuRecipe({ id: "mr-1", recipe_id: "r1", title: "Борщ", votes_count: 2 }),
  makeMenuRecipe({
    id: "mr-2",
    recipe_id: "r2",
    title: "Пицца",
    votes_count: 1,
    voters: [{ id: "v1", first_name: "Аня", username: "anya" }],
  }),
];

function renderVoting(overrides: Partial<Parameters<typeof MenuVoting>[0]> = {}) {
  const onVote = vi.fn();
  const onCancelVote = vi.fn();
  const menu = makeMenu({ status: "voting", recipes, total_votes: 3 });
  render(
    <MemoryRouter>
      <MenuVoting
        menu={menu}
        onVote={onVote}
        onCancelVote={onCancelVote}
        isPending={false}
        {...overrides}
      />
    </MemoryRouter>
  );
  return { onVote, onCancelVote };
}

describe("MenuVoting", () => {
  it("пока не голосовал — у каждого рецепта кнопка 'Голосовать'", async () => {
    const user = userEvent.setup();
    const { onVote } = renderVoting();

    expect(screen.getByText(/не проголосовали/)).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Голосовать" });
    expect(buttons).toHaveLength(2);

    await user.click(buttons[0]);
    expect(onVote).toHaveBeenCalledWith("r1");
  });

  it("после голоса — кнопка отмены только у выбранного рецепта", async () => {
    const user = userEvent.setup();
    const menu = makeMenu({
      status: "voting",
      recipes,
      total_votes: 3,
      user_voted_recipe_id: "r1",
    });
    const { onCancelVote } = renderVoting({ menu });

    expect(screen.getByText(/вы проголосовали/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Голосовать" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отменить голос" }));
    expect(onCancelVote).toHaveBeenCalledTimes(1);
  });

  it("показывает счётчики голосов и аватарки голосовавших", () => {
    renderVoting();

    expect(screen.getByText("2 гол.")).toBeInTheDocument();
    expect(screen.getByText("1 гол.")).toBeInTheDocument();
    expect(screen.getByTitle("Аня")).toBeInTheDocument();
  });

  it("блокирует кнопки при isPending", () => {
    renderVoting({ isPending: true });

    for (const btn of screen.getAllByRole("button", { name: "Голосовать" })) {
      expect(btn).toBeDisabled();
    }
  });
});
