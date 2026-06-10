import { useEffect } from "react";
import { useLocalStorage } from "@/hooks/useLocalStorage";

type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

function getDefaultTheme(): Theme {
  return globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

export function useTheme() {
  // Значение хранится сырой строкой ("light"/"dark") — совместимо со старым форматом
  const [theme, setTheme] = useLocalStorage<Theme>(STORAGE_KEY, getDefaultTheme, {
    serialize: (v) => v,
    deserialize: (raw) => (raw === "light" || raw === "dark" ? raw : undefined),
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return { theme, toggleTheme };
}
