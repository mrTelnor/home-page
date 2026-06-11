import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const { Wrapper } = createWrapper({ route: "/login" });
  return render(<LoginPage />, { wrapper: Wrapper });
}

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

  it("есть ссылка на регистрацию", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "Зарегистрироваться" })).toHaveAttribute(
      "href",
      "/register"
    );
  });
});
