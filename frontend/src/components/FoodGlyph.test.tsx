import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FoodGlyph } from "./FoodGlyph";
import { FOOD_COLORS, FOOD_KINDS, pickPaletteByTitle } from "./food-kinds";

describe("FoodGlyph", () => {
  it.each(FOOD_KINDS.map((k) => k.id))("рендерит svg для вида %s", (kind) => {
    const { container } = render(<FoodGlyph title="Тест" kind={kind} color="red" />);

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("g")).toBeInTheDocument();
  });

  it("без kind использует суп по умолчанию", () => {
    const { container } = render(<FoodGlyph title="Что-то" />);

    expect(container.querySelector("svg g")).toBeInTheDocument();
  });

  it("известный цвет берётся из палитры", () => {
    const { container } = render(<FoodGlyph title="Борщ" kind="soup" color="green" />);

    const root = container.firstElementChild as HTMLElement;
    expect(root.style.background).toBe("rgb(216, 224, 188)"); // #D8E0BC
  });

  it("неизвестный цвет — палитра выбирается по названию", () => {
    const { container } = render(<FoodGlyph title="Борщ" kind="soup" color="неон" />);

    const expected = pickPaletteByTitle("Борщ").bg;
    const root = container.firstElementChild as HTMLElement;
    // jsdom нормализует hex в rgb
    const hex = expected.replace("#", "");
    const rgb = `rgb(${parseInt(hex.slice(0, 2), 16)}, ${parseInt(hex.slice(2, 4), 16)}, ${parseInt(hex.slice(4, 6), 16)})`;
    expect(root.style.background).toBe(rgb);
  });

  it("pickPaletteByTitle детерминирована и возвращает палитру из набора", () => {
    const pal = pickPaletteByTitle("Окрошка");

    expect(pal).toEqual(pickPaletteByTitle("Окрошка"));
    expect(Object.values(FOOD_COLORS)).toContainEqual(pal);
  });
});
