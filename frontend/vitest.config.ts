import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [svelte()],
  // Sin esto Svelte resuelve su build de servidor y `mount()` no está disponible (S6).
  resolve: { conditions: ["browser"] },
  test: {
    environment: "jsdom",
    include: ["tests/vitest/**/*.test.ts"],
  },
});
