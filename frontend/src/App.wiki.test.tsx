import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { useAuthStore } from "@/store/auth";
import { mockResponse } from "@/test/utils";

// Хост вики: тот же App показывает маршруты вики с корня
vi.mock("@/lib/wikiHost", () => ({
  isWikiHost: () => true,
  mainSiteUrl: () => "https://example.test",
}));

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("App на хосте вики", () => {
  it("с корня открывается вики, а не сайт рецептов: гость попадает на вход в вики", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));

    render(<App />);

    expect(await screen.findByText("Вход в вики")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
    expect(screen.queryByText("Семейная страница Волковых")).not.toBeInTheDocument();
    expect(screen.queryByText("Войти как гость")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "На сайт" })).toHaveAttribute("href", "https://example.test");
  });

  it("маршруты сайта рецептов на хосте вики не существуют", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
    window.history.replaceState(null, "", "/recipes");

    render(<App />);

    // /recipes здесь — неизвестная страница вики: гостя ведёт на вход, списка рецептов нет
    expect(await screen.findByText("Вход в вики")).toBeInTheDocument();
    expect(window.location.search).toBe("?next=%2Frecipes");
  });
});
