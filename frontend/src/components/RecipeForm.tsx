import { type FormEvent, useState } from "react";
import { type Ingredient } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { GlyphPicker } from "@/components/GlyphPicker";
import { IngredientsEditor } from "@/components/IngredientsEditor";
import {
  type IngredientField,
  type IngredientRow,
  type IngredientRowErrors,
  createIngredientRow,
} from "@/components/ingredient-rows";

interface FormErrors {
  title?: boolean;
  description?: boolean;
  servings?: boolean;
  ingredients?: boolean;
  rows?: Record<number, IngredientRowErrors>;
}

interface Props {
  initialData?: {
    title: string;
    description: string;
    servings: number;
    ingredients: Ingredient[];
    glyph_kind?: string | null;
    glyph_color?: string | null;
  };
  onSubmit: (data: {
    title: string;
    description: string;
    servings: number;
    ingredients: { name: string; amount: string; unit: string | null }[];
    glyph_kind: string | null;
    glyph_color: string | null;
  }) => void;
  isPending: boolean;
  submitLabel: string;
}

function isNumericAmount(value: string): boolean {
  const normalized = value.replace(",", ".");
  return normalized !== "" && Number.isFinite(Number(normalized));
}

export function RecipeForm({ initialData, onSubmit, isPending, submitLabel }: Readonly<Props>) {
  const [title, setTitle] = useState(initialData?.title ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [servings, setServings] = useState<string>(
    initialData?.servings == null ? "" : String(initialData.servings)
  );
  const [ingredients, setIngredients] = useState<IngredientRow[]>(
    initialData?.ingredients.map((i) =>
      createIngredientRow({ name: i.name, amount: i.amount, unit: i.unit ?? "" })
    ) ?? [createIngredientRow()]
  );
  const [glyphKind, setGlyphKind] = useState<string>(initialData?.glyph_kind ?? "");
  const [glyphColor, setGlyphColor] = useState<string>(initialData?.glyph_color ?? "");
  const [errors, setErrors] = useState<FormErrors>({});
  const [errorMessages, setErrorMessages] = useState<string[]>([]);

  const handleRowRemoved = (index: number) => {
    const newRows = { ...errors.rows };
    delete newRows[index];
    setErrors({ ...errors, rows: newRows });
  };

  const clearError = (key: keyof FormErrors) => {
    if (errors[key]) setErrors({ ...errors, [key]: false });
  };

  const clearRowError = (index: number, field: keyof IngredientRowErrors) => {
    if (errors.rows?.[index]?.[field]) {
      const newRow = { ...errors.rows[index], [field]: false };
      setErrors({ ...errors, rows: { ...errors.rows, [index]: newRow } });
    }
  };

  const handleIngredientFocus = (index: number, field: IngredientField) => {
    if (field === "name") {
      clearError("ingredients");
    } else if (field === "amount") {
      clearError("ingredients");
      clearRowError(index, "amountNotNumeric");
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    const newErrors: FormErrors = { rows: {} };
    const messages: string[] = [];

    if (!title.trim()) {
      newErrors.title = true;
      messages.push("Введите название блюда");
    }
    if (!description.trim()) {
      newErrors.description = true;
      messages.push("Заполните описание рецепта");
    }

    const servingsNum = Number.parseInt(servings, 10);
    if (!servings.trim() || Number.isNaN(servingsNum) || servingsNum < 1 || servingsNum > 50) {
      newErrors.servings = true;
      messages.push("Укажите количество порций");
    }

    let hasValidIngredient = false;
    ingredients.forEach((ing, i) => {
      const rowErr: IngredientRowErrors = {};
      const hasName = ing.name.trim().length > 0;
      const hasAmount = ing.amount.trim().length > 0;
      const hasUnit = ing.unit.trim().length > 0;

      if (hasName && hasAmount) {
        hasValidIngredient = true;
      }

      if (hasUnit && hasAmount && !isNumericAmount(ing.amount.trim())) {
        rowErr.amountNotNumeric = true;
      }

      if (Object.keys(rowErr).length > 0 && newErrors.rows) {
        newErrors.rows[i] = rowErr;
      }
    });

    if (!hasValidIngredient) {
      newErrors.ingredients = true;
      messages.push("Добавьте хотя бы один ингредиент с названием и количеством");
    }

    if (Object.values(newErrors.rows ?? {}).some((r) => r.amountNotNumeric)) {
      messages.push("Если указана единица измерения, в поле «Кол-во» должно быть число");
    }

    setErrors(newErrors);
    setErrorMessages(messages);

    if (
      newErrors.title ||
      newErrors.description ||
      newErrors.servings ||
      newErrors.ingredients ||
      Object.values(newErrors.rows ?? {}).some((r) => r.amountNotNumeric)
    ) {
      return;
    }

    const validIngredients = ingredients
      .filter((i) => i.name.trim() && i.amount.trim())
      .map((i) => ({ name: i.name, amount: i.amount, unit: i.unit || null }));
    onSubmit({
      title,
      description,
      servings: servingsNum,
      ingredients: validIngredients,
      glyph_kind: glyphKind || null,
      glyph_color: glyphColor || null,
    });
  };

  const errorClass = "border-destructive focus-visible:ring-destructive";

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="title">Название</Label>
          <Input
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onFocus={() => clearError("title")}
            maxLength={200}
            placeholder="Введите название блюда"
            className={errors.title ? errorClass : ""}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="servings">Порций</Label>
          <Input
            id="servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(e.target.value)}
            onFocus={() => clearError("servings")}
            min={1}
            max={50}
            placeholder="Сколько порций получится"
            className={errors.servings ? errorClass : ""}
          />
        </div>
        <GlyphPicker
          title={title}
          kind={glyphKind}
          color={glyphColor}
          onKindChange={setGlyphKind}
          onColorChange={setGlyphColor}
        />
      </div>

      <Separator />

      <IngredientsEditor
        value={ingredients}
        onChange={setIngredients}
        errors={errors.rows}
        onFieldFocus={handleIngredientFocus}
        onRowRemoved={handleRowRemoved}
      />

      <Separator />

      <div className="space-y-2">
        <Label htmlFor="description">Описание / Как готовить</Label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onFocus={() => clearError("description")}
          rows={10}
          className={`flex w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${
            errors.description
              ? "border-destructive focus-visible:ring-destructive"
              : "border-input focus-visible:ring-ring"
          }`}
          placeholder="Опишите процесс приготовления..."
        />
      </div>

      <div className="space-y-2">
        <Button type="submit" className="w-full" disabled={isPending}>
          {isPending ? "Сохранение..." : submitLabel}
        </Button>
        {errorMessages.length > 0 && (
          <ul className="text-sm text-destructive space-y-1">
            {errorMessages.map((msg) => (
              <li key={msg}>• {msg}</li>
            ))}
          </ul>
        )}
      </div>
    </form>
  );
}
