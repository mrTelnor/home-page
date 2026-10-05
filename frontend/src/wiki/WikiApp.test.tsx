import { Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { configure, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  type WikiNoteDetail,
  type WikiNoteSummary,
  type WikiNotebookNode,
} from "@/api/types";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeUser, mockResponse } from "@/test/utils";
import WikiApp from "./WikiApp";

// Страницы вики — lazy-чанки (заметка тянет разбор Markdown): при параллельном прогоне
// всех тестов первая загрузка не укладывается в стандартную секунду ожидания
const DEFAULT_ASYNC_TIMEOUT = 1000;
const LAZY_ASYNC_TIMEOUT = 5000;

const fetchMock = vi.fn();

type Reply = Parameters<typeof mockResponse>[0];

const notebooks: WikiNotebookNode[] = [
  {
    id: "nb-root",
    name: "Пет-проекты",
    slug: "pet-proekty",
    parent_id: null,
    note_count: 0,
    total_note_count: 2,
    children: [
      {
        id: "nb-site",
        name: "Мой домашний сайт",
        slug: "moi-domashnii-sait",
        parent_id: "nb-root",
        note_count: 2,
        total_note_count: 2,
        children: [],
      },
    ],
  },
];

const summary: WikiNoteSummary = {
  id: "note-1",
  slug: "moi-domashnii-sait/grabli",
  title: "Грабли home-page",
  notebook_id: "nb-site",
  metadata: { type: "reference", project: "home-page", status: "active" },
  tags: ["docker"],
  updated_at: "2026-10-03T09:00:00Z",
};

const note: WikiNoteDetail = {
  id: "note-1",
  slug: "moi-domashnii-sait/grabli",
  title: "Грабли home-page",
  content: "# Грабли home-page\n\nИндекс: [[README]], см. также [[Нет такой]].",
  metadata: { type: "reference", project: "home-page", status: "active" },
  notebook: { id: "nb-site", name: "Мой домашний сайт", slug: "moi-domashnii-sait" },
  tags: ["docker"],
  links: [{ slug: "moi-domashnii-sait/readme", title: "README", alias: null }],
  backlinks: [{ slug: "moi-domashnii-sait/arkhitektura", title: "Архитектура", alias: null }],
  created_at: "2026-09-30T09:00:00Z",
  updated_at: "2026-10-03T09:00:00Z",
};

const unauthorized: Reply = { ok: false, status: 401, body: { detail: "Not authenticated" } };
const unavailable: Reply = {
  ok: false,
  status: 503,
  statusText: "Service Unavailable",
  body: { detail: "Wiki database is unavailable" },
};

/** Ответы API по пути запроса; неизвестный путь — 404. */
function routeApi(routes: Record<string, Reply>) {
  fetchMock.mockImplementation((url: string) => {
    const path = new URL(url).pathname;
    const reply = routes[path] ?? { ok: false, status: 404, body: { detail: "Not found" } };
    return Promise.resolve(mockResponse(reply));
  });
}

const adminApi = (overrides: Record<string, Reply> = {}): Record<string, Reply> => ({
  "/api/auth/me": { body: makeUser({ role: "admin", username: "nikita" }) },
  "/api/wiki/notebooks": { body: notebooks },
  "/api/wiki/recent": { body: [summary] },
  "/api/wiki/search": { body: [summary] },
  "/api/wiki/notebooks/nb-site/notes": { body: [summary] },
  "/api/wiki/notes/moi-domashnii-sait/grabli": { body: note },
  ...overrides,
});

function calledPaths(): string[] {
  return fetchMock.mock.calls.map(([url]) => {
    const parsed = new URL(url as string);
    return parsed.pathname + parsed.search;
  });
}

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

function renderWiki(route = "/") {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[route]}>
        <Suspense fallback={<p>Загрузка чанка...</p>}>
          <WikiApp />
        </Suspense>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  configure({ asyncUtilTimeout: LAZY_ASYNC_TIMEOUT });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  configure({ asyncUtilTimeout: DEFAULT_ASYNC_TIMEOUT });
  vi.unstubAllGlobals();
});

describe("вики: доступ", () => {
  it("гостя отправляет на вход с возвратом на исходную страницу", async () => {
    routeApi({ "/api/auth/me": unauthorized });
    renderWiki("/n/moi-domashnii-sait/grabli");

    expect(await screen.findByText("Вход в вики")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/login?next=%2Fn%2Fmoi-domashnii-sait%2Fgrabli"
    );
    // До API вики гость не доходит
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/"))).toBe(false);
  });

  it("обычному пользователю — отказ, без запросов к API вики", async () => {
    routeApi({ "/api/auth/me": { body: makeUser({ role: "user", username: "vasya" }) } });
    renderWiki("/");

    expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
    expect(screen.getByText(/только администраторам/)).toBeInTheDocument();
    expect(screen.queryByText("База знаний")).not.toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/"))).toBe(false);
  });

  it("админ видит обзор: дерево блокнотов и последние изменения", async () => {
    routeApi(adminApi());
    renderWiki("/");

    expect(await screen.findByRole("heading", { name: "База знаний" })).toBeInTheDocument();
    const tree = await screen.findByRole("navigation", { name: "Блокноты" });
    expect(within(tree).getByRole("link", { name: /Мой домашний сайт/ })).toHaveAttribute(
      "href",
      "/b/nb-site"
    );
    const recentLink = await screen.findByRole("link", { name: "Грабли home-page" });
    expect(recentLink).toHaveAttribute("href", "/n/moi-domashnii-sait/grabli");
    expect(screen.getByText("reference")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("#docker")).toBeInTheDocument();
  });

  it("ошибка проверки авторизации не выкидывает на вход", async () => {
    routeApi({ "/api/auth/me": { ok: false, status: 500, body: {} } });
    renderWiki("/");

    // useMe дважды повторяет запрос при 5xx (1 с и 2 с) — ждём дольше обычного
    expect(await screen.findByText(/Не удалось проверить авторизацию/)).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/");
  }, 10000);

  it("после входа возвращает на страницу из next", async () => {
    let loggedIn = false;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      if (path === "/api/auth/login" && init?.method === "POST") {
        loggedIn = true;
        return Promise.resolve(mockResponse({ body: { message: "ok" } }));
      }
      if (path === "/api/auth/me") {
        return Promise.resolve(
          mockResponse(loggedIn ? { body: makeUser({ role: "admin" }) } : unauthorized)
        );
      }
      const reply = adminApi()[path] ?? { ok: false, status: 404, body: { detail: "Not found" } };
      return Promise.resolve(mockResponse(reply));
    });
    renderWiki("/login?next=%2Fn%2Fmoi-domashnii-sait%2Fgrabli");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "nikita");
    await userEvent.type(screen.getByLabelText("Пароль"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("/n/moi-domashnii-sait/grabli")
    );
    expect(await screen.findByRole("heading", { name: "Обратные ссылки" })).toBeInTheDocument();
  }, 15000);

  it("внешний адрес в next игнорируется", async () => {
    routeApi(adminApi());
    renderWiki("/login?next=https%3A%2F%2Fevil.example");

    // Админ уже вошёл — со страницы входа уходит на корень вики, а не наружу
    expect(await screen.findByRole("heading", { name: "База знаний" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/");
  });
});

describe("вики: база знаний недоступна (503)", () => {
  it("обзор показывает понятное состояние и кнопку повтора", async () => {
    routeApi(adminApi({ "/api/wiki/notebooks": unavailable, "/api/wiki/recent": unavailable }));
    renderWiki("/");

    expect(await screen.findByRole("heading", { name: "База знаний недоступна" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
    // 503 не повторяем автоматически: по одному запросу на эндпоинт
    expect(calledPaths().filter((p) => p === "/api/wiki/notebooks")).toHaveLength(1);
  });

  it("«Повторить» перезапрашивает данные и показывает обзор", async () => {
    const routes = adminApi({ "/api/wiki/notebooks": unavailable, "/api/wiki/recent": unavailable });
    routeApi(routes);
    renderWiki("/");
    const retry = await screen.findByRole("button", { name: "Повторить" });

    routeApi(adminApi());
    await userEvent.click(retry);

    expect(await screen.findByRole("heading", { name: "База знаний" })).toBeInTheDocument();
    expect(screen.queryByText("База знаний недоступна")).not.toBeInTheDocument();
  });

  it("страница заметки при 503 — то же состояние", async () => {
    routeApi(adminApi({ "/api/wiki/notes/moi-domashnii-sait/grabli": unavailable }));
    renderWiki("/n/moi-domashnii-sait/grabli");

    expect(await screen.findByRole("heading", { name: "База знаний недоступна" })).toBeInTheDocument();
  });
});

describe("вики: заметка, блокнот, поиск", () => {
  it("заметка: текст, ссылки [[…]], бейджи, обратные ссылки", async () => {
    routeApi(adminApi());
    renderWiki("/n/moi-domashnii-sait/grabli");

    expect(await screen.findByRole("heading", { level: 1, name: "Грабли home-page" })).toBeInTheDocument();
    // Заголовок из текста заметки не дублируется заголовком страницы
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "README" })).toHaveAttribute(
      "href",
      "/n/moi-domashnii-sait/readme"
    );
    expect(screen.getByText("Нет такой")).toHaveClass("wiki-link-unresolved");
    expect(screen.getByRole("link", { name: "reference" })).toHaveAttribute("href", "/search?type=reference");
    expect(screen.getByRole("link", { name: "#docker" })).toHaveAttribute("href", "/search?tag=docker");
    expect(screen.getByRole("link", { name: "Архитектура" })).toHaveAttribute(
      "href",
      "/n/moi-domashnii-sait/arkhitektura"
    );
    // slug уходит в API со слэшами, без %2F
    expect(calledPaths()).toContain("/api/wiki/notes/moi-domashnii-sait/grabli");
  });

  it("несуществующая заметка — «не найдена»", async () => {
    routeApi(adminApi());
    renderWiki("/n/net/takoi");

    expect(await screen.findByRole("heading", { name: "Заметка не найдена" })).toBeInTheDocument();
  });

  it("блокнот: путь, название и заметки", async () => {
    routeApi(adminApi());
    renderWiki("/b/nb-site");

    expect(await screen.findByRole("heading", { level: 1, name: "Мой домашний сайт" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Грабли home-page" })).toBeInTheDocument();
    const trail = screen.getByRole("navigation", { name: "Путь" });
    expect(within(trail).getByRole("link", { name: "Пет-проекты" })).toHaveAttribute("href", "/b/nb-root");
  });

  it("поиск: параметры адреса уходят в API, выдача показывается", async () => {
    routeApi(adminApi());
    renderWiki("/search?q=grab&type=reference&tag=docker");

    expect(await screen.findByRole("heading", { name: /Найдено: 1/ })).toBeInTheDocument();
    expect(calledPaths()).toContain("/api/wiki/search?q=grab&type=reference&tag=docker&limit=50");
    expect(screen.getByLabelText("Тип")).toHaveValue("reference");
    expect(screen.getByLabelText("Тег")).toHaveValue("docker");
  });

  it("поиск без слов и фильтров не ходит в API", async () => {
    routeApi(adminApi());
    renderWiki("/search");

    expect(await screen.findByText(/Введите слова или выберите фильтр/)).toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/search"))).toBe(false);
  });

  it("строка поиска в шапке ведёт на страницу поиска", async () => {
    routeApi(adminApi());
    renderWiki("/");

    const box = await screen.findByRole("searchbox", { name: "Поиск по заметкам" });
    await userEvent.type(box, "traefik{Enter}");

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/search?q=traefik"));
  });
});

describe("вики: мета robots", () => {
  it("добавляет noindex, nofollow и убирает при размонтировании", async () => {
    routeApi({ "/api/auth/me": unauthorized });
    const { unmount } = renderWiki("/login");

    await screen.findByText("Вход в вики");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, nofollow"
    );
    unmount();
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
  });
});
