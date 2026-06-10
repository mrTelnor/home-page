import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("boom");
}

beforeEach(() => {
  // React логирует пойманную ошибку в console.error — глушим шум в тестах
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("рендерит детей, пока ошибок нет", () => {
    render(
      <ErrorBoundary>
        <p>Всё хорошо</p>
      </ErrorBoundary>
    );

    expect(screen.getByText("Всё хорошо")).toBeInTheDocument();
  });

  it("показывает fallback с кнопкой перезагрузки, если ребёнок бросил в render", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText("Что-то пошло не так")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Перезагрузить" })).toBeInTheDocument();
  });
});
