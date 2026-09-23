export type Theme = "light" | "dark";

const STORAGE_KEY = "theyrethink-theme";

/** Tema aplicado ahora mismo (lo fija el script anti-parpadeo de `app.html`). */
export function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function setTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Sin localStorage (modo privado): el tema no persiste.
  }
}

export function toggleTheme(): Theme {
  const next: Theme = currentTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
