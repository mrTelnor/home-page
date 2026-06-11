import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GlyphPicker } from "./GlyphPicker";
import { FOOD_COLORS } from "./food-kinds";

function renderPicker(overrides: Partial<Parameters<typeof GlyphPicker>[0]> = {}) {
  const onKindChange = vi.fn();
  const onColorChange = vi.fn();
  render(
    <GlyphPicker
      title="Борщ"
      kind=""
      color=""
      onKindChange={onKindChange}
      onColorChange={onColorChange}
      {...overrides}
    />
  );
  return { onKindChange, onColorChange };
}

describe("GlyphPicker", () => {
  it("показывает селект типов с авто-вариантом", () => {
    renderPicker();

    const select = screen.getByLabelText("Тип");
    expect(select).toHaveValue("");
    expect(screen.getByRole("option", { name: "— Авто (по названию) —" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Суп" })).toBeInTheDocument();
  });

  it("выбор типа зовёт onKindChange", async () => {
    const user = userEvent.setup();
    const { onKindChange } = renderPicker();

    await user.selectOptions(screen.getByLabelText("Тип"), "pizza");

    expect(onKindChange).toHaveBeenCalledWith("pizza");
  });

  it("клик по цвету зовёт onColorChange", async () => {
    const user = userEvent.setup();
    const { onColorChange } = renderPicker();

    await user.click(screen.getByRole("button", { name: "red" }));

    expect(onColorChange).toHaveBeenCalledWith("red");
  });

  it("кнопка авто-цвета сбрасывает цвет в пустую строку", async () => {
    const user = userEvent.setup();
    const { onColorChange } = renderPicker({ color: "red" });

    await user.click(screen.getByRole("button", { name: "Авто-цвет" }));

    expect(onColorChange).toHaveBeenCalledWith("");
  });

  it("подсвечивает выбранный цвет рамкой", () => {
    renderPicker({ color: "green", kind: "soup" });

    expect(screen.getByRole("button", { name: "green" })).toHaveClass("border-foreground");
    expect(screen.getByRole("button", { name: "red" })).toHaveClass("border-transparent");
    // все цвета палитры отрисованы
    for (const c of Object.keys(FOOD_COLORS)) {
      expect(screen.getByRole("button", { name: c })).toBeInTheDocument();
    }
  });
});
