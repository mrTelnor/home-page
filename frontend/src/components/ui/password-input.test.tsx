import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PasswordInput } from "./password-input";

it("по умолчанию скрывает пароль и переключает видимость глазиком", async () => {
  const { container } = render(<PasswordInput defaultValue="secret" />);
  const input = container.querySelector("input")!;

  expect(input.type).toBe("password");

  await userEvent.click(screen.getByRole("button", { name: "Показать пароль" }));
  expect(input.type).toBe("text");

  await userEvent.click(screen.getByRole("button", { name: "Скрыть пароль" }));
  expect(input.type).toBe("password");
});
