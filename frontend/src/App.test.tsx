import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { useAuthStore } from "@/store/auth";
import { mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("рендерит главную страницу для гостя", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));

    render(<App />);

    await waitFor(() => expect(screen.getByText("Семейная страница Волковых")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Смотреть рецепты" })).toBeInTheDocument();
  });

  it("показывает 404 на неизвестном пути", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
    window.history.replaceState(null, "", "/no-such-page");

    render(<App />);

    await waitFor(() => expect(screen.getByText("404")).toBeInTheDocument());
  });
});
