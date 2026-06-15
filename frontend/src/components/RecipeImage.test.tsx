import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecipeImage } from "./RecipeImage";

describe("RecipeImage", () => {
  it("рендерит img при наличии imageUrl", () => {
    render(<RecipeImage title="Борщ" imageUrl="/api/recipe-images/x.jpg" />);
    const img = screen.getByAltText("Борщ") as HTMLImageElement;
    expect(img.tagName).toBe("IMG");
  });

  it("откатывается на глиф при ошибке загрузки", () => {
    render(<RecipeImage title="Борщ" imageUrl="/api/recipe-images/x.jpg" />);
    fireEvent.error(screen.getByAltText("Борщ"));
    expect(screen.queryByAltText("Борщ")).toBeNull();
    expect(document.querySelector("svg")).not.toBeNull();
  });

  it("сразу рендерит глиф без imageUrl", () => {
    render(<RecipeImage title="Борщ" />);
    expect(screen.queryByAltText("Борщ")).toBeNull();
    expect(document.querySelector("svg")).not.toBeNull();
  });

  it("абсолютный URL не префиксуется API_URL", () => {
    render(<RecipeImage title="Борщ" imageUrl="https://cdn.example.com/x.jpg" />);
    const img = screen.getByAltText("Борщ") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("https://cdn.example.com/x.jpg");
  });
});
