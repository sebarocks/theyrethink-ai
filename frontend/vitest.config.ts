import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    // Sin esto Svelte resuelve su build de servidor y `mount()` no está disponible (S6).
    conditions: ["browser"],
    // Los componentes importan por el alias de SvelteKit `$lib`; Vitest no carga el
    // plugin de SvelteKit, así que el alias se declara aquí (S6).
    alias: { $lib: new URL("./src/lib", import.meta.url).pathname },
  },
  test: {
    environment: "jsdom",
    include: ["tests/vitest/**/*.test.ts"],
  },
});
