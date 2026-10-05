// QA: вход на вики через страницу входа основного сайта — сценарии целиком (задача трекера 12,
// доработка шага 5). Настоящий App с BrowserRouter и настоящие lib/wikiHost, wiki/paths,
// lib/wikiReturn: подменён только сам переход (lib/redirect) — его адрес запоминается, и
// следующая «страница» открывается ровно по нему. Адрес страницы jsdom меняем через
// reconfigure: сайт — http://localhost:3000, его вики — http://wiki.localhost:3000.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeUser, mockResponse } from "@/test/utils";

const redirects = vi.hoisted(() => [] as string[]);
vi.mock("@/lib/redirect", () => ({
  redirectTo: (url: string) => {
    redirects.push(url);
  },
}));

const SITE = "http://localhost:3000";
const WIKI = "http://wiki.localhost:3000";
const ASYNC = { timeout: 5000 };
const LONG = 20_000;

// Vitest кладёт экземпляр JSDOM в глобальную переменную jsdom
const dom = (globalThis as unknown as { jsdom: { reconfigure(o: { url: string }): void } }).jsdom;

const fetchMock = vi.fn();
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const unauthorized = { ok: false, status: 401, body: { detail: "Not authenticated" } };
const siteLogin = (wikiUrl: string) => `${SITE}/login?next=${encodeURIComponent(wikiUrl)}`;

type Reply = Parameters<typeof mockResponse>[0];

/** Кто вошёл: null — гость. Может зависеть от того, с какой страницы пришёл запрос. */
let me: () => Reply = () => unauthorized;
let wikiApi: Reply | null = null;

function calls(): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
}

/**
 * Открыть адрес «как в новой загрузке страницы»: модули приложения (а с ними клиент
 * запросов и хранилище) создаются заново — после перехода между сайтом и вики кэша нет.
 */
async function open(url: string) {
  cleanup();
  vi.resetModules();
  dom.reconfigure({ url });
  const { default: App } = await import("./App");
  render(<App />);
}

beforeEach(() => {
  redirects.length = 0;
  me = () => unauthorized;
  wikiApi = null;
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname;
    if (path === "/api/auth/me") return Promise.resolve(mockResponse(me()));
    if (path === "/api/auth/login" && init?.method === "POST") {
      return Promise.resolve(mockResponse({ body: { message: "ok" } }));
    }
    if (path === "/api/auth/logout") {
      me = () => unauthorized;
      return Promise.resolve(mockResponse({ status: 204, body: null }));
    }
    if (path.startsWith("/api/wiki/")) return Promise.resolve(mockResponse(wikiApi ?? { body: [] }));
    return Promise.resolve(mockResponse({ ok: false, status: 404, body: { detail: "Not found" } }));
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  dom.reconfigure({ url: `${SITE}/` });
});

describe("QA вход на вики через сайт: гость", () => {
  it(
    "страница вики с запросом и якорем → вход сайта → после входа ровно та же страница",
    async () => {
      const page = `${WIKI}/search?q=a%26b&tag=k8s#top`;

      // 1. Гость на вики: один переход на вход сайта, в next — полный адрес страницы
      await open(page);
      await waitFor(() => expect(redirects).toEqual([siteLogin(page)]), ASYNC);
      expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
      expect(calls().filter((p) => p.startsWith("/api/wiki/"))).toEqual([]);

      // 2. Страница входа сайта по этому адресу: форма, до входа никуда не уводит
      await open(redirects[0]);
      const user = userEvent.setup();
      await user.type(await screen.findByLabelText("Имя пользователя", {}, ASYNC), "nikita");
      await user.type(screen.getByLabelText("Пароль"), "secret123");
      await pause(50);
      expect(redirects).toHaveLength(1);

      // 3. Вход: один переход, ровно на исходную страницу вики
      me = () => ({ body: makeUser({ role: "admin" }) });
      await user.click(screen.getByRole("button", { name: "Войти" }));
      await waitFor(() => expect(redirects).toHaveLength(2), ASYNC);
      expect(redirects[1]).toBe(page);
      await pause(50);
      expect(redirects).toHaveLength(2);
      // Роутер сайта на главную не уводил
      expect(window.location.pathname).toBe("/login");

      // 4. Вики по адресу возврата: админ видит свою страницу, новых переходов нет
      await open(redirects[1]);
      expect(
        await screen.findByRole("searchbox", { name: "Поиск по заметкам" }, ASYNC)
      ).toBeInTheDocument();
      await pause(100);
      expect(redirects).toHaveLength(2);
      expect(window.location.href).toBe(page);
    },
    LONG
  );

  it("старый адрес /login на вики: возврат — на корень вики, чужой next не переносится", async () => {
    await open(`${WIKI}/login?next=https%3A%2F%2Fevil.example%2F#x`);

    await waitFor(() => expect(redirects).toEqual([siteLogin(`${WIKI}/`)]), ASYNC);
    expect(redirects[0]).not.toContain("evil");
  });
});

describe("QA вход на вики через сайт: уже вошедший", () => {
  it("админ на /login?next=<вики> сразу уходит на вики — один переход, формы нет", async () => {
    me = () => ({ body: makeUser({ role: "admin" }) });
    const page = `${WIKI}/n/moi-domashnii-sait/grabli?x=1#h`;

    await open(siteLogin(page));

    await waitFor(() => expect(redirects).toEqual([page]), ASYNC);
    await pause(100);
    expect(redirects).toHaveLength(1);
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
  });

  it(
    "не-админ: сайт возвращает на вики, там «Нет доступа» — и на этом всё, круга нет",
    async () => {
      me = () => ({ body: makeUser({ role: "user", username: "vasya" }) });
      const page = `${WIKI}/n/a/b`;

      await open(siteLogin(page));
      await waitFor(() => expect(redirects).toEqual([page]), ASYNC);

      await open(redirects[0]);
      expect(await screen.findByRole("heading", { name: "Нет доступа" }, ASYNC)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "На сайт" })).toHaveAttribute("href", SITE);
      await pause(200);
      expect(redirects).toHaveLength(1);
      expect(calls().filter((p) => p.startsWith("/api/wiki/"))).toEqual([]);

      // «Выйти» с экрана отказа: вход сайта с возвратом на корень вики
      await userEvent.click(screen.getByRole("button", { name: "Выйти" }));
      await waitFor(() => expect(redirects).toHaveLength(2), ASYNC);
      expect(redirects[1]).toBe(siteLogin(`${WIKI}/`));
    },
    LONG
  );
});

describe("QA вход на вики через сайт: сессия закончилась посреди работы", () => {
  it("API вики отвечает 401, «кто я» — админ: ссылка «Войти» на вход сайта, сам не уводит", async () => {
    me = () => ({ body: makeUser({ role: "admin" }) });
    wikiApi = unauthorized;
    const page = `${WIKI}/search?q=traefik`;

    await open(page);

    const headings = await screen.findAllByRole("heading", { name: "Сессия закончилась" }, ASYNC);
    expect(headings.length).toBeGreaterThan(0);
    for (const link of screen.getAllByRole("link", { name: "Войти" })) {
      expect(link).toHaveAttribute("href", siteLogin(page));
    }
    await pause(200);
    expect(redirects).toEqual([]);
  });
});

describe("QA вики без поддомена (VITE_WIKI=true)", () => {
  it("гость видит «Нужен вход», перехода и ссылки на вход нет", async () => {
    vi.stubEnv("VITE_WIKI", "true");

    await open(`${SITE}/n/a/b?x=1`);

    expect(await screen.findByRole("heading", { name: "Нужен вход" }, ASYNC)).toBeInTheDocument();
    await pause(100);
    expect(redirects).toEqual([]);
    expect(screen.queryByRole("link", { name: "Войти на сайте" })).not.toBeInTheDocument();
    expect(window.location.href).toBe(`${SITE}/n/a/b?x=1`);
    expect(calls().filter((p) => p.startsWith("/api/wiki/"))).toEqual([]);
  });
});

describe("QA основной сайт без next — как раньше", () => {
  it(
    "страница входа не спрашивает «кто я»; после входа — главная сайта, перехода на вики нет",
    async () => {
      await open(`${SITE}/login`);

      const user = userEvent.setup();
      await user.type(await screen.findByLabelText("Имя пользователя", {}, ASYNC), "nikita");
      await user.type(screen.getByLabelText("Пароль"), "secret123");
      await pause(50);
      expect(calls()).toEqual([]);

      me = () => ({ body: makeUser() });
      await user.click(screen.getByRole("button", { name: "Войти" }));

      await waitFor(() => expect(window.location.pathname).toBe("/"), ASYNC);
      expect(redirects).toEqual([]);
    },
    LONG
  );

  it("уже вошедший на /login без next остаётся на форме — как до доработки", async () => {
    me = () => ({ body: makeUser({ role: "admin" }) });

    await open(`${SITE}/login`);

    expect(await screen.findByLabelText("Пароль", {}, ASYNC)).toBeInTheDocument();
    await pause(100);
    expect(redirects).toEqual([]);
    expect(calls()).toEqual([]);
    expect(window.location.pathname).toBe("/login");
  });
});

describe("QA зацикливание между сайтом и вики", () => {
  // Известный дефект (задача трекера 12): если «кто я» с адреса вики отвечает 401, а с адреса
  // сайта — 200 (cookie API не доходит с вики: другой site, блокировка в браузере), сайт
  // и вики перекидывают человека друг другу без конца — предохранителя нет.
  // Тест покраснеет, когда появится предохранитель, — тогда `it.fails` заменить на `it`.
  it.fails(
    "ДЕФЕКТ: cookie не доходит с вики — перекидывание между сайтом и вики останавливается",
    async () => {
      me = () =>
        window.location.host.startsWith("wiki.")
          ? unauthorized
          : { body: makeUser({ role: "admin" }) };
      const ROUNDS = 4;

      let url = `${WIKI}/n/a/b`;
      for (let i = 0; i < ROUNDS * 2; i++) {
        const before = redirects.length;
        await open(url);
        try {
          await waitFor(() => expect(redirects.length).toBe(before + 1), { timeout: 1500 });
        } catch {
          break; // страница никуда не увела — круг разорван
        }
        url = redirects[redirects.length - 1];
      }

      expect(redirects.length).toBeLessThan(ROUNDS * 2);
    },
    LONG
  );
});
