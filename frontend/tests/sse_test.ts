/// <reference lib="deno.ns" />
// El parser de SSE es lógica pura: se testea sin navegador ni red.
import { assertEquals } from "@std/assert";
import { createSseParser } from "../src/lib/chat/sse.ts";

Deno.test("parsea un evento completo", () => {
  const parse = createSseParser();

  assertEquals(parse('event: chunk\ndata: {"text":"hola"}\n\n'), [
    { event: "chunk", data: '{"text":"hola"}' },
  ]);
});

Deno.test("tolera eventos partidos entre chunks", () => {
  const parse = createSseParser();

  assertEquals(parse("event: chu"), []);
  assertEquals(parse('nk\ndata: {"text":"ho'), []);
  assertEquals(parse('la"}\n\n'), [{
    event: "chunk",
    data: '{"text":"hola"}',
  }]);
});

Deno.test("emite varios eventos de un mismo chunk", () => {
  const parse = createSseParser();

  assertEquals(
    parse("event: heartbeat\ndata: {}\n\nevent: done\ndata: {}\n\n"),
    [
      { event: "heartbeat", data: "{}" },
      { event: "done", data: "{}" },
    ],
  );
});

Deno.test("normaliza separadores CRLF", () => {
  const parse = createSseParser();

  assertEquals(parse("event: done\r\ndata: {}\r\n\r\n"), [{
    event: "done",
    data: "{}",
  }]);
});

Deno.test("descarta eventos sin línea data", () => {
  const parse = createSseParser();

  assertEquals(parse("event: ping\n\n"), []);
});
