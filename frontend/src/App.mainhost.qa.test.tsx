// QA: на основном домене (хост не начинается с «wiki.») сайт рецептов не изменился —
// маршрутов вики нет, к API вики никто не ходит.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { isWikiHost } from "@/lib/wikiHost";
import { useAuthStore } from "@/store/auth";
import { mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

function calledPaths(): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
}

beforeEach(() => {
  fetchMock.mockReset();
  // Гость: любой запрос — 401
  fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("QA App на основном домене", () => {
  it("тестовый хост не считается хостом вики", () => {
    expect(window.location.hostname.startsWith("wiki.")).toBe(false);
    expect(isWikiHost()).toBe(false);
  });

  it.each([
    "/n/moi-domashnii-sait/grabli",
    "/n/a",
    "/b/11111111-2222-3333-4444-555555555555",
    "/search",
    "/search?q=traefik",
  ])("маршрут вики %s — обычная 404 сайта", async (route) => {
    window.history.replaceState(null, "", route);

    render(<App />);

    await waitFor(() => expect(screen.getByText("404")).toBeInTheDocument());
    expect(screen.queryByText("Вход в вики")).not.toBeInTheDocument();
    expect(screen.queryByText("База знаний")).not.toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe(route);
    expect(calledPaths().some((p) => p.startsWith("/api/wiki"))).toBe(false);
    // Мета robots вики на сайте не появляется
    expect(document.head.querySelector('meta[name="robots"][content*="noindex"]')).toBeNull();
  });

  it("/login на основном домене — вход сайта, а не вход в вики", async () => {
    window.history.replaceState(null, "", "/login?next=%2Fn%2Fa");

    render(<App />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Войти" })).toBeInTheDocument());
    expect(screen.queryByText("Вход в вики")).not.toBeInTheDocument();
    expect(screen.queryByText("Вики доступна только администраторам.")).not.toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki"))).toBe(false);
  });

  it("главная и список рецептов открываются как раньше, без запросов к API вики", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText("Семейная страница Волковых")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Смотреть рецепты" })).toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki"))).toBe(false);
  });
});
