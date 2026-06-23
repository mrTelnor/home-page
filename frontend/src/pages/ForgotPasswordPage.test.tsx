import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { createQueryClient, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("показывает успех при status sent", async () => {
  fetchMock.mockResolvedValue(mockResponse({ body: { status: "sent" } }));
  renderPage();
  await userEvent.type(screen.getByLabelText("Логин или email"), "someone");
  await userEvent.click(screen.getByRole("button", { name: "Отправить ссылку" }));
  await waitFor(() => expect(screen.getByText(/отправили инструкции/i)).toBeInTheDocument());
});

it("при choose показывает кнопки каналов и шлёт повторный запрос", async () => {
  fetchMock
    .mockResolvedValueOnce(mockResponse({ body: { status: "choose", channels: ["telegram", "email"] } }))
    .mockResolvedValueOnce(mockResponse({ body: { status: "sent" } }));
  renderPage();
  await userEvent.type(screen.getByLabelText("Логин или email"), "both");
  await userEvent.click(screen.getByRole("button", { name: "Отправить ссылку" }));
  await screen.findByRole("button", { name: /Telegram/i });
  await userEvent.click(screen.getByRole("button", { name: /Telegram/i }));
  await waitFor(() => expect(screen.getByText(/отправили инструкции/i)).toBeInTheDocument());
});

it("при no_channels подсказывает обратиться к админу", async () => {
  fetchMock.mockResolvedValue(mockResponse({ body: { status: "no_channels" } }));
  renderPage();
  await userEvent.type(screen.getByLabelText("Логин или email"), "lonely");
  await userEvent.click(screen.getByRole("button", { name: "Отправить ссылку" }));
  await waitFor(() => expect(screen.getByText(/администратору/i)).toBeInTheDocument());
});
