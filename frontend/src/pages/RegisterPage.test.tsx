import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegisterPage } from "./RegisterPage";
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
  const { Wrapper } = createWrapper({ route: "/register" });
  return render(<RegisterPage />, { wrapper: Wrapper });
}

async function submitForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Имя пользователя"), "newbie");
  await user.type(screen.getByLabelText("Пароль"), "secret123");
  await user.type(screen.getByLabelText("Инвайт-код"), "WOLF");
  await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));
}

describe("RegisterPage", () => {
  it("успешная регистрация шлёт данные и ведёт на /login", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/login"));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/register");
    expect(JSON.parse(options.body as string)).toEqual({
      username: "newbie",
      password: "secret123",
      invite_code: "WOLF",
    });
  });

  it("при 403 показывает 'Неверный инвайт-код'", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 403, body: { detail: "Forbidden" } })
    );
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Неверный инвайт-код")).toBeInTheDocument());
  });

  it("при 409 показывает 'Имя пользователя занято'", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 409, body: { detail: "Conflict" } })
    );
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Имя пользователя занято")).toBeInTheDocument());
  });

  it("при другой ошибке показывает сообщение сервера", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 422, body: { detail: "Пароль слишком короткий" } })
    );
    renderPage();

    await submitForm(user);

    await waitFor(() => expect(screen.getByText("Пароль слишком короткий")).toBeInTheDocument());
  });

  it("есть ссылка на вход", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login");
  });
});
