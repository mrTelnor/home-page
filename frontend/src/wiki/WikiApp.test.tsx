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
import { redirectTo } from "@/lib/redirect";
import { mainSiteUrl } from "@/lib/wikiHost";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeUser, mockResponse } from "@/test/utils";
import WikiApp from "./WikiApp";

// Страницы вики — lazy-чанки (заметка тянет разбор Markdown): при параллельном прогоне
// всех тестов первая загрузка не укладывается в стандартную секунду ожидания
const DEFAULT_ASYNC_TIMEOUT = 1000;
const LAZY_ASYNC_TIMEOUT = 5000;

// Переход на другой origin (вход — на основном сайте) jsdom выполнить не может — перехватываем
vi.mock("@/lib/redirect", () => ({ redirectTo: vi.fn() }));
// Вики на поддомене wiki.: адрес основного сайта известен
vi.mock("@/lib/wikiHost", () => ({
  isWikiHost: () => true,
  mainSiteUrl: vi.fn(() => "https://example.test"),
}));

const fetchMock = vi.fn();
const redirectMock = vi.mocked(redirectTo);
const mainSiteUrlMock = vi.mocked(mainSiteUrl);

/** Страница входа сайта с возвратом на страницу вики (тесты открыты на http://localhost:3000). */
const siteLogin = (path: string) =>
  `https://example.test/login?next=${encodeURIComponent(window.location.origin + path)}`;

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
  redirectMock.mockReset();
  mainSiteUrlMock.mockReturnValue("https://example.test");
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  configure({ asyncUtilTimeout: DEFAULT_ASYNC_TIMEOUT });
  vi.unstubAllGlobals();
});

describe("вики: доступ", () => {
  it("гостя отправляет на вход основного сайта с возвратом на исходную страницу", async () => {
    routeApi({ "/api/auth/me": unauthorized });
    renderWiki("/n/moi-domashnii-sait/grabli?x=1");

    const expected = siteLogin("/n/moi-domashnii-sait/grabli?x=1");
    expect(await screen.findByRole("link", { name: "Войти на сайте" })).toHaveAttribute(
      "href",
      expected
    );
    expect(redirectMock).toHaveBeenCalledTimes(1);
    expect(redirectMock).toHaveBeenCalledWith(expected);
    // Своей формы входа нет, роутер вики адрес не меняет
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/n/moi-domashnii-sait/grabli?x=1");
    // До API вики гость не доходит
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/"))).toBe(false);
  });

  it("адрес возврата — ровно origin вики и исходная страница", async () => {
    routeApi({ "/api/auth/me": unauthorized });
    renderWiki("/search?q=a%26b&tag=k8s");

    await screen.findByRole("link", { name: "Войти на сайте" });
    const target = new URL(redirectMock.mock.calls[0][0]);
    expect(target.origin + target.pathname).toBe("https://example.test/login");
    expect([...target.searchParams.keys()]).toEqual(["next"]);
    expect(target.searchParams.get("next")).toBe(
      `${window.location.origin}/search?q=a%26b&tag=k8s`
    );
  });

  it("старый адрес /login на вики: гость уходит на вход сайта с возвратом на корень вики", async () => {
    routeApi({ "/api/auth/me": unauthorized });
    renderWiki("/login?next=https%3A%2F%2Fevil.example");

    await screen.findByRole("link", { name: "Войти на сайте" });
    expect(redirectMock).toHaveBeenCalledWith(siteLogin("/"));
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
  });

  it("локально (VITE_WIKI=true, адрес сайта неизвестен): гостю — подсказка, без перехода", async () => {
    mainSiteUrlMock.mockReturnValue(null);
    let loggedIn = false;
    fetchMock.mockImplementation((url: string) => {
      const path = new URL(url).pathname;
      if (path === "/api/auth/me") {
        return Promise.resolve(
          mockResponse(loggedIn ? { body: makeUser({ role: "admin" }) } : unauthorized)
        );
      }
      const reply = adminApi()[path] ?? { ok: false, status: 404, body: { detail: "Not found" } };
      return Promise.resolve(mockResponse(reply));
    });
    renderWiki("/");

    expect(await screen.findByRole("heading", { name: "Нужен вход" })).toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("link", { name: "Войти на сайте" })).not.toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/"))).toBe(false);

    // Вошёл на сайте в соседней вкладке — «Проверить снова» открывает вики
    loggedIn = true;
    await userEvent.click(screen.getByRole("button", { name: "Проверить снова" }));

    expect(await screen.findByRole("heading", { name: "База знаний" })).toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("обычному пользователю — отказ, без запросов к API вики", async () => {
    routeApi({ "/api/auth/me": { body: makeUser({ role: "user", username: "vasya" }) } });
    renderWiki("/");

    expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
    expect(screen.getByText(/только администраторам/)).toBeInTheDocument();
    expect(screen.queryByText("База знаний")).not.toBeInTheDocument();
    expect(calledPaths().some((p) => p.startsWith("/api/wiki/"))).toBe(false);
    // Вошедшего не-админа на вход не гоняем
    expect(redirectMock).not.toHaveBeenCalled();
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
    expect(redirectMock).not.toHaveBeenCalled();
  }, 10000);

  it("вошедший на сайте админ, вернувшись по адресу возврата, видит исходную страницу", async () => {
    // Сессия общая: cookie ставит API, поэтому после входа на сайте вики открывается сразу
    routeApi(adminApi());
    renderWiki("/n/moi-domashnii-sait/grabli");

    expect(await screen.findByRole("heading", { name: "Обратные ссылки" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/n/moi-domashnii-sait/grabli");
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("у вики нет страницы /login: вошедшему админу — «Страница не найдена», next не читается", async () => {
    routeApi(adminApi());
    renderWiki("/login?next=https%3A%2F%2Fevil.example");

    expect(await screen.findByRole("heading", { name: "Страница не найдена" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("«Выйти» в шапке вики: после выхода — на вход сайта с возвратом на корень вики", async () => {
    let loggedIn = true;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      if (path === "/api/auth/logout" && init?.method === "POST") {
        loggedIn = false;
        return Promise.resolve(mockResponse({ status: 204, body: null }));
      }
      if (path === "/api/auth/me") {
        return Promise.resolve(
          mockResponse(loggedIn ? { body: makeUser({ role: "admin" }) } : unauthorized)
        );
      }
      const reply = adminApi()[path] ?? { ok: false, status: 404, body: { detail: "Not found" } };
      return Promise.resolve(mockResponse(reply));
    });
    renderWiki("/n/moi-domashnii-sait/grabli");
    await screen.findByRole("heading", { name: "Обратные ссылки" });

    await userEvent.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(redirectMock).toHaveBeenCalledWith(siteLogin("/")));
    expect(screen.queryByRole("heading", { name: "Обратные ссылки" })).not.toBeInTheDocument();
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
    const { unmount } = renderWiki("/");

    await screen.findByRole("link", { name: "Войти на сайте" });
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, nofollow"
    );
    unmount();
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
  });
});
