// Общие типы данных API.
// Поля соответствуют ответам backend (backend/app/schemas/*.py).

/** backend/app/schemas/auth.py :: UserResponse */
export interface User {
  id: string;
  username: string;
  role: string;
  created_at: string;
  tg_id: number | null;
  first_name: string | null;
  birthday: string | null;
  is_volkov: boolean;
  gender: "male" | "female" | null;
  email: string | null;
}

/** backend/app/schemas/recipe.py :: IngredientResponse (id отсутствует в запросах) */
export interface Ingredient {
  id?: string;
  name: string;
  amount: string;
  unit: string | null;
}

/** backend/app/schemas/recipe.py :: RecipeResponse */
export interface Recipe {
  id: string;
  title: string;
  description: string | null;
  servings: number;
  author_id: string;
  ingredients: Ingredient[];
  glyph_kind: string | null;
  glyph_color: string | null;
  image_url?: string | null;
  created_at: string;
  updated_at: string;
}

/** backend/app/schemas/menu.py :: VoterResponse */
export interface Voter {
  id: string;
  first_name: string | null;
  username: string;
}

/** backend/app/schemas/menu.py :: MenuRecipeResponse */
export interface MenuRecipe {
  id: string;
  recipe_id: string;
  title: string;
  source: "random" | "user";
  added_by: string | null;
  votes_count: number;
  voters: Voter[];
}

/** backend/app/schemas/auth.py :: AdminUserResponse */
export interface AdminUserRow {
  id: string;
  username: string;
  first_name: string | null;
  role: string;
  has_telegram: boolean;
  has_email: boolean;
}

/** backend/app/schemas/menu.py :: MenuResponse */
export interface Menu {
  id: string;
  date: string;
  status: "collecting" | "voting" | "closed";
  winner_recipe_id: string | null;
  recipes: MenuRecipe[];
  created_at: string;
  user_voted_recipe_id: string | null;
  total_votes: number;
}
