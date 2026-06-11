import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { TelegramLoginButton } from "./TelegramLoginButton";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";
import { type TelegramAuthData } from "@/hooks/useProfile";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.onTelegramAuth = undefined;
});

const tgData: TelegramAuthData = {
  id: 123,
  first_name: "Никита",
  auth_date: 1700000000,
  hash: "abc",
};

function renderButton() {
  const { Wrapper } = createWrapper();
  return render(<TelegramLoginButton />, { wrapper: Wrapper });
}

describe("TelegramLoginButton", () => {
  it("вставляет скрипт виджета Telegram с нужными data-атрибутами", () => {
    const { container } = renderButton();

    const script = container.querySelector("script");
    expect(script).not.toBeNull();
    expect(script?.src).toContain("telegram.org/js/telegram-widget.js");
    expect(script?.dataset.telegramLogin).toBeTruthy();
    expect(script?.dataset.onauth).toBe("onTelegramAuth(user)");
    expect(script?.dataset.requestAccess).toBe("write");
  });

  it("регистрирует глобальный колбэк, который шлёт verify-запрос", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser({ tg_id: 123 }) }));
    renderButton();

    expect(globalThis.onTelegramAuth).toBeTypeOf("function");

    act(() => {
      globalThis.onTelegramAuth?.(tgData);
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/auth/telegram-verify");
    expect(options.body).toBe(JSON.stringify(tgData));
  });

  it("показывает сообщение об ошибке, если привязка не удалась", async () => {
    fetchMock.mockResolvedValue(
      mockResponse({ ok: false, status: 400, body: { detail: "Bad hash" } })
    );
    renderButton();

    act(() => {
      globalThis.onTelegramAuth?.(tgData);
    });

    await waitFor(() =>
      expect(screen.getByText("Ошибка привязки. Попробуйте ещё раз.")).toBeInTheDocument()
    );
  });

  it("снимает глобальный колбэк при размонтировании", () => {
    const { unmount } = renderButton();

    expect(globalThis.onTelegramAuth).toBeTypeOf("function");

    unmount();

    expect(globalThis.onTelegramAuth).toBeUndefined();
  });
});
