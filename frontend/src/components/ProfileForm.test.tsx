import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileForm } from "./ProfileForm";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";
import { type User } from "@/api/types";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const baseUser: User = {
  id: "u1", username: "tester", role: "user", created_at: "2026-01-01T00:00:00Z",
  tg_id: null, first_name: null, birthday: null, is_volkov: false, gender: null, email: null,
};

function renderForm(user: User = makeUser()) {
  const { Wrapper } = createWrapper();
  return render(<ProfileForm user={user} />, { wrapper: Wrapper });
}

describe("ProfileForm", () => {
  it("заполняет поля из данных пользователя", () => {
    renderForm(
      makeUser({ first_name: "Ник", birthday: "1990-05-01", is_volkov: true, gender: "male" })
    );

    expect(screen.getByLabelText("Имя")).toHaveValue("Ник");
    expect(screen.getByLabelText("День рождения")).toHaveValue("1990-05-01");
    expect(screen.getByRole("radio", { name: "Мужской" })).toBeChecked();
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("при женском поле меняется подпись чекбокса", async () => {
    const user = userEvent.setup();
    renderForm();

    expect(screen.getByText("Я Волков")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Женский" }));

    expect(screen.getByText("Я Волкова")).toBeInTheDocument();
  });

  it("сабмит шлёт PATCH с нормализованными данными и показывает 'Сохранено'", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderForm();

    await user.type(screen.getByLabelText("Имя"), "  Ник  ");
    fireEvent.change(screen.getByLabelText("День рождения"), {
      target: { value: "1990-05-01" },
    });
    fireEvent.change(screen.getByLabelText("День рождения"), { target: { value: "" } });
    await user.click(screen.getByRole("radio", { name: "Мужской" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(screen.getByText(/Сохранено/)).toBeInTheDocument());

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/me");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body as string)).toEqual({
      first_name: "Ник",
      birthday: null,
      is_volkov: true,
      gender: "male",
      email: null,
    });
  });

  it("пустые поля уходят как null", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderForm();

    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(
      JSON.parse((fetchMock.mock.calls[0] as [string, RequestInit])[1].body as string)
    ).toEqual({
      first_name: null,
      birthday: null,
      is_volkov: false,
      gender: null,
      email: null,
    });
  });

  it("изменение поля скрывает индикатор 'Сохранено'", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderForm();

    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(screen.getByText(/Сохранено/)).toBeInTheDocument());

    await user.type(screen.getByLabelText("Имя"), "Н");

    expect(screen.queryByText(/Сохранено/)).not.toBeInTheDocument();
  });

  it("сохраняет email", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: { ...baseUser, email: "me@x.com" } }));
    renderForm(baseUser);
    await userEvent.type(screen.getByLabelText("Email"), "me@x.com");
    await userEvent.click(screen.getByRole("button", { name: /Сохранить/ }));
    await waitFor(() => expect(screen.getByText(/Сохранено/)).toBeInTheDocument());

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toMatchObject({ email: "me@x.com" });
  });

  it("показывает ошибку 403 при блокировке смены email", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 403, body: { detail: "Сменить email можно только после 27.06.2026" } })
    );
    renderForm(baseUser);
    await userEvent.type(screen.getByLabelText("Email"), "new@x.com");
    await userEvent.click(screen.getByRole("button", { name: /Сохранить/ }));
    await waitFor(() => expect(screen.getByText(/Сменить email можно только после/)).toBeInTheDocument());
  });
});
