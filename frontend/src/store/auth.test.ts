import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./auth";
import { makeUser } from "@/test/utils";

beforeEach(() => {
  useAuthStore.setState({ user: null });
});

describe("useAuthStore", () => {
  it("по умолчанию пользователь отсутствует", () => {
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("setUser сохраняет пользователя", () => {
    const user = makeUser();

    useAuthStore.getState().setUser(user);

    expect(useAuthStore.getState().user).toEqual(user);
  });

  it("clearUser очищает пользователя", () => {
    useAuthStore.getState().setUser(makeUser());

    useAuthStore.getState().clearUser();

    expect(useAuthStore.getState().user).toBeNull();
  });
});
