import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { type Ingredient, type Recipe } from "@/api/types";

export function useRecipesList() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: () => api.get<Recipe[]>(endpoints.recipes.list),
  });
}

export function useRecipe(id: string) {
  return useQuery({
    queryKey: ["recipes", id],
    queryFn: () => api.get<Recipe>(endpoints.recipes.detail(id)),
    enabled: !!id,
  });
}

export function useCreateRecipe() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: {
      title: string;
      description?: string;
      servings: number;
      ingredients: Omit<Ingredient, "id">[];
      glyph_kind?: string | null;
      glyph_color?: string | null;
      photo_url?: string;
    }) => api.post<Recipe>(endpoints.recipes.list, data),
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
    mutationFn: (data: {
      title?: string;
      description?: string;
      servings?: number;
      ingredients?: Omit<Ingredient, "id">[];
      glyph_kind?: string | null;
      glyph_color?: string | null;
      photo_url?: string;
    }) => api.put<Recipe>(endpoints.recipes.detail(id), data),
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
    mutationFn: (id: string) => api.del(endpoints.recipes.detail(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate("/recipes");
    },
  });
}
