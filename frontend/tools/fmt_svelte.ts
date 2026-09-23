/// <reference lib="deno.ns" />
// `deno fmt` ignora los archivos `.svelte` en silencio (S6 §2.5), así que se formatean con
// Prettier + `prettier-plugin-svelte` invocados **como librería** (nunca la CLI de Prettier
// ni npm). Ver ADR `0018`.
import * as prettier from "prettier";
import sveltePlugin from "prettier-plugin-svelte";

async function collectSvelteFiles(dir: string): Promise<string[]> {
  const found: string[] = [];
  for await (const entry of Deno.readDir(dir)) {
    const path = `${dir}/${entry.name}`;
    if (entry.isDirectory) {
      found.push(...(await collectSvelteFiles(path)));
    } else if (entry.isFile && entry.name.endsWith(".svelte")) {
      found.push(path);
    }
  }
  return found;
}

const targets = Deno.args.length > 0 ? Deno.args : ["src"];

const paths: string[] = [];
for (const target of targets) {
  paths.push(...(await collectSvelteFiles(target)));
}

for (const path of paths) {
  const source = await Deno.readTextFile(path);
  const formatted = await prettier.format(source, {
    parser: "svelte",
    plugins: [sveltePlugin],
  });
  if (formatted !== source) {
    await Deno.writeTextFile(path, formatted);
  }
}
