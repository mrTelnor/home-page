// QA: границы адресов вики (найдено на шаге 5, задача трекера 12).
//   slug: сегменты «.» и «..» не должны уводить запрос за пределы /api/wiki/notes/.
//   next: управляющие символы на странице входа не должны ронять приложение.
import { Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import { endpoints } from "@/api/endpoints";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeUser, mockResponse } from "@/test/utils";
import WikiApp from "@/wiki/WikiApp";
import { safeNextPath } from "@/wiki/paths";

vi.mock("@/lib/wikiHost", () => ({
  isWikiHost: () => true,
  mainSiteUrl: () => "https://example.test",
}));

const API_ORIGIN = "https://api.example.test";
const ASYNC = { timeout: 5000 };
const fetchMock = vi.fn();

/** Путь запроса так, как его увидит сервер: браузер схлопывает «.» и «..» до отправки. */
function serverPath(url: unknown): string {
  return new URL(String(url)).pathname;
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const path = serverPath(url);
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
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("D1: slug с сегментами «.» и «..» не выводит запрос за пределы /api/wiki/notes/", () => {
  it.each(["../../auth/me", "..", "a/../../recent", "./../notebooks", "a/../../../auth/logout"])(
    "endpoints.wiki.note(%j)",
    (slug) => {
      const path = serverPath(API_ORIGIN + endpoints.wiki.note(slug));
      expect(path.startsWith("/api/wiki/notes/")).toBe(true);
    }
  );

  it.each(["/n/..%2F..%2Fauth%2Fme", "/n/%2E%2E/%2E%2E/auth/me"])(
    "страница %s: запрос не уходит на чужой эндпоинт, показано «Заметка не найдена»",
    async (route) => {
      render(
        <QueryClientProvider client={createQueryClient()}>
          <MemoryRouter initialEntries={[route]}>
            <ErrorBoundary>
              <Suspense fallback={null}>
                <WikiApp />
              </Suspense>
            </ErrorBoundary>
          </MemoryRouter>
        </QueryClientProvider>
      );

      await waitFor(
        () =>
          expect(
            screen.queryByRole("heading", { name: "Заметка не найдена" }) ??
              screen.queryByText("Что-то пошло не так")
          ).not.toBeNull(),
        ASYNC
      );
      // Запрос, собранный как запрос заметки, должен и на сервере остаться запросом заметки
      const noteCalls = fetchMock.mock.calls
        .map(([url]) => String(url))
        .filter((url) => url.includes("/api/wiki/notes/"));
      expect(noteCalls.map(serverPath).filter((p) => !p.startsWith("/api/wiki/notes/"))).toEqual(
        []
      );
      // Чужой ответ (например, /api/auth/me) не должен рендериться как заметка и ронять страницу
      expect(screen.queryByText("Что-то пошло не так")).not.toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Заметка не найдена" })).toBeInTheDocument();
    }
  );
});

describe("D2: управляющие символы в next не роняют приложение", () => {
  const PAYLOADS = [
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
    "/\t\\evil.example",
  ];

  it.each(PAYLOADS)("safeNextPath(%j) — небезопасный путь заменяется корнем", (next) => {
    // Браузер выбрасывает \t \n \r при разборе адреса: «/\t/host» превращается в «//host»
    expect(safeNextPath(next)).toBe("/");
  });

  it.each(PAYLOADS)(
    "вошедший админ на /login?next=%j попадает в вики, а не на экран ошибки",
    async (next) => {
      window.history.replaceState(null, "", `/login?next=${encodeURIComponent(next)}`);

      render(<App />);

      await waitFor(
        () =>
          expect(
            screen.queryByRole("searchbox", { name: "Поиск по заметкам" }) ??
              screen.queryByText("Что-то пошло не так")
          ).not.toBeNull(),
        ASYNC
      );
      expect(screen.queryByText("Что-то пошло не так")).not.toBeInTheDocument();
      expect(window.location.pathname).toBe("/");
    }
  );
});
