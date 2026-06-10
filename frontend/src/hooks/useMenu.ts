import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { endpoints } from "@/api/endpoints";
import { type Menu, type Recipe } from "@/api/types";

export function useTodayMenu() {
  return useQuery({
    queryKey: ["menu", "today"],
    queryFn: async () => {
      try {
        return await api.get<Menu>(endpoints.menus.today);
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
    queryFn: () => api.get<Menu[]>(endpoints.menus.list),
  });
}

export function useAllRecipes() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: () => api.get<Recipe[]>(endpoints.recipes.list),
  });
}

export function useSuggestRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ menuId, recipeId }: { menuId: string; recipeId: string }) =>
      api.post(endpoints.menus.suggest(menuId), { recipe_id: recipeId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu", "today"] });
    },
  });
}

export function useVote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ menuId, recipeId }: { menuId: string; recipeId: string }) =>
      api.post(endpoints.menus.vote(menuId), { recipe_id: recipeId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu", "today"] });
    },
  });
}

export function useCancelVote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ menuId }: { menuId: string }) => api.del(endpoints.menus.vote(menuId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu", "today"] });
    },
  });
}
