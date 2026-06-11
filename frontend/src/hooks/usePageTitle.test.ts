import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePageTitle } from "./usePageTitle";

describe("usePageTitle", () => {
  it("ставит заголовок с названием сайта", () => {
    renderHook(() => usePageTitle("Рецепты"));

    expect(document.title).toBe("Рецепты | Семейная страница Волковых");
  });

  it("при пустом заголовке оставляет только название сайта", () => {
    renderHook(() => usePageTitle(""));

    expect(document.title).toBe("Семейная страница Волковых");
  });

  it("обновляет заголовок при смене title", () => {
    const { rerender } = renderHook(({ title }) => usePageTitle(title), {
      initialProps: { title: "Вход" },
    });

    rerender({ title: "Профиль" });

    expect(document.title).toBe("Профиль | Семейная страница Волковых");
  });
});
