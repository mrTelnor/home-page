import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Avatar, AvatarStack } from "./Avatar";

const user = { id: "u1", first_name: "Никита", username: "nikita" };

describe("Avatar", () => {
  it("показывает первую букву имени и title", () => {
    render(<Avatar user={user} />);

    expect(screen.getByText("Н")).toBeInTheDocument();
    expect(screen.getByTitle("Никита")).toBeInTheDocument();
  });

  it("падает обратно на username, если имени нет", () => {
    render(<Avatar user={{ id: "u2", first_name: null, username: "wolf" }} />);

    expect(screen.getByText("W")).toBeInTheDocument();
    expect(screen.getByTitle("wolf")).toBeInTheDocument();
  });

  it("показывает '?', если ни имени, ни username нет", () => {
    render(<Avatar user={{ id: "u3", username: "" }} />);

    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("рисует кольцо при ring", () => {
    render(<Avatar user={user} ring size={40} />);

    const el = screen.getByTitle("Никита");
    expect(el.style.boxShadow).not.toBe("none");
    expect(el.style.width).toBe("40px");
  });
});

describe("AvatarStack", () => {
  const users = [
    { id: "a", first_name: "Аня", username: "anya" },
    { id: "b", first_name: "Боря", username: "borya" },
    { id: "c", first_name: "Вера", username: "vera" },
    { id: "d", first_name: "Гена", username: "gena" },
    { id: "e", first_name: "Дима", username: "dima" },
    { id: "f", first_name: "Ева", username: "eva" },
  ];

  it("показывает максимум max аватарок и счётчик остальных", () => {
    render(<AvatarStack users={users} max={4} />);

    expect(screen.getByText("А")).toBeInTheDocument();
    expect(screen.getByText("Г")).toBeInTheDocument();
    expect(screen.queryByText("Д")).not.toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("не показывает счётчик, если все поместились", () => {
    render(<AvatarStack users={users.slice(0, 2)} />);

    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });
});
