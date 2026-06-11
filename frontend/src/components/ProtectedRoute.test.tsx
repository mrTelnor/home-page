import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { ProtectedRoute } from "./ProtectedRoute";
import { AuthAwareRoute } from "./AuthAwareRoute";
import { useAuthStore } from "@/store/auth";
import { createQueryClient, makeUser, mockResponse } from "@/test/utils";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  useAuthStore.setState({ user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderProtected() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={["/secret"]}>
        <Routes>
          <Route path="/login" element={<p>Страница входа</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<p>Секретная страница</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProtectedRoute", () => {
  it("показывает индикатор загрузки, пока статус не известен", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderProtected();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("рендерит вложенный маршрут для авторизованного", async () => {
    fetchMock.mockResolvedValue(mockResponse({ body: makeUser() }));
    renderProtected();

    await waitFor(() => expect(screen.getByText("Секретная страница")).toBeInTheDocument());
  });

  it("редиректит на /login без авторизации", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
    renderProtected();

    await waitFor(() => expect(screen.getByText("Страница входа")).toBeInTheDocument());
  });
});

describe("AuthAwareRoute", () => {
  function renderAuthAware() {
    return render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route element={<AuthAwareRoute />}>
              <Route path="/" element={<p>Открытая страница</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  it("показывает индикатор загрузки", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    renderAuthAware();

    expect(screen.getByText("Загрузка...")).toBeInTheDocument();
  });

  it("рендерит контент даже без авторизации", async () => {
    fetchMock.mockResolvedValue(mockResponse({ ok: false, status: 401, body: {} }));
    renderAuthAware();

    await waitFor(() => expect(screen.getByText("Открытая страница")).toBeInTheDocument());
  });
});
