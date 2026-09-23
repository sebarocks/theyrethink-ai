import { expect, test } from "vitest";
import { currentTheme, setTheme, toggleTheme } from "../../src/lib/theme.ts";

test("toggleTheme alterna entre claro y oscuro", () => {
  document.documentElement.classList.remove("dark");
  expect(currentTheme()).toBe("light");
  expect(toggleTheme()).toBe("dark");
  expect(document.documentElement.classList.contains("dark")).toBe(true);
  expect(toggleTheme()).toBe("light");
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});

test("setTheme persiste la elección", () => {
  setTheme("dark");
  expect(localStorage.getItem("theyrethink-theme")).toBe("dark");
});
