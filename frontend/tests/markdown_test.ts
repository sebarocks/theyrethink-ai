import { assertEquals } from "@std/assert";
import {
  parseBlocks,
  parseInline,
  safeHref,
} from "../src/lib/chat/markdown.ts";

Deno.test("parsea encabezados, listas y bloques de código", () => {
  const blocks = parseBlocks(
    "# Título\n\n- uno\n- dos\n\n```ts\nconst a = 1;\n```",
  );
  assertEquals(blocks, [
    { type: "heading", level: 1, text: "Título" },
    { type: "list", ordered: false, items: ["uno", "dos"] },
    { type: "code", language: "ts", code: "const a = 1;" },
  ]);
});

Deno.test("parsea listas ordenadas, citas y párrafos de varias líneas", () => {
  const blocks = parseBlocks(
    "1. uno\n2. dos\n\n> cita\n\nlinea uno\nlinea dos",
  );
  assertEquals(blocks, [
    { type: "list", ordered: true, items: ["uno", "dos"] },
    { type: "quote", text: "cita" },
    { type: "paragraph", text: "linea uno linea dos" },
  ]);
});

Deno.test("parsea negrita, cursiva, código y enlaces en línea", () => {
  assertEquals(parseInline("hola **mundo** y `code`"), [
    { type: "text", text: "hola " },
    { type: "bold", text: "mundo" },
    { type: "text", text: " y " },
    { type: "code", text: "code" },
  ]);
  assertEquals(parseInline("[web](https://x.test)"), [
    { type: "link", text: "web", href: "https://x.test" },
  ]);
});

Deno.test("rechaza esquemas peligrosos en enlaces", () => {
  assertEquals(safeHref("javascript:alert(1)"), null);
  assertEquals(safeHref("https://ok.test"), "https://ok.test");
  assertEquals(safeHref("/web/1"), "/web/1");
  const segments = parseInline("[x](javascript:alert(1))");
  assertEquals(segments.some((segment) => segment.type === "link"), false);
});

Deno.test("no genera HTML: el marcado desconocido queda como texto", () => {
  assertEquals(parseBlocks("<script>alert(1)</script>"), [
    { type: "paragraph", text: "<script>alert(1)</script>" },
  ]);
});
