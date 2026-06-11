import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChangePasswordDialog } from "./ChangePasswordDialog";
import { createWrapper, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderDialog(open = true) {
  const onOpenChange = vi.fn();
  const { Wrapper } = createWrapper();
  render(<ChangePasswordDialog open={open} onOpenChange={onOpenChange} />, { wrapper: Wrapper });
  return { onOpenChange };
}

async function fillForm(user: ReturnType<typeof userEvent.setup>, confirm = "newpass123") {
  await user.type(screen.getByLabelText("Текущий пароль"), "oldpass123");
  await user.type(screen.getByLabelText("Новый пароль"), "newpass123");
  await user.type(screen.getByLabelText("Подтверждение"), confirm);
}

describe("ChangePasswordDialog", () => {
  it("не рендерит содержимое в закрытом состоянии", () => {
    renderDialog(false);

    expect(screen.queryByText("Сменить пароль")).not.toBeInTheDocument();
  });

  it("показывает локальную ошибку при несовпадении паролей и не зовёт API", async () => {
    const user = userEvent.setup();
    renderDialog();

    await fillForm(user, "другой123");
    await user.click(screen.getByRole("button", { name: "Сменить пароль" }));

    expect(screen.getByText("Пароли не совпадают")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("при успехе чистит поля и закрывает диалог", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ body: {} }));
    const { onOpenChange } = renderDialog();

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Сменить пароль" }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/change-password");
    expect(JSON.parse(options.body as string)).toEqual({
      old_password: "oldpass123",
      new_password: "newpass123",
    });
  });

  it("показывает 'Неверный текущий пароль' при 401", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 401, body: { detail: "Wrong" } })
    );
    renderDialog();

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Сменить пароль" }));

    await waitFor(() => expect(screen.getByText("Неверный текущий пароль")).toBeInTheDocument());
  });

  it("показывает сообщение сервера при другой ошибке", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 422, body: { detail: "Пароль слишком простой" } })
    );
    renderDialog();

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Сменить пароль" }));

    await waitFor(() => expect(screen.getByText("Пароль слишком простой")).toBeInTheDocument());
  });
});
