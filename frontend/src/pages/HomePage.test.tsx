import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { HomePage } from "./HomePage";
import { useAuthStore } from "@/store/auth";
import { createWrapper, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 404, body: {} }));
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const { Wrapper } = createWrapper();
  return render(<HomePage />, { wrapper: Wrapper });
}

describe("HomePage", () => {
  it("гостю показывает приветствие и ссылки на рецепты и вход", () => {
    renderPage();

    expect(screen.getByText("Семейная страница Волковых")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Смотреть рецепты" })).toHaveAttribute(
      "href",
      "/recipes"
    );
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login");
    expect(screen.queryByText(/Привет/)).not.toBeInTheDocument();
  });

  it("пользователю показывает приветствие по имени и виджет голосования", () => {
    useAuthStore.setState({ user: makeUser({ first_name: "Ник" }) });
    renderPage();

    expect(screen.getByText("Привет, Ник!")).toBeInTheDocument();
    expect(screen.getByText("Голосование за ужин")).toBeInTheDocument();
  });

  it("без имени приветствует по username", () => {
    useAuthStore.setState({ user: makeUser({ first_name: null, username: "wolf" }) });
    renderPage();

    expect(screen.getByText("Привет, wolf!")).toBeInTheDocument();
  });
});
