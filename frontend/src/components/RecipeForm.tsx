import { type FormEvent, useState } from "react";
import { type Ingredient } from "@/hooks/useRecipes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface IngredientRow {
  name: string;
  amount: string;
  unit: string;
}

interface Props {
  initialData?: {
    title: string;
    description: string;
    servings: number;
    ingredients: Ingredient[];
  };
  onSubmit: (data: {
    title: string;
    description: string;
    servings: number;
    ingredients: { name: string; amount: string; unit: string | null }[];
  }) => void;
  isPending: boolean;
  submitLabel: string;
}

export function RecipeForm({ initialData, onSubmit, isPending, submitLabel }: Props) {
  const [title, setTitle] = useState(initialData?.title ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [servings, setServings] = useState(initialData?.servings ?? 4);
  const [ingredients, setIngredients] = useState<IngredientRow[]>(
    initialData?.ingredients.map((i) => ({
      name: i.name,
      amount: i.amount,
      unit: i.unit ?? "",
    })) ?? [{ name: "", amount: "", unit: "" }]
  );

  const addIngredient = () => {
    setIngredients([...ingredients, { name: "", amount: "", unit: "" }]);
  };

  const removeIngredient = (index: number) => {
    if (!confirm("Удалить ингредиент?")) return;
    setIngredients(ingredients.filter((_, i) => i !== index));
  };

  const updateIngredient = (index: number, field: keyof IngredientRow, value: string) => {
    const updated = [...ingredients];
    updated[index] = { ...updated[index], [field]: value };
    setIngredients(updated);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const validIngredients = ingredients
      .filter((i) => i.name.trim() && i.amount.trim())
      .map((i) => ({ name: i.name, amount: i.amount, unit: i.unit || null }));
    onSubmit({ title, description, servings, ingredients: validIngredients });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="title">Название</Label>
          <Input
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={3}
            maxLength={200}
            placeholder="Борщ"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="servings">Порций</Label>
          <Input
            id="servings"
            type="number"
            value={servings}
            onChange={(e) => setServings(Number(e.target.value))}
            min={1}
            max={50}
          />
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <Label>Ингредиенты</Label>
        {ingredients.map((ing, index) => (
          <Card key={index}>
            <CardContent className="pt-4">
              <div className="flex gap-2 items-end">
                <div className="flex-1 space-y-1">
                  <Label className="text-xs">Название</Label>
                  <Input
                    value={ing.name}
                    onChange={(e) => updateIngredient(index, "name", e.target.value)}
                    required
                  />
                </div>
                <div className="w-24 space-y-1">
                  <Label className="text-xs">Кол-во</Label>
                  <Input
                    value={ing.amount}
                    onChange={(e) => updateIngredient(index, "amount", e.target.value)}
                    required
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
        ))}
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
          rows={10}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          placeholder="Опишите процесс приготовления..."
        />
      </div>

      <Button type="submit" className="w-full" disabled={isPending}>
        {isPending ? "Сохранение..." : submitLabel}
      </Button>
    </form>
  );
}
