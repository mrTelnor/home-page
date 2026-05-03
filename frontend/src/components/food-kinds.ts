export const FOOD_COLORS = {
  red:    { bg: "#F6D7CF", fg: "#7A2416", dk: "#B8442A" },
  orange: { bg: "#F7DFC2", fg: "#80441A", dk: "#C48A2A" },
  yellow: { bg: "#F6E9B8", fg: "#6E5412", dk: "#B89028" },
  green:  { bg: "#D8E0BC", fg: "#3F5528", dk: "#6B7A4B" },
  teal:   { bg: "#C2DCD6", fg: "#1F4A42", dk: "#3F7268" },
  blue:   { bg: "#C8D5E2", fg: "#1F3A58", dk: "#3F5E86" },
  purple: { bg: "#DACCE0", fg: "#3F2E4C", dk: "#6E5184" },
  pink:   { bg: "#F0CFD4", fg: "#6E2838", dk: "#A8495F" },
  brown:  { bg: "#DFCBB3", fg: "#48331A", dk: "#7A5A32" },
  cream:  { bg: "#EFE5CE", fg: "#5A4A24", dk: "#8E7538" },
} as const;

export type FoodColor = keyof typeof FOOD_COLORS;

export const FOOD_KINDS = [
  { id: "soup",     label: "Суп" },
  { id: "noodles",  label: "Лапша" },
  { id: "eggs",     label: "Яичница" },
  { id: "pancakes", label: "Блины" },
  { id: "pelmeni",  label: "Пельмени" },
  { id: "pie",      label: "Пирог" },
  { id: "pizza",    label: "Пицца" },
  { id: "salad",    label: "Салат" },
  { id: "steak",    label: "Стейк" },
  { id: "chicken",  label: "Курица" },
  { id: "toast",    label: "Тосты" },
  { id: "roast",    label: "Вырезка" },
  { id: "shashlik", label: "Шашлык" },
  { id: "pot",      label: "Кастрюля" },
  { id: "bread",    label: "Хлеб" },
] as const;

export type FoodKind = typeof FOOD_KINDS[number]["id"];

export function pickPaletteByTitle(title: string) {
  let x = 0;
  for (let i = 0; i < title.length; i++) x = (x * 31 + title.charCodeAt(i)) >>> 0;
  const keys = Object.keys(FOOD_COLORS) as FoodColor[];
  return FOOD_COLORS[keys[x % keys.length]];
}
