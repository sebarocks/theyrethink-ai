import { paraglideVitePlugin } from "@inlang/paraglide-js";
import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    sveltekit({
      adapter: adapter({ fallback: "200.html" }),
      // SPA servida desde la raíz por FastAPI (D4): rutas de assets absolutas para que
      // funcionen en rutas anidadas como `/web/[agent]`.
      paths: { relative: false },
    }),
    paraglideVitePlugin({
      project: "./project.inlang",
      outdir: "./src/lib/paraglide",
      emitTsDeclarations: true,
      // Debe coincidir con la task `i18n` de `deno.json` (que `check` ejecuta antes del
      // typecheck): si divergen, `check` valida contra un runtime distinto del construido.
      strategy: ["localStorage", "preferredLanguage", "baseLocale"],
    }),
  ],
});
