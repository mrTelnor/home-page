import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { WolfMark } from "./WolfMark";

describe("WolfMark", () => {
  it("рендерит svg с размером по умолчанию", () => {
    const { container } = render(<WolfMark />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "28");
    expect(svg).toHaveAttribute("height", "28");
  });

  it("принимает размер, цвет и класс", () => {
    const { container } = render(<WolfMark size={96} color="#000" stroke={2} className="logo" />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "96");
    expect(svg).toHaveClass("logo");
    expect(container.querySelector("g")).toHaveAttribute("stroke", "#000");
  });
});
