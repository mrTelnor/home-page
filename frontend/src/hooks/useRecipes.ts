import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";

export interface Ingredient {
  id?: string;
  name: string;
  amount: string;
  unit: string | null;
}

export interface Recipe {
  id: string;
  title: string;
  description: string | null;
  servings: number;
  author_id: string;
  ingredients: Ingredient[];
  glyph_kind: string | null;
  glyph_color: string | null;
  created_at: string;
  updated_at: string;
}

export function useRecipesList() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: () => api.get<Recipe[]>("/api/recipes"),
  });
}

export function useRecipe(id: string) {
  return useQuery({
    queryKey: ["recipes", id],
    queryFn: () => api.get<Recipe>(`/api/recipes/${id}`),
    enabled: !!id,
  });
}

export function useCreateRecipe() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { title: string; description?: string; servings: number; ingredients: Omit<Ingredient, "id">[]; glyph_kind?: string | null; glyph_color?: string | null }) =>
      api.post<Recipe>("/api/recipes", data),
    onSuccess: (recipe) => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate(`/recipes/${recipe.id}`);
    },
  });
}

export function useUpdateRecipe(id: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: { title?: string; description?: string; servings?: number; ingredients?: Omit<Ingredient, "id">[]; glyph_kind?: string | null; glyph_color?: string | null }) =>
      api.put<Recipe>(`/api/recipes/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      queryClient.invalidateQueries({ queryKey: ["recipes", id] });
      navigate(`/recipes/${id}`);
    },
  });
}

export function useDeleteRecipe() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (id: string) => api.del(`/api/recipes/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate("/recipes");
    },
  });
}
