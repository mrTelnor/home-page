import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfilePage } from "./ProfilePage";
import { useAuthStore } from "@/store/auth";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderPage() {
  const { Wrapper } = createWrapper({ route: "/profile" });
  return render(<ProfilePage />, { wrapper: Wrapper });
}

describe("ProfilePage", () => {
  it("ничего не рендерит без пользователя", () => {
    const { container } = renderPage();

    expect(container.querySelector("h1")).toBeNull();
  });

  it("показывает данные аккаунта", () => {
    useAuthStore.setState({ user: makeUser({ username: "nikita", role: "admin" }) });
    renderPage();

    expect(screen.getByText("Личный кабинет")).toBeInTheDocument();
    expect(screen.getByText("nikita")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("Зарегистрирован")).toBeInTheDocument();
  });

  it("без привязки показывает кнопку входа через Telegram", () => {
    useAuthStore.setState({ user: makeUser({ tg_id: null }) });
    renderPage();

    expect(screen.getByText(/Привяжите Telegram/)).toBeInTheDocument();
    expect(screen.queryByText("Отвязать Telegram")).not.toBeInTheDocument();
  });

  it("с привязкой показывает ID и отвязывает после подтверждения", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    useAuthStore.setState({ user: makeUser({ tg_id: 12345 }) });
    renderPage();

    expect(screen.getByText("Привязан")).toBeInTheDocument();
    expect(screen.getByText("ID: 12345")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отвязать Telegram" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect((fetchMock.mock.calls[0] as [string])[0]).toContain("/api/auth/telegram-unlink");
  });

  it("не отвязывает без подтверждения", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    useAuthStore.setState({ user: makeUser({ tg_id: 12345 }) });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Отвязать Telegram" }));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("кнопка 'Сменить пароль' открывает диалог", async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: makeUser() });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Сменить пароль" }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });
});
