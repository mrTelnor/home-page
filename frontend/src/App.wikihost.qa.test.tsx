// QA: на хосте вики (под админом) маршрутов сайта рецептов нет, а `next` на странице
// входа не уводит на чужой адрес. Рендерим настоящий App с BrowserRouter: открытый
// редирект в React Router проявляется только с настоящей историей браузера.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { useAuthStore } from "@/store/auth";
import { makeUser, mockResponse } from "@/test/utils";

vi.mock("@/lib/wikiHost", () => ({
  isWikiHost: () => true,
  mainSiteUrl: () => "https://example.test",
}));

const fetchMock = vi.fn();
const ASYNC = { timeout: 5000 };

/** Попытки ухода со страницы: jsdom не умеет навигацию и сообщает о ней событием jsdomError. */
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

function calledPaths(): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
}

beforeEach(() => {
  navigationAttempts = [];
  dom.virtualConsole.on("jsdomError", onJsdomError);
  // ErrorBoundary пишет пойманную ошибку в console.error — в выводе тестов она не нужна
  vi.spyOn(console, "error").mockImplementation(() => {});
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const path = new URL(url).pathname;
    if (path === "/api/auth/me") {
      return Promise.resolve(
        mockResponse({ body: makeUser({ role: "admin", username: "nikita" }) })
      );
    }
    if (path === "/api/wiki/notebooks" || path === "/api/wiki/recent") {
      return Promise.resolve(mockResponse({ body: [] }));
    }
    return Promise.resolve(mockResponse({ ok: false, status: 404, body: { detail: "Not found" } }));
  });
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  dom.virtualConsole.off("jsdomError", onJsdomError);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("QA контроль: тест умеет заметить уход на чужой адрес", () => {
  it("jsdom сообщает о попытке внешнего перехода", () => {
    window.location.assign("https://evil.example/");
    expect(navigationAttempts).toHaveLength(1);
  });

  it("pushState на чужой origin бросает ошибку — на это и опирается запасной переход роутера", () => {
    expect(() => window.history.pushState(null, "", "//evil.example")).toThrow();
    expect(() => window.history.pushState(null, "", "/\\evil.example")).toThrow();
    expect(() => window.history.pushState(null, "", "/\t/evil.example")).toThrow();
  });
});

describe("QA App на хосте вики: маршрутов сайта рецептов нет", () => {
  it.each([
    "/recipes",
    "/recipes/new",
    "/vote",
    "/profile",
    "/admin/users",
    "/register",
    "/forgot-password",
  ])("%s — «Страница не найдена» вики", async (route) => {
    window.history.replaceState(null, "", route);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Страница не найдена" }, ASYNC)
    ).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Поиск по заметкам" })).toBeInTheDocument();
    expect(screen.queryByText("Семейная страница Волковых")).not.toBeInTheDocument();
    // Данные сайта рецептов не запрашиваются
    const foreign = calledPaths().filter(
      (p) => !p.startsWith("/api/wiki/") && p !== "/api/auth/me"
    );
    expect(foreign).toEqual([]);
  });

  it("корень — обзор вики, а не главная сайта", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "База знаний" }, ASYNC)).toBeInTheDocument();
    expect(screen.queryByText("Семейная страница Волковых")).not.toBeInTheDocument();
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, nofollow"
    );
  });
});

describe("QA App на хосте вики: next на странице входа не уводит наружу", () => {
  // Админ уже вошёл: страница входа сразу уходит по next — самый короткий путь к редиректу
  it.each([
    "//evil.example",
    "//evil.example/n/a",
    "///evil.example",
    "https://evil.example",
    "https:evil.example",
    "HTTPS://evil.example/x",
    "/\\evil.example",
    "/\\/evil.example",
    "\\\\evil.example",
    "\\/evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
    "/\t\\evil.example",
    "\t//evil.example",
    " //evil.example",
    "/.//evil.example",
    "/..//evil.example",
    "/a/..//evil.example",
    "javascript:alert(1)",
    "data:text/html,x",
    "evil.example",
    "@evil.example",
    "/login?next=//evil.example",
    "/%2F/evil.example",
  ])("next=%j", async (next) => {
    window.history.replaceState(null, "", `/login?next=${encodeURIComponent(next)}`);

    render(<App />);

    // Приложение либо осталось в вики (шапка с поиском), либо показало экран ошибки.
    // Экран ошибки на управляющих символах в next — дефект, он описан отдельным тестом
    // в wiki-defects.qa.test.tsx; здесь проверяется только отсутствие ухода наружу.
    await waitFor(
      () =>
        expect(
          screen.queryByRole("searchbox", { name: "Поиск по заметкам" }) ??
            screen.queryByText("Что-то пошло не так")
        ).not.toBeNull(),
      ASYNC
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(navigationAttempts).toEqual([]);
    expect(window.location.host).toBe("localhost:3000");
    if (!/[\t\n\r]/.test(next)) {
      expect(screen.getByRole("searchbox", { name: "Поиск по заметкам" })).toBeInTheDocument();
      expect(window.location.pathname).not.toBe("/login");
      expect(screen.queryByText("Вход в вики")).not.toBeInTheDocument();
    }
  });

  it.each([
    ["/n/a/b", "/n/a/b", ""],
    ["/search?q=x&tag=k8s", "/search", "?q=x&tag=k8s"],
    ["/b/11111111-2222-3333-4444-555555555555", "/b/11111111-2222-3333-4444-555555555555", ""],
  ])("законный next=%s возвращает на страницу вики", async (next, pathname, search) => {
    window.history.replaceState(null, "", `/login?next=${encodeURIComponent(next)}`);

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe(pathname), ASYNC);
    expect(window.location.search).toBe(search);
    expect(navigationAttempts).toEqual([]);
  });
});
