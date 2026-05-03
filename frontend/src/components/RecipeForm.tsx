import { type FormEvent, useState } from "react";
import { type Ingredient } from "@/hooks/useRecipes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { FoodGlyph } from "@/components/FoodGlyph";
import { FOOD_KINDS, FOOD_COLORS } from "@/components/food-kinds";

interface IngredientRow {
  id: string;
  name: string;
  amount: string;
  unit: string;
}

let nextRowId = 0;
const newRowId = () => `row-${++nextRowId}`;

interface IngredientErrors {
  name?: boolean;
  amount?: boolean;
  amountNotNumeric?: boolean;
}

interface FormErrors {
  title?: boolean;
  description?: boolean;
  servings?: boolean;
  ingredients?: boolean;
  rows?: Record<number, IngredientErrors>;
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
    initialData?.ingredients.map((i) => ({
      id: newRowId(),
      name: i.name,
      amount: i.amount,
      unit: i.unit ?? "",
    })) ?? [{ id: newRowId(), name: "", amount: "", unit: "" }]
  );
  const [glyphKind, setGlyphKind] = useState<string>(initialData?.glyph_kind ?? "");
  const [glyphColor, setGlyphColor] = useState<string>(initialData?.glyph_color ?? "");
  const [errors, setErrors] = useState<FormErrors>({});
  const [errorMessages, setErrorMessages] = useState<string[]>([]);

  const addIngredient = () => {
    setIngredients([...ingredients, { id: newRowId(), name: "", amount: "", unit: "" }]);
  };

  const removeIngredient = (index: number) => {
    if (!confirm("Удалить ингредиент?")) return;
    setIngredients(ingredients.filter((_, i) => i !== index));
    const newRows = { ...errors.rows };
    delete newRows[index];
    setErrors({ ...errors, rows: newRows });
  };

  const updateIngredient = (index: number, field: keyof IngredientRow, value: string) => {
    const updated = [...ingredients];
    updated[index] = { ...updated[index], [field]: value };
    setIngredients(updated);
  };

  const clearError = (key: keyof FormErrors) => {
    if (errors[key]) setErrors({ ...errors, [key]: false });
  };

  const clearRowError = (index: number, field: keyof IngredientErrors) => {
    if (errors.rows?.[index]?.[field]) {
      const newRow = { ...errors.rows[index], [field]: false };
      setErrors({ ...errors, rows: { ...errors.rows, [index]: newRow } });
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
      const rowErr: IngredientErrors = {};
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
      messages.push('Если указана единица измерения, в поле «Кол-во» должно быть число');
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
        <div className="space-y-2">
          <Label>Иконка</Label>
          <div className="flex flex-wrap items-start gap-4">
            <div className="w-32 shrink-0 overflow-hidden rounded-md border border-border">
              <FoodGlyph title={title} kind={glyphKind || null} color={glyphColor || null} />
            </div>
            <div className="flex-1 min-w-[200px] space-y-2">
              <div className="space-y-1">
                <Label htmlFor="glyph-kind" className="text-xs">Тип</Label>
                <select
                  id="glyph-kind"
                  value={glyphKind}
                  onChange={(e) => setGlyphKind(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">— Авто (по названию) —</option>
                  {FOOD_KINDS.map((k) => (
                    <option key={k.id} value={k.id}>{k.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Цвет</Label>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setGlyphColor("")}
                    aria-label="Авто-цвет"
                    title="Авто (по названию)"
                    className={`h-7 w-7 rounded-full border-2 text-xs ${
                      glyphColor === "" ? "border-foreground" : "border-border"
                    }`}
                  >
                    ↺
                  </button>
                  {(Object.keys(FOOD_COLORS) as Array<keyof typeof FOOD_COLORS>).map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setGlyphColor(c)}
                      aria-label={c}
                      title={c}
                      style={{ background: FOOD_COLORS[c].dk }}
                      className={`h-7 w-7 rounded-full border-2 ${
                        glyphColor === c ? "border-foreground" : "border-transparent"
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <Label>Ингредиенты</Label>
        {ingredients.map((ing, index) => {
          const rowErr = errors.rows?.[index] ?? {};
          return (
            <Card key={ing.id}>
              <CardContent className="pt-4">
                <div className="flex gap-2 items-end">
                  <div className="flex-1 space-y-1">
                    <Label className="text-xs">Название</Label>
                    <Input
                      value={ing.name}
                      onChange={(e) => updateIngredient(index, "name", e.target.value)}
                      onFocus={() => clearError("ingredients")}
                    />
                  </div>
                  <div className="w-24 space-y-1">
                    <Label className="text-xs">Кол-во</Label>
                    <Input
                      value={ing.amount}
                      onChange={(e) => updateIngredient(index, "amount", e.target.value)}
                      onFocus={() => {
                        clearError("ingredients");
                        clearRowError(index, "amountNotNumeric");
                      }}
                      className={rowErr.amountNotNumeric ? errorClass : ""}
                    />
                  </div>
                  <div className="w-20 space-y-1">
                    <Label className="text-xs">Ед.</Label>
                    <Input
                      value={ing.unit}
                      onChange={(e) => updateIngredient(index, "unit", e.target.value)}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeIngredient(index)}
                    disabled={ingredients.length <= 1}
                    className="text-destructive hover:text-destructive"
                  >
                    ✕
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addIngredient}
          className="w-full"
        >
          + Добавить ингредиент
        </Button>
        <p className="text-xs text-muted-foreground">
          Для ингредиентов без точной меры впишите "по вкусу" в поле «Кол-во»,
          поле «Ед.» оставьте пустым.
        </p>
      </div>

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
