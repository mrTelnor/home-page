import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecipeForm } from "./RecipeForm";

function renderForm(overrides: Partial<Parameters<typeof RecipeForm>[0]> = {}) {
  const onSubmit = vi.fn();
  render(<RecipeForm onSubmit={onSubmit} isPending={false} submitLabel="Создать" {...overrides} />);
  return { onSubmit };
}

// Карточки ингредиентов (по одной на строку)
function ingredientCards() {
  return document.querySelectorAll('[data-slot="card"]');
}

function ingredientInputs(card: Element) {
  // Внутри карточки три поля: Название, Кол-во, Ед.
  const inputs = within(card as HTMLElement).getAllByRole("textbox");
  return { name: inputs[0], amount: inputs[1], unit: inputs[2] };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("RecipeForm: валидация", () => {
  it("при пустом названии показывает ошибку и не вызывает onSubmit", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(screen.getByText(/Введите название блюда/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("требует описание, порции и хотя бы один ингредиент", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(screen.getByText(/Заполните описание рецепта/)).toBeInTheDocument();
    expect(screen.getByText(/Укажите количество порций/)).toBeInTheDocument();
    expect(
      screen.getByText(/Добавьте хотя бы один ингредиент с названием и количеством/)
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("RecipeForm: строки ингредиентов", () => {
  it("кнопка добавления добавляет строку, удаление убирает (с подтверждением)", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderForm();

    expect(ingredientCards()).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "+ Добавить ингредиент" }));
    expect(ingredientCards()).toHaveLength(2);

    const removeButtons = screen.getAllByRole("button", { name: "✕" });
    expect(removeButtons).toHaveLength(2);
    await user.click(removeButtons[1]);

    expect(window.confirm).toHaveBeenCalledWith("Удалить ингредиент?");
    expect(ingredientCards()).toHaveLength(1);
  });

  it("не удаляет строку, если пользователь отменил подтверждение", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderForm();

    await user.click(screen.getByRole("button", { name: "+ Добавить ингредиент" }));
    expect(ingredientCards()).toHaveLength(2);

    await user.click(screen.getAllByRole("button", { name: "✕" })[1]);
    expect(ingredientCards()).toHaveLength(2);
  });

  it("кнопка удаления заблокирована, пока строка одна", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "✕" })).toBeDisabled();
  });
});

describe("RecipeForm: успешный сабмит", () => {
  it("вызывает onSubmit с собранными данными", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByPlaceholderText("Введите название блюда"), "Борщ");
    await user.type(screen.getByPlaceholderText("Сколько порций получится"), "4");
    await user.type(screen.getByPlaceholderText("Опишите процесс приготовления..."), "Варить час.");

    const row = ingredientInputs(ingredientCards()[0]);
    await user.type(row.name, "Свёкла");
    await user.type(row.amount, "2");
    await user.type(row.unit, "шт");

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      title: "Борщ",
      description: "Варить час.",
      servings: 4,
      ingredients: [{ name: "Свёкла", amount: "2", unit: "шт" }],
      glyph_kind: null,
      glyph_color: null,
    });
  });

  it("включает photo_url в payload при заполнении поля URL фото", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByPlaceholderText("Введите название блюда"), "Фото");
    await user.type(screen.getByPlaceholderText("Сколько порций получится"), "2");
    await user.type(screen.getByPlaceholderText("Опишите процесс приготовления..."), "Готовить.");
    const row = ingredientInputs(ingredientCards()[0]);
    await user.type(row.name, "Соль");
    await user.type(row.amount, "по вкусу");
    await user.type(screen.getByPlaceholderText("https://…"), "https://example.com/p.jpg");

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ photo_url: "https://example.com/p.jpg" })
    );
  });

  it("невалидный URL фото блокирует сабмит", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByPlaceholderText("Введите название блюда"), "Фото");
    await user.type(screen.getByPlaceholderText("Сколько порций получится"), "2");
    await user.type(screen.getByPlaceholderText("Опишите процесс приготовления..."), "Готовить.");
    const row = ingredientInputs(ingredientCards()[0]);
    await user.type(row.name, "Соль");
    await user.type(row.amount, "по вкусу");
    await user.type(screen.getByPlaceholderText("https://…"), "ftp://bad");

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(screen.getByText(/URL фото должен начинаться с http/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("кнопка «Убрать фото» в режиме редактирования шлёт photo_url пустой строкой", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm({
      initialData: {
        title: "Старый",
        description: "Описание",
        servings: 3,
        ingredients: [{ name: "Соль", amount: "по вкусу", unit: null }],
        image_url: "/api/recipe-images/x.jpg",
      },
    });

    await user.click(screen.getByRole("button", { name: /Убрать фото/ }));
    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ photo_url: "" }));
  });

  it("отбрасывает незаполненные строки ингредиентов и шлёт unit: null без единицы", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByPlaceholderText("Введите название блюда"), "Окрошка");
    await user.type(screen.getByPlaceholderText("Сколько порций получится"), "2");
    await user.type(
      screen.getByPlaceholderText("Опишите процесс приготовления..."),
      "Смешать и охладить."
    );

    const row = ingredientInputs(ingredientCards()[0]);
    await user.type(row.name, "Квас");
    await user.type(row.amount, "по вкусу");

    // Пустая строка не должна попасть в результат
    await user.click(screen.getByRole("button", { name: "+ Добавить ингредиент" }));

    await user.click(screen.getByRole("button", { name: "Создать" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0].ingredients).toEqual([
      { name: "Квас", amount: "по вкусу", unit: null },
    ]);
  });
});

describe("RecipeForm: состояние isPending", () => {
  it("блокирует кнопку и меняет подпись на 'Сохранение...'", () => {
    renderForm({ isPending: true });

    const button = screen.getByRole("button", { name: "Сохранение..." });
    expect(button).toBeDisabled();
  });
});
