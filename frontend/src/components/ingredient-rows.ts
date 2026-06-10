// Модель строки редактора ингредиентов (вынесена из IngredientsEditor,
// чтобы компонентный файл экспортировал только компоненты — react-refresh).

export interface IngredientRow {
  id: string;
  name: string;
  amount: string;
  unit: string;
}

export type IngredientField = "name" | "amount" | "unit";

export interface IngredientRowErrors {
  name?: boolean;
  amount?: boolean;
  amountNotNumeric?: boolean;
}

let nextRowId = 0;
const newRowId = () => `row-${++nextRowId}`;

export function createIngredientRow(
  init?: Pick<IngredientRow, "name" | "amount" | "unit">
): IngredientRow {
  return { id: newRowId(), name: "", amount: "", unit: "", ...init };
}
