import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { createQueryClient, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>Экран входа</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("битый токен → сообщение об ошибке", async () => {
  fetchMock.mockResolvedValue(mockResponse({ body: { valid: false } }));
  renderAt("/reset-password?token=bad");
  await waitFor(() => expect(screen.getByText(/недействительна|устарела/i)).toBeInTheDocument());
});

it("валидный токен → сабмит → переход на вход", async () => {
  fetchMock
    .mockResolvedValueOnce(mockResponse({ body: { valid: true } })) // validate
    .mockResolvedValueOnce(mockResponse({ body: { status: "ok" } })); // confirm
  renderAt("/reset-password?token=good");
  const pwd = await screen.findByLabelText("Новый пароль");
  await userEvent.type(pwd, "brandnew123");
  await userEvent.type(screen.getByLabelText("Повторите пароль"), "brandnew123");
  await userEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
  await waitFor(() => expect(screen.getByText("Экран входа")).toBeInTheDocument());
});
