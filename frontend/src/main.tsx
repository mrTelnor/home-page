import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

// Apply stored theme before first render to avoid flash
const storedTheme = localStorage.getItem("theme");
let initialTheme: "light" | "dark";
if (storedTheme === "light" || storedTheme === "dark") {
  initialTheme = storedTheme;
} else {
  const prefersDark = globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches;
  initialTheme = prefersDark ? "dark" : "light";
}
if (initialTheme === "dark") document.documentElement.classList.add("dark");

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
