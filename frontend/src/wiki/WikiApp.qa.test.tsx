// QA: гейт вики на внутренних страницах, состояния ошибок API, отсутствие лишних
// повторов запросов, путь slug «адрес страницы → адрес API → ссылка обратно».
import { Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { configure, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { type WikiNoteDetail, type WikiNoteSummary, type WikiNotebookNode } from "@/api/types";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeUser, mockResponse } from "@/test/utils";
import WikiApp from "./WikiApp";
import { notePath } from "./paths";

const DEFAULT_ASYNC_TIMEOUT = 1000;
const LAZY_ASYNC_TIMEOUT = 5000;
/** Дольше первой задержки повтора TanStack Query (1 с): за это время повтор успел бы уйти. */
const RETRY_WINDOW_MS = 1300;

type Reply = Parameters<typeof mockResponse>[0];
type Handler = Reply | (() => Reply | Promise<never>);

const fetchMock = vi.fn();

const NOTEBOOK_ID = "11111111-2222-3333-4444-555555555555";

const notebooks: WikiNotebookNode[] = [
  {
    id: NOTEBOOK_ID,
    name: "Блокнот",
    slug: "bloknot",
    parent_id: null,
    note_count: 1,
    total_note_count: 1,
    children: [],
  },
];

function makeNote(slug: string, overrides: Partial<WikiNoteDetail> = {}): WikiNoteDetail {
  return {
    id: "note-1",
    slug,
    title: "Заметка",
    content: "Текст заметки.",
    metadata: { type: "reference" },
    notebook: { id: NOTEBOOK_ID, name: "Блокнот", slug: "bloknot" },
    tags: [],
    links: [],
    backlinks: [],
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-03T09:00:00Z",
    ...overrides,
  };
}

function makeSummary(slug: string, title = "Заметка"): WikiNoteSummary {
  return {
    id: `id-${title}`,
    slug,
    title,
    notebook_id: NOTEBOOK_ID,
    metadata: {},
    tags: [],
    updated_at: "2026-10-03T09:00:00Z",
  };
}

const admin: Reply = { body: makeUser({ role: "admin", username: "nikita" }) };
const plainUser: Reply = { body: makeUser({ role: "user", username: "vasya" }) };
const unauthorized: Reply = { ok: false, status: 401, body: { detail: "Not authenticated" } };
const notFound: Reply = { ok: false, status: 404, body: { detail: "Not found" } };

/** Адрес запроса без origin — в том виде, в каком его собрал код (без нормализации URL). */
function rawPath(url: unknown): string {
  return String(url).replace(/^https?:\/\/[^/]+/, "");
}

function calls(): string[] {
  return fetchMock.mock.calls.map(([url]) => rawPath(url));
}

function wikiCalls(): string[] {
  return calls().filter((p) => p.startsWith("/api/wiki/"));
}

/** Ответы по началу пути запроса: выигрывает самый длинный подходящий ключ. */
function routeApi(routes: Record<string, Handler>) {
  const keys = Object.keys(routes).sort((a, b) => b.length - a.length);
  fetchMock.mockImplementation((url: string) => {
    const path = rawPath(url);
    const key = keys.find((k) => path === k || path.startsWith(k));
    const handler: Handler = key ? routes[key] : notFound;
    const reply = typeof handler === "function" ? handler() : handler;
    return reply instanceof Promise ? reply : Promise.resolve(mockResponse(reply));
  });
}

function adminApi(overrides: Record<string, Handler> = {}): Record<string, Handler> {
  return {
    "/api/auth/me": admin,
    "/api/wiki/notebooks": { body: notebooks },
    [`/api/wiki/notebooks/${NOTEBOOK_ID}/notes`]: { body: [] },
    "/api/wiki/recent": { body: [] },
    "/api/wiki/search": { body: [] },
    ...overrides,
  };
}

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

function renderWiki(route: string) {
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

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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

describe("QA вики: гейт на внутренних страницах", () => {
  it.each([
    ["/n/a/b", "/login?next=%2Fn%2Fa%2Fb"],
    [`/b/${NOTEBOOK_ID}`, `/login?next=%2Fb%2F${NOTEBOOK_ID}`],
    ["/search?q=traefik&tag=k8s", "/login?next=%2Fsearch%3Fq%3Dtraefik%26tag%3Dk8s"],
    ["/recipes", "/login?next=%2Frecipes"],
  ])("гость на %s → вход с возвратом, запросов к API вики нет", async (route, expected) => {
    routeApi({ "/api/auth/me": unauthorized });
    renderWiki(route);

    expect(await screen.findByText("Вход в вики")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(expected);
    await pause(100);
    expect(wikiCalls()).toEqual([]);
  });

  it.each(["/", "/n/a/b", `/b/${NOTEBOOK_ID}`, "/search?q=traefik", "/no-such-page"])(
    "обычный пользователь на %s → «Нет доступа», запросов к API вики нет",
    async (route) => {
      routeApi({
        ...adminApi(),
        "/api/auth/me": plainUser,
        "/api/wiki/notes/": { body: makeNote("a/b") },
      });
      renderWiki(route);

      expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
      expect(screen.getByText(/Вы вошли как vasya/)).toBeInTheDocument();
      // Ни шапки вики, ни дерева блокнотов, ни поиска
      expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: "Блокноты" })).not.toBeInTheDocument();
      await pause(150);
      expect(wikiCalls()).toEqual([]);
    }
  );

  it("обычный пользователь после входа на вики получает отказ, а не заметку", async () => {
    let loggedIn = false;
    routeApi({
      ...adminApi(),
      "/api/auth/login": () => {
        loggedIn = true;
        return { body: { message: "ok" } };
      },
      "/api/auth/me": () => (loggedIn ? plainUser : unauthorized),
      "/api/wiki/notes/": { body: makeNote("a/b") },
    });
    renderWiki("/login?next=%2Fn%2Fa%2Fb");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "vasya");
    await userEvent.type(screen.getByLabelText("Пароль"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/n/a/b");
    expect(wikiCalls()).toEqual([]);
  }, 15000);

  it("неверный пароль: сообщение об ошибке, остаёмся на входе", async () => {
    routeApi({
      "/api/auth/me": unauthorized,
      "/api/auth/login": { ok: false, status: 401, body: { detail: "Invalid credentials" } },
    });
    renderWiki("/login?next=%2Fn%2Fa%2Fb");

    await userEvent.type(await screen.findByLabelText("Имя пользователя"), "nikita");
    await userEvent.type(screen.getByLabelText("Пароль"), "wrong-pass");
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Неверный логин или пароль")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login?next=%2Fn%2Fa%2Fb");
    expect(wikiCalls()).toEqual([]);
  }, 15000);
});

describe("QA вики: ответы API с ошибкой — что видит админ и сколько запросов уходит", () => {
  const noteUrl = "/api/wiki/notes/a/b";

  it.each([
    [403, "Нет доступа", false],
    [404, "Заметка не найдена", false],
    [422, "Заметка не найдена", false],
    [429, "Слишком много запросов", true],
    [503, "База знаний недоступна", true],
    [500, "Ошибка загрузки", true],
    [502, "Ошибка загрузки", true],
  ])("заметка: %i → «%s», автоповторов нет", async (status, heading, hasRetry) => {
    routeApi(adminApi({ "/api/wiki/notes/": { ok: false, status, body: { detail: "x" } } }));
    renderWiki("/n/a/b");

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Повторить" }) !== null).toBe(hasRetry);
    // Текст заметки и обратные ссылки не показаны
    expect(screen.queryByRole("heading", { name: "Обратные ссылки" })).not.toBeInTheDocument();

    // Запрос заметки общий у шапки и страницы. Если ответ с ошибкой пришёл раньше, чем
    // загрузился чанк страницы, страница при появлении запрашивает ещё раз — не больше.
    const sent = calls().filter((p) => p === noteUrl).length;
    expect(sent).toBeGreaterThanOrEqual(1);
    expect(sent).toBeLessThanOrEqual(2);

    await pause(RETRY_WINDOW_MS);
    expect(calls().filter((p) => p === noteUrl)).toHaveLength(sent);
    expect(calls().filter((p) => p === "/api/wiki/notebooks")).toHaveLength(1);
    expect(calls().filter((p) => p === "/api/auth/me")).toHaveLength(1);
  });

  it.each([
    ["несуществующий блокнот (404)", `/b/${NOTEBOOK_ID}`, 404],
    ["id не uuid (422)", "/b/not-a-uuid", 422],
  ])("%s → «Блокнот не найден»", async (_name, route, status) => {
    routeApi(
      adminApi({
        [`/api/wiki/notebooks/${route.slice("/b/".length)}/notes`]: {
          ok: false,
          status,
          body: { detail: "Notebook not found" },
        },
      })
    );
    renderWiki(route);

    expect(await screen.findByRole("heading", { name: "Блокнот не найден" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "К обзору" })).toHaveAttribute("href", "/");
    const sent = wikiCalls().filter((p) => p.endsWith("/notes")).length;
    expect(sent).toBeLessThanOrEqual(2);
    await pause(RETRY_WINDOW_MS);
    expect(wikiCalls().filter((p) => p.endsWith("/notes"))).toHaveLength(sent);
  });

  it("поиск: 422 → «Запрос не принят», 429 → «Слишком много запросов»", async () => {
    routeApi(
      adminApi({
        "/api/wiki/search": { ok: false, status: 422, body: { detail: [{ msg: "too long" }] } },
      })
    );
    const first = renderWiki("/search?q=abc");
    expect(await screen.findByRole("heading", { name: "Запрос не принят" })).toBeInTheDocument();
    first.unmount();

    routeApi(
      adminApi({
        "/api/wiki/search": { ok: false, status: 429, body: { detail: "Too Many Requests" } },
      })
    );
    renderWiki("/search?q=abc");
    expect(
      await screen.findByRole("heading", { name: "Слишком много запросов" })
    ).toBeInTheDocument();
  });

  it("401 посреди работы: /me перечитывается, гостя уводит на вход с возвратом", async () => {
    let meCalls = 0;
    routeApi({
      "/api/auth/me": () => {
        meCalls += 1;
        // Первый ответ — ещё админ; сессия истекла, дальше 401
        return meCalls === 1 ? admin : unauthorized;
      },
      "/api/wiki/": unauthorized,
    });
    renderWiki("/n/a/b");

    expect(await screen.findByText("Вход в вики")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login?next=%2Fn%2Fa%2Fb");

    await pause(RETRY_WINDOW_MS);
    expect(meCalls).toBeLessThanOrEqual(3);
    expect(calls().filter((p) => p === noteUrl).length).toBeLessThanOrEqual(2);
    expect(calls().filter((p) => p === "/api/wiki/notebooks")).toHaveLength(1);
  });

  it("401 от API вики при живой сессии не зацикливает запросы", async () => {
    // Рассогласование: /me считает админом, API вики отвечает 401
    routeApi({ "/api/auth/me": admin, "/api/wiki/": unauthorized });
    renderWiki("/n/a/b");

    expect(await screen.findByRole("heading", { name: "Сессия закончилась" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login");

    await pause(RETRY_WINDOW_MS);
    expect(calls().filter((p) => p === "/api/auth/me").length).toBeLessThanOrEqual(2);
    expect(calls().filter((p) => p === noteUrl).length).toBeLessThanOrEqual(2);
    expect(screen.getByTestId("where")).toHaveTextContent("/n/a/b");
  });

  it("сетевой сбой: один повтор, затем «Ошибка загрузки»; дальше запросы не идут", async () => {
    routeApi(
      adminApi({
        "/api/wiki/notes/": () => Promise.reject(new TypeError("Failed to fetch")),
      })
    );
    renderWiki("/n/a/b");

    expect(await screen.findByRole("heading", { name: "Ошибка загрузки" })).toBeInTheDocument();
    expect(screen.getByText(/Проверьте соединение/)).toBeInTheDocument();
    expect(calls().filter((p) => p === noteUrl)).toHaveLength(2);

    // Следующий повтор TanStack Query ушёл бы через 2 с
    await pause(2500);
    expect(calls().filter((p) => p === noteUrl)).toHaveLength(2);
  }, 15000);

  it("«Повторить» после сетевого сбоя загружает заметку", async () => {
    let fail = true;
    routeApi(
      adminApi({
        "/api/wiki/notes/": () =>
          fail ? Promise.reject(new TypeError("Failed to fetch")) : { body: makeNote("a/b") },
      })
    );
    renderWiki("/n/a/b");

    const retry = await screen.findByRole("button", { name: "Повторить" });
    fail = false;
    await userEvent.click(retry);

    expect(await screen.findByText("Текст заметки.")).toBeInTheDocument();
  }, 15000);

  it("сбой дерева блокнотов не прячет заметку", async () => {
    routeApi(
      adminApi({
        "/api/wiki/notebooks": {
          ok: false,
          status: 503,
          body: { detail: "Wiki database is unavailable" },
        },
        "/api/wiki/notes/": { body: makeNote("a/b") },
      })
    );
    renderWiki("/n/a/b");

    expect(await screen.findByText("Текст заметки.")).toBeInTheDocument();
    expect(screen.getByText("Список блокнотов не загрузился.")).toBeInTheDocument();
  });
});

describe("QA вики: slug в адресе страницы, в адресе API и обратно", () => {
  const SLUGS = [
    "moi-domashnii-sait/grabli",
    "rabochie-zametki/anyflow-zone-migrations/2026-09-runbook",
    "рабочие-заметки/грабли дома",
    "скидки/100%/итог",
    "a?b/c#d/e&f=g+h",
    "a%20b/c%d/%",
    "(скобки)/it's/«кавычки»",
  ];

  /** Сегменты slug из адреса запроса к API: декодируем то, что реально ушло в fetch. */
  function slugFromApiCall(): string {
    const call = calls().find((p) => p.startsWith("/api/wiki/notes/"));
    expect(call, "запрос заметки не ушёл").toBeDefined();
    const tail = (call ?? "").slice("/api/wiki/notes/".length);
    // В адресе не осталось сырых «?» и «#»: иначе хвост slug ушёл бы в query или fragment
    expect(tail).not.toMatch(/[?#\s]/);
    return tail.split("/").map(decodeURIComponent).join("/");
  }

  it.each(SLUGS)("страница /n/<slug> запрашивает ровно этот slug: %s", async (slug) => {
    routeApi(adminApi({ "/api/wiki/notes/": { body: makeNote(slug) } }));
    renderWiki(notePath(slug));

    expect(await screen.findByText("Текст заметки.")).toBeInTheDocument();
    expect(slugFromApiCall()).toBe(slug);
    // Бэкенд (Starlette, {slug:path}) декодирует путь один раз — получит исходный slug
    expect(
      new URL(
        `https://api.example.test${calls().find((p) => p.startsWith("/api/wiki/notes/"))}`
      ).pathname
        .slice("/api/wiki/notes/".length)
        .split("/")
        .map(decodeURIComponent)
        .join("/")
    ).toBe(slug);
  });

  it.each(SLUGS)("ссылка из списка заметок ведёт на тот же slug: %s", async (slug) => {
    routeApi(
      adminApi({
        "/api/wiki/recent": { body: [makeSummary(slug, "Цель перехода")] },
        "/api/wiki/notes/": { body: makeNote(slug) },
      })
    );
    renderWiki("/");

    await userEvent.click(await screen.findByRole("link", { name: "Цель перехода" }));

    expect(await screen.findByText("Текст заметки.")).toBeInTheDocument();
    expect(slugFromApiCall()).toBe(slug);
  });

  it("[[ссылка]] и обратная ссылка со сложным slug ведут на нужную заметку", async () => {
    const target = "рабочие-заметки/a?b#c/100%";
    const source = makeNote("a/b", {
      content: "См. [[Цель]].",
      links: [{ slug: target, title: "Цель", alias: null }],
      backlinks: [{ slug: target, title: "Источник", alias: null }],
    });
    routeApi(adminApi({ "/api/wiki/notes/": { body: source } }));
    renderWiki("/n/a/b");

    const expected = notePath(target);
    expect(await screen.findByRole("link", { name: "Цель" })).toHaveAttribute("href", expected);
    expect(screen.getByRole("link", { name: "Источник" })).toHaveAttribute("href", expected);

    fetchMock.mockClear();
    await userEvent.click(screen.getByRole("link", { name: "Цель" }));
    await waitFor(() => expect(calls().some((p) => p.startsWith("/api/wiki/notes/"))).toBe(true));
    expect(slugFromApiCall()).toBe(target);
  });

  it("id блокнота уходит в API одним сегментом пути", async () => {
    routeApi(adminApi());
    renderWiki(`/b/${NOTEBOOK_ID}`);

    expect(await screen.findByRole("heading", { level: 1, name: "Блокнот" })).toBeInTheDocument();
    await waitFor(() => expect(wikiCalls()).toContain(`/api/wiki/notebooks/${NOTEBOOK_ID}/notes`));
  });

  it("параметры поиска с кириллицей и спецсимволами доходят до API без искажений", async () => {
    routeApi(adminApi());
    const q = "грабл & 100% #1 a+b";
    renderWiki(
      `/search?${new URLSearchParams({ q, tag: "c++", project: "home-page" }).toString()}`
    );

    await waitFor(() =>
      expect(wikiCalls().some((p) => p.startsWith("/api/wiki/search?"))).toBe(true)
    );
    const sent = new URLSearchParams(
      (wikiCalls().find((p) => p.startsWith("/api/wiki/search?")) ?? "").split("?")[1]
    );
    expect(sent.get("q")).toBe(q);
    expect(sent.get("tag")).toBe("c++");
    expect(sent.get("project")).toBe("home-page");
    expect(sent.get("limit")).toBe("50");
  });
});

describe("QA вики: данные заметки вне Markdown тоже не становятся разметкой", () => {
  it("название, теги, metadata, имя блокнота и алиас обратной ссылки с HTML — текст", async () => {
    const xss = '<img src=x onerror="window.__qaXss=1">';
    const note = makeNote("a/b", {
      title: `Заголовок ${xss}`,
      content: "Без своего заголовка.",
      metadata: { type: `t${xss}`, status: `s${xss}`, project: `p${xss}` },
      tags: [`tag${xss}`],
      notebook: { id: NOTEBOOK_ID, name: `Блокнот ${xss}`, slug: "x" },
      backlinks: [{ slug: "c/d", title: `Источник ${xss}`, alias: `алиас ${xss}` }],
    });
    routeApi(adminApi({ "/api/wiki/notes/": { body: note } }));
    const { container } = renderWiki("/n/a/b");

    expect(await screen.findByText("Без своего заголовка.")).toBeInTheDocument();
    expect(container.querySelector("img, script, [onerror]")).toBeNull();
    expect(container.textContent).toContain(`Заголовок ${xss}`);
    expect((window as unknown as Record<string, unknown>).__qaXss).toBeUndefined();
    // Бейджи ведут в поиск вики, значение — параметром запроса
    for (const a of container.querySelectorAll("a")) {
      expect(a.getAttribute("href")?.startsWith("/")).toBe(true);
    }
  });
});
