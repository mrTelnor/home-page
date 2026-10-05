// Возврат на вики со страницы входа основного сайта (`/login?next=…`) — на настоящем App
// с BrowserRouter и без подмены перехода: открытый редирект в React Router проявляется
// только с настоящей историей браузера, а уход со страницы jsdom выдаёт событием jsdomError.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { isWikiHost } from "@/lib/wikiHost";
import { useAuthStore } from "@/store/auth";
import { makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();
const ASYNC = { timeout: 5000 };
// Тесты открыты на http://localhost:3000 — это основной сайт, его вики:
const WIKI = "http://wiki.localhost:3000";

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

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const unauthorized = { ok: false, status: 401, body: { detail: "Not authenticated" } };

let loggedIn = false;

function openLogin(next: string) {
  window.history.replaceState(null, "", `/login?next=${encodeURIComponent(next)}`);
  render(<App />);
}

beforeEach(() => {
  navigationAttempts = [];
  loggedIn = false;
  dom.virtualConsole.on("jsdomError", onJsdomError);
  fetchMock.mockReset();
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
    return Promise.resolve(mockResponse({ ok: false, status: 404, body: { detail: "Not found" } }));
  });
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  dom.virtualConsole.off("jsdomError", onJsdomError);
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

/** Адреса возврата, которые страница входа обязана проигнорировать. */
const BAD_NEXT = [
  "https://evil.example/",
  "http://evil.example/n/a",
  "http://wiki.localhost:3000.evil.example/",
  "http://wiki.localhost.evil.example:3000/",
  "http://evilwiki.localhost:3000/",
  "http://x.wiki.localhost:3000/",
  "http://wiki.localhost:8443/",
  "http://wiki.localhost/",
  "https://wiki.localhost:3000/",
  "ftp://wiki.localhost:3000/",
  "//wiki.localhost:3000/n/a",
  "//evil.example",
  "///evil.example",
  "/\\evil.example",
  "/\\/evil.example",
  "\\\\evil.example",
  "http:\\\\wiki.localhost:3000/",
  "http://wiki.localhost:3000\\@evil.example/",
  "http://wiki.localhost:3000/\\evil.example",
  "javascript:alert(1)",
  "JaVaScRiPt:alert(1)",
  "javascript://wiki.localhost:3000/%0aalert(1)",
  "data:text/html,x",
  "http://wiki.localhost:3000@evil.example/",
  "http://wiki.localhost:3000:pass@evil.example/",
  "http://evil.example@wiki.localhost:3000/",
  "http://wiki.localhost:3000\t.evil.example/",
  "http://wiki.localhost:3000/\n/evil.example",
  "/\t/evil.example",
  "\t//evil.example",
  " //evil.example",
  "http://wiki.localhost:3000//evil.example",
  "/..//evil.example",
  "/n/a",
  "evil.example",
  "@evil.example",
];

describe("контроль: тест видит уход со страницы и стоит на основном сайте", () => {
  it("jsdom сообщает о попытке перехода через location.replace", () => {
    window.location.replace("https://evil.example/");
    expect(navigationAttempts).toHaveLength(1);
  });

  it("тестовый хост — основной сайт, не вики", () => {
    expect(window.location.origin).toBe("http://localhost:3000");
    expect(isWikiHost()).toBe(false);
  });
});

describe("вход на сайте с возвратом на вики", () => {
  it("гость входит и одним явным переходом возвращается на свою страницу вики", async () => {
    const user = userEvent.setup();
    openLogin(`${WIKI}/n/moi-domashnii-sait/grabli?x=1`);

    await user.type(await screen.findByLabelText("Имя пользователя", {}, ASYNC), "nikita");
    await user.type(screen.getByLabelText("Пароль"), "secret123");
    expect(navigationAttempts).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("link", { name: "Перейти в вики" }, ASYNC)).toHaveAttribute(
      "href",
      `${WIKI}/n/moi-domashnii-sait/grabli?x=1`
    );
    await waitFor(() => expect(navigationAttempts).toHaveLength(1), ASYNC);
    await pause(50);
    expect(navigationAttempts).toHaveLength(1);
    // Роутер сайта на главную не уводил
    expect(window.location.pathname).toBe("/login");
  });

  it("уже вошедший сразу возвращается на вики", async () => {
    loggedIn = true;
    openLogin(`${WIKI}/search?q=traefik#top`);

    expect(await screen.findByRole("link", { name: "Перейти в вики" }, ASYNC)).toHaveAttribute(
      "href",
      `${WIKI}/search?q=traefik#top`
    );
    await waitFor(() => expect(navigationAttempts).toHaveLength(1), ASYNC);
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
  });
});

describe("вредный адрес возврата игнорируется", () => {
  it.each(BAD_NEXT)("уже вошедший, next=%j — обычная страница входа, ухода нет", async (next) => {
    loggedIn = true;
    openLogin(next);

    expect(await screen.findByLabelText("Пароль", {}, ASYNC)).toBeInTheDocument();
    await pause(50);
    expect(navigationAttempts).toEqual([]);
    expect(window.location.host).toBe("localhost:3000");
    expect(window.location.pathname).toBe("/login");
    expect(screen.queryByRole("link", { name: "Перейти в вики" })).not.toBeInTheDocument();
  });

  it.each([
    "https://evil.example/",
    "//evil.example",
    "/\\evil.example",
    "http://wiki.localhost:3000.evil.example/",
    "http://wiki.localhost:3000@evil.example/",
    "javascript:alert(1)",
    "http://wiki.localhost:8443/",
  ])("вход с next=%j — обычная главная сайта, ухода нет", async (next) => {
    const user = userEvent.setup();
    openLogin(next);

    await user.type(await screen.findByLabelText("Имя пользователя", {}, ASYNC), "nikita");
    await user.type(screen.getByLabelText("Пароль"), "secret123");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => expect(window.location.pathname).toBe("/"), ASYNC);
    await pause(50);
    expect(window.location.search).toBe("");
    expect(navigationAttempts).toEqual([]);
    expect(window.location.host).toBe("localhost:3000");
  });
});
