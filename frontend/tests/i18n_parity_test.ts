/// <reference lib="deno.ns" />
// Invariante de AGENTS.md §3.7: una clave nueva se añade a los 6 idiomas o no se añade.
import { assert, assertEquals } from "@std/assert";
import { LOCALES } from "../src/lib/i18n/locales.ts";

const MESSAGES_DIR = new URL("../messages/", import.meta.url);

async function messagesOf(locale: string): Promise<Record<string, string>> {
  const raw = await Deno.readTextFile(new URL(`${locale}.json`, MESSAGES_DIR));
  return JSON.parse(raw) as Record<string, string>;
}

Deno.test("las 6 locales declaran exactamente las mismas claves", async () => {
  const base = Object.keys(await messagesOf("es")).sort();
  for (const locale of LOCALES) {
    assertEquals(
      Object.keys(await messagesOf(locale)).sort(),
      base,
      `las claves de «${locale}» no coinciden con las de «es»`,
    );
  }
});

Deno.test("ninguna traducción está vacía", async () => {
  for (const locale of LOCALES) {
    for (const [key, value] of Object.entries(await messagesOf(locale))) {
      assert(value.trim().length > 0, `«${locale}.${key}» está vacía`);
    }
  }
});
