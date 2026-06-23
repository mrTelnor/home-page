import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { AdminUsersPage } from "./AdminUsersPage";
import { createQueryClient, mockResponse } from "@/test/utils";
import { useAuthStore } from "@/store/auth";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({
    user: {
      id: "a1", username: "admin", role: "admin", created_at: "2026-01-01T00:00:00Z",
      tg_id: null, first_name: null, birthday: null, is_volkov: false, gender: null, email: null,
    },
  });
});
afterEach(async () => {
  vi.unstubAllGlobals();
  await act(async () => {
    useAuthStore.setState({ user: null });
  });
});

function renderPage() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <AdminUsersPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("показывает юзеров и генерирует ссылку", async () => {
  fetchMock
    .mockResolvedValueOnce(
      mockResponse({ body: [{ id: "u1", username: "vasya", first_name: null, role: "user", has_telegram: false, has_email: false }] })
    )
    .mockResolvedValueOnce(
      mockResponse({ body: { link: "https://telnor.ru/reset-password?token=abc", expires_at: "2026-06-20T12:00:00Z" } })
    );
  renderPage();
  await screen.findByText("vasya");
  await userEvent.click(screen.getByRole("button", { name: "Сбросить пароль" }));
  await waitFor(() => {
    expect(screen.getByDisplayValue("https://telnor.ru/reset-password?token=abc")).toBeInTheDocument();
    // pendingId must be cleared (button re-enabled) — ensures onSettled has fully settled
    expect(screen.getByRole("button", { name: "Сбросить пароль" })).not.toBeDisabled();
  });
});
