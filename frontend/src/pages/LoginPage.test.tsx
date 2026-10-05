import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";
import { redirectTo } from "@/lib/redirect";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

// Переход на другой origin (возврат на вики) jsdom выполнить не может — перехватываем
vi.mock("@/lib/redirect", () => ({ redirectTo: vi.fn() }));

const fetchMock = vi.fn();
const redirectMock = vi.mocked(redirectTo);

// Страница входа в тестах открыта на http://localhost:3000 — вики этого сайта:
const WIKI = `http://wiki.${window.location.host}`;
const unauthorized = { ok: false, status: 401, body: { detail: "Not authenticated" } };

beforeEach(() => {
  redirectMock.mockReset();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage(route = "/login") {
  const { Wrapper } = createWrapper({ route });
  return render(<LoginPage />, { wrapper: Wrapper });
}

const withNext = (next: string) => `/login?next=${encodeURIComponent(next)}`;

/** Гость входит: /me отвечает 401 до входа и пользователем после. */
function mockLoginFlow() {
  let loggedIn = false;
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname;
    if (path === "/api/auth/login" && init?.method === "POST") {
      loggedIn = true;
      return Promise.resolve(mockResponse({ body: { message: "ok" } }));
    }
    if (path === "/api/auth/me") {
      return Promise.resolve(mockResponse(loggedIn ? { body: makeUser() } : unauthorized));
    }
    return Promise.resolve(mockResponse({ ok: false, status: 404, body: {} }));
  });
}

function calledPaths(): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname);
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Адреса возврата, которые страница входа обязана проигнорировать. */
const BAD_NEXT = [
  "https://evil.example/",
  "http://evil.example/",
  "http://wiki.localhost:3000.evil.example/",
  "http://wiki.localhost.evil.example:3000/",
  "http://evilwiki.localhost:3000/",
  "http://x.wiki.localhost:3000/",
  "http://localhost:3000/n/a",
  "http://wiki.localhost:8443/",
  "http://wiki.localhost/",
  "https://wiki.localhost:3000/",
  "//wiki.localhost:3000/n/a",
  "//evil.example",
  "/\\evil.example",
  "\\\\evil.example",
  "http:\\\\wiki.localhost:3000/",
  "http://wiki.localhost:3000\\@evil.example/",
  "javascript:alert(1)",
  "data:text/html,x",
  "http://wiki.localhost:3000@evil.example/",
  "http://evil.example@wiki.localhost:3000/",
  "http://user:pass@wiki.localhost:3000/",
  "http://wiki.localhost:3000\t.evil.example/",
  "http://wiki.localhost:3000/\n/evil.example",
  " http://wiki.localhost:3000/",
  "http://wiki.localhost:3000//evil.example",
  "/n/a",
  "/recipes",
];

async function submitForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Имя пользователя"), "nikita");
  await user.type(screen.getByLabelText("Пароль"), "secret123");
  await user.click(screen.getByRole("button", { name: "Войти" }));
}

describe("LoginPage", () => {
  it("успешный вход шлёт логин и ведёт на главную", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/"));
    const loginCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/login")) as [
      string,
      RequestInit,
    ];
    expect(JSON.parse(loginCall[1].body as string)).toEqual({
      username: "nikita",
      password: "secret123",
    });
  });

  it("при 401 показывает 'Неверный логин или пароль'", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 401, body: { detail: "Bad credentials" } })
    );
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Неверный логин или пароль")).toBeInTheDocument());
  });

  it("при другой ошибке показывает сообщение сервера", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 429, body: { detail: "Слишком много попыток" } })
    );
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Слишком много попыток")).toBeInTheDocument());
  });

  it("кнопка гостя ведёт на /recipes без запроса", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Войти как гость" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/recipes");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("без next запрос «кто я» со страницы входа не уходит", async () => {
    renderPage();

    await pause(20);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("есть ссылка на регистрацию", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "Зарегистрироваться" })).toHaveAttribute(
      "href",
      "/register"
    );
  });
});

describe("LoginPage: возврат на вики (?next=)", () => {
  it("после входа возвращает на страницу вики, с которой пришёл гость", async () => {
    const user = userEvent.setup();
    mockLoginFlow();
    renderPage(withNext(`${WIKI}/n/moi-domashnii-sait/grabli?x=1#h`));

    await submitForm(user);

    await waitFor(() => expect(redirectMock).toHaveBeenCalled());
    await pause(30);
    expect(redirectMock).toHaveBeenCalledTimes(1);
    expect(redirectMock).toHaveBeenCalledWith(`${WIKI}/n/moi-domashnii-sait/grabli?x=1#h`);
    // Роутер сайта при этом никуда не уходит: переход на вики — не его дело
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it("уже вошедшего сразу возвращает на вики, форма не показывается", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser({ role: "admin" }) }));
    renderPage(withNext(`${WIKI}/search?q=traefik`));

    await waitFor(() => expect(redirectMock).toHaveBeenCalledWith(`${WIKI}/search?q=traefik`));
    expect(redirectMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Перейти в вики" })).toHaveAttribute(
      "href",
      `${WIKI}/search?q=traefik`
    );
    expect(screen.queryByLabelText("Пароль")).not.toBeInTheDocument();
    expect(calledPaths()).toEqual(["/api/auth/me"]);
  });

  it("гостю с адресом возврата показывается обычная форма, перехода до входа нет", async () => {
    fetchMock.mockResolvedValue(mockResponse(unauthorized));
    renderPage(withNext(`${WIKI}/n/a`));

    await waitFor(() => expect(calledPaths()).toEqual(["/api/auth/me"]));
    await pause(20);
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("неверный пароль: остаёмся на входе, на вики не уходим", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse(unauthorized));
    renderPage(withNext(`${WIKI}/n/a`));

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Неверный логин или пароль")).toBeInTheDocument());
    expect(redirectMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it.each(BAD_NEXT)(
    "вредный next=%j: после входа — обычная главная, без перехода наружу",
    async (next) => {
      const user = userEvent.setup();
      mockLoginFlow();
      renderPage(withNext(next));

      await submitForm(user);

      await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/"));
      expect(redirectMock).not.toHaveBeenCalled();
    }
  );

  it.each(BAD_NEXT)("вредный next=%j: уже вошедшего никуда не уводит", async (next) => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser({ role: "admin" }) }));
    renderPage(withNext(next));

    await pause(30);
    expect(redirectMock).not.toHaveBeenCalled();
    // Адрес возврата не принят — обычная страница входа, «кто я» даже не спрашиваем
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Перейти в вики" })).not.toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });
});
