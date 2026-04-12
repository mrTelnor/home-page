import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface MenuRecipe {
  id: string;
  recipe_id: string;
  title: string;
  source: "random" | "user";
  added_by: string | null;
  votes_count: number;
}

export interface Menu {
  id: string;
  date: string;
  status: "collecting" | "voting" | "closed";
  winner_recipe_id: string | null;
  recipes: MenuRecipe[];
  created_at: string;
}

export interface Recipe {
  id: string;
  title: string;
  description: string | null;
  servings: number;
  author_id: string;
  created_at: string;
}

export function useTodayMenu() {
  return useQuery({
    queryKey: ["menu", "today"],
    queryFn: async () => {
      try {
        return await api.get<Menu>("/api/menus/today");
      } catch {
        return null;
      }
    },
    refetchInterval: 30000,
  });
}

export function useMenuHistory() {
  return useQuery({
    queryKey: ["menu", "history"],
    queryFn: () => api.get<Menu[]>("/api/menus"),
  });
}

export function useAllRecipes() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: () => api.get<Recipe[]>("/api/recipes"),
  });
}

export function useSuggestRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ menuId, recipeId }: { menuId: string; recipeId: string }) =>
      api.post(`/api/menus/${menuId}/suggest`, { recipe_id: recipeId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu", "today"] });
    },
  });
}

export function useVote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ menuId, recipeId }: { menuId: string; recipeId: string }) =>
      api.post(`/api/menus/${menuId}/vote`, { recipe_id: recipeId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu", "today"] });
    },
  });
}
