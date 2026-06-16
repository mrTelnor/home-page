import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./Layout";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeMenu, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
});

function renderLayout(route = "/") {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="*" element={<p>Контент страницы</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Layout", () => {
  it("для гостя показывает кнопку входа и не показывает меню", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderLayout();

    expect(screen.getByRole("link", { name: "Войти" })).toBeInTheDocument();
    expect(screen.queryByText("Выйти")).not.toBeInTheDocument();
    expect(screen.queryByText("Открыть книгу")).not.toBeInTheDocument();
    expect(screen.getByText("Контент страницы")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("для пользователя показывает навигацию, профиль и выход", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    useAuthStore.setState({ user: makeUser({ username: "nikita" }) });
    renderLayout();

    expect(screen.getByText("Меню дня")).toBeInTheDocument();
    expect(screen.getByText("Добавить рецепт")).toBeInTheDocument();
    expect(screen.getByText("Открыть книгу")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Профиль" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "nikita" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("на мобиле бургер раскрывает навигацию, у гостя бургера нет", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    useAuthStore.setState({ user: makeUser() });
    renderLayout();

    // панель скрыта до клика
    expect(screen.queryByTestId("mobile-nav")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Меню" }));

    const panel = screen.getByTestId("mobile-nav");
    expect(within(panel).getByText("Открыть книгу")).toBeInTheDocument();
    expect(within(panel).getByText("Добавить рецепт")).toBeInTheDocument();

    // клик по ссылке закрывает панель
    await user.click(within(panel).getByText("Открыть книгу"));
    expect(screen.queryByTestId("mobile-nav")).not.toBeInTheDocument();
  });

  it("у гостя нет кнопки мобильного меню", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderLayout();
    expect(screen.queryByRole("button", { name: "Меню" })).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("подпись пункта меню зависит от статуса меню дня", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeMenu({ status: "voting" }) }));
    useAuthStore.setState({ user: makeUser() });
    renderLayout();

    await waitFor(() => expect(screen.getByText("Проголосовать")).toBeInTheDocument());
  });

  it("в статусе collecting предлагает рецепт", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeMenu({ status: "collecting" }) }));
    useAuthStore.setState({ user: makeUser() });
    renderLayout();

    await waitFor(() => expect(screen.getByText("Предложить рецепт")).toBeInTheDocument());
  });

  it("переключатель темы меняет тему", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderLayout();

    await user.click(screen.getByRole("button", { name: "Тёмная тема" }));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("button", { name: "Светлая тема" })).toBeInTheDocument();
  });

  it("кнопка 'Выйти' разлогинивает", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ status: 204, body: null }));
    useAuthStore.setState({ user: makeUser() });
    renderLayout();

    await user.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(useAuthStore.getState().user).toBeNull());
    const logoutCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/logout"));
    expect(logoutCall).toBeDefined();
  });

  it("кнопка 'Назад' заблокирована на главной", () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderLayout("/");

    expect(screen.getByRole("button", { name: /Назад/ })).toBeDisabled();
  });

  it("кнопка 'Назад' активна не на главной и возвращает по истории", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
    renderLayout("/recipes");

    const backButton = screen.getByRole("button", { name: /Назад/ });
    expect(backButton).toBeEnabled();

    await user.click(backButton);

    // история из одной записи — просто не падает
    expect(screen.getByText("Контент страницы")).toBeInTheDocument();
  });
});
