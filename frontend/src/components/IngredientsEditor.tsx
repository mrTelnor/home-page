import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
  type IngredientField,
  type IngredientRow,
  type IngredientRowErrors,
  createIngredientRow,
} from "@/components/ingredient-rows";

interface Props {
  value: IngredientRow[];
  onChange: (rows: IngredientRow[]) => void;
  errors?: Record<number, IngredientRowErrors>;
  onFieldFocus?: (index: number, field: IngredientField) => void;
  onRowRemoved?: (index: number) => void;
}

const errorClass = "border-destructive focus-visible:ring-destructive";

export function IngredientsEditor({
  value,
  onChange,
  errors,
  onFieldFocus,
  onRowRemoved,
}: Readonly<Props>) {
  const addRow = () => {
    onChange([...value, createIngredientRow()]);
  };

  const removeRow = (index: number) => {
    if (!confirm("Удалить ингредиент?")) return;
    onChange(value.filter((_, i) => i !== index));
    onRowRemoved?.(index);
  };

  const updateRow = (index: number, field: IngredientField, fieldValue: string) => {
    const updated = [...value];
    updated[index] = { ...updated[index], [field]: fieldValue };
    onChange(updated);
  };

  return (
    <div className="space-y-4">
      <Label>Ингредиенты</Label>
      {value.map((ing, index) => {
        const rowErr = errors?.[index] ?? {};
        return (
          <Card key={ing.id}>
            <CardContent className="pt-4">
              <div className="flex gap-2 items-end">
                <div className="flex-1 space-y-1">
                  <Label className="text-xs">Название</Label>
                  <Input
                    value={ing.name}
                    onChange={(e) => updateRow(index, "name", e.target.value)}
                    onFocus={() => onFieldFocus?.(index, "name")}
                  />
                </div>
                <div className="w-24 space-y-1">
                  <Label className="text-xs">Кол-во</Label>
                  <Input
                    value={ing.amount}
                    onChange={(e) => updateRow(index, "amount", e.target.value)}
                    onFocus={() => onFieldFocus?.(index, "amount")}
                    className={rowErr.amountNotNumeric ? errorClass : ""}
                  />
                </div>
                <div className="w-20 space-y-1">
                  <Label className="text-xs">Ед.</Label>
                  <Input
                    value={ing.unit}
                    onChange={(e) => updateRow(index, "unit", e.target.value)}
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRow(index)}
                  disabled={value.length <= 1}
                  className="text-destructive hover:text-destructive"
                >
                  ✕
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
      <Button type="button" variant="outline" size="sm" onClick={addRow} className="w-full">
        + Добавить ингредиент
      </Button>
      <p className="text-xs text-muted-foreground">
        Для ингредиентов без точной меры впишите "по вкусу" в поле «Кол-во», поле «Ед.» оставьте
        пустым.
      </p>
    </div>
  );
}
