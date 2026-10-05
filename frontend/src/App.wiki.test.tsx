import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { useAuthStore } from "@/store/auth";
import { mockResponse } from "@/test/utils";

// Хост вики: тот же App показывает маршруты вики с корня
vi.mock("@/lib/wikiHost", () => ({
  isWikiHost: () => true,
  mainSiteUrl: () => "https://example.test",
}));

const fetchMock = vi.fn();
const ASYNC = { timeout: 5000 };

/**
 * Попытки ухода со страницы. Переход на вход сайта не подменяем: jsdom навигацию не
 * выполняет, но сообщает о ней событием jsdomError — так видно, что переход настоящий.
 */
let navigationAttempts: string[] = [];

interface JsdomHandle {
  virtualConsole: {
    on(event: "jsdomError", listener: (error: Error) => void): void;
    off(event: "jsdomError", listener: (error: Error) => void): void;
  };
}
// Vitest кладёт экземпляр JSDOM в глобальную переменную jsdom
const dom = (globalThis as unknown as { jsdom: JsdomHandle }).jsdom;
const onJsdomError = (error: Error) => {
  if (/not implemented: navigation/i.test(error.message)) navigationAttempts.push(error.message);
};

/** Страница входа сайта с возвратом на страницу вики (тесты открыты на http://localhost:3000). */
const siteLogin = (path: string) =>
  `https://example.test/login?next=${encodeURIComponent(`http://localhost:3000${path}`)}`;

function calledPaths(): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
}

beforeEach(() => {
  navigationAttempts = [];
  dom.virtualConsole.on("jsdomError", onJsdomError);
  fetchMock.mockReset();
  // Гость: любой запрос — 401
  fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  dom.virtualConsole.off("jsdomError", onJsdomError);
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("App на хосте вики", () => {
  it("с корня открывается вики, а не сайт рецептов: гость уходит на вход основного сайта", async () => {
    render(<App />);

    expect(await screen.findByRole("link", { name: "Войти на сайте" }, ASYNC)).toHaveAttribute(
      "href",
      siteLogin("/")
    );
    await waitFor(() => expect(navigationAttempts).toHaveLength(1), ASYNC);
    // Своей формы входа у вики нет, адрес страницы роутер не меняет
    expect(window.location.pathname).toBe("/");
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
    expect(screen.queryByText("Семейная страница Волковых")).not.toBeInTheDocument();
    expect(screen.queryByText("Войти как гость")).not.toBeInTheDocument();
  });

  it("маршруты сайта рецептов на хосте вики не существуют", async () => {
    window.history.replaceState(null, "", "/recipes");

    render(<App />);

    // /recipes здесь — неизвестная страница вики: гостя ведёт на вход сайта, списка рецептов нет
    expect(await screen.findByRole("link", { name: "Войти на сайте" }, ASYNC)).toHaveAttribute(
      "href",
      siteLogin("/recipes")
    );
    expect(screen.queryByText("Семейная страница Волковых")).not.toBeInTheDocument();
  });

  it.each(["/n/a/b", "/search?q=x&tag=k8s", "/b/11111111-2222-3333-4444-555555555555"])(
    "гость на %s — один явный переход на вход сайта с возвратом на эту страницу",
    async (route) => {
      window.history.replaceState(null, "", route);

      render(<App />);

      expect(await screen.findByRole("link", { name: "Войти на сайте" }, ASYNC)).toHaveAttribute(
        "href",
        siteLogin(route)
      );
      // Переход настоящий (location.replace мимо роутера), и он один
      await waitFor(() => expect(navigationAttempts).toHaveLength(1), ASYNC);
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(navigationAttempts).toHaveLength(1);
      // Роутер вики адрес не трогал, к API вики гость не ходил
      expect(window.location.pathname + window.location.search).toBe(route);
      expect(calledPaths().filter((p) => p.startsWith("/api/wiki/"))).toEqual([]);
    }
  );

  it.each(["/login", "/login?next=%2F%2Fevil.example", "/login?next=https%3A%2F%2Fevil.example"])(
    "старый адрес %s — возврат на корень вики, чужой next не подхватывается",
    async (route) => {
      window.history.replaceState(null, "", route);

      render(<App />);

      const link = await screen.findByRole("link", { name: "Войти на сайте" }, ASYNC);
      expect(link).toHaveAttribute("href", siteLogin("/"));
      expect(link.getAttribute("href")).not.toContain("evil");
      await waitFor(() => expect(navigationAttempts).toHaveLength(1), ASYNC);
    }
  );
});
