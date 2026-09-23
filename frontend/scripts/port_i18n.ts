/// <reference lib="deno.ns" />
// Migración (una vez) de las claves de i18n del proyecto anterior a Paraglide.
//
// Lee `../theythink-ai/static/js/i18n*.js` — **solo lectura** (AGENTS.md §1) —, extrae los
// literales `TRANSLATIONS` (i18n.js) y `mine` (i18n.extra.*.js), los fusiona por locale y
// escribe `messages/{locale}.json` con claves planas `grupo_clave`.
//
// Ver DEVELOPMENT_PLAN.md §5 (Fase 4) y ADR 0019.
import { LOCALES } from "../src/lib/i18n/locales.ts";

const LEGACY_JS = new URL("../../../theythink-ai/static/js/", import.meta.url);
const OUT = new URL("../messages/", import.meta.url);

const FILES: Array<[file: string, marker: string]> = [
  ["i18n.js", "var TRANSLATIONS = "],
  ["i18n.extra.chat.js", "var mine = "],
  ["i18n.extra.dashboard.js", "var mine = "],
  ["i18n.extra.telegram.js", "var mine = "],
  ["i18n.extra.terms.js", "var mine = "],
  ["i18n.extra.whatsapp.js", "var mine = "],
];

type Groups = Record<string, Record<string, unknown>>;
type Tree = Record<string, Groups>;

/** Devuelve cada literal `{...}` que sigue a `marker`, con llaves balanceadas. */
function extractBlocks(source: string, marker: string): string[] {
  const blocks: string[] = [];
  let from = 0;
  while (true) {
    const at = source.indexOf(marker, from);
    if (at === -1) break;
    const open = source.indexOf("{", at + marker.length);
    let depth = 0;
    let inString: string | null = null;
    let escaped = false;
    let i = open;
    for (; i < source.length; i++) {
      const ch = source[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === inString) inString = null;
        continue;
      }
      if (ch === '"' || ch === "'") inString = ch;
      else if (ch === "{") depth++;
      else if (ch === "}" && --depth === 0) break;
    }
    blocks.push(source.slice(open, i + 1));
    from = i + 1;
  }
  return blocks;
}

// deno-lint-ignore no-eval
const evaluate = (literal: string): Tree =>
  new Function(`return (${literal});`)() as Tree;

function mergeInto(target: Tree, source: Tree): void {
  for (const [locale, groups] of Object.entries(source)) {
    target[locale] ??= {};
    for (const [group, entries] of Object.entries(groups)) {
      target[locale][group] = { ...(target[locale][group] ?? {}), ...entries };
    }
  }
}

const merged: Tree = {};
for (const [file, marker] of FILES) {
  const source = await Deno.readTextFile(new URL(file, LEGACY_JS));
  for (const block of extractBlocks(source, marker)) {
    mergeInto(merged, evaluate(block));
  }
}

for (const locale of LOCALES) {
  const groups = merged[locale];
  if (!groups) throw new Error(`falta la locale «${locale}» en el origen`);

  const flat: Record<string, string> = {};
  for (const group of Object.keys(groups).sort()) {
    for (const [key, value] of Object.entries(groups[group])) {
      flat[`${group}_${key}`] = typeof value === "string"
        ? value
        : JSON.stringify(value);
    }
  }

  // Se conservan las claves ya presentes (p. ej. añadidas a mano) para que re-ejecutar el
  // script no borre trabajo posterior; las claves portadas mandan.
  let existing: Record<string, string> = {};
  try {
    existing = JSON.parse(
      await Deno.readTextFile(new URL(`${locale}.json`, OUT)),
    );
  } catch {
    // Primera ejecución: aún no hay fichero.
  }

  const sorted = Object.fromEntries(
    Object.entries({ ...existing, ...flat }).sort(([a], [b]) =>
      a.localeCompare(b)
    ),
  );
  await Deno.writeTextFile(
    new URL(`${locale}.json`, OUT),
    `${JSON.stringify(sorted, null, 2)}\n`,
  );
  console.log(`${locale}: ${Object.keys(sorted).length} claves`);
}
