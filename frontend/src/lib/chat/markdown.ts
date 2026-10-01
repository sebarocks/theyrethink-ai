/**
 * Parser de Markdown mínimo y **seguro** para las respuestas del agente.
 *
 * No genera HTML ni usa `{@html}`: devuelve una estructura de bloques y segmentos que Svelte
 * renderiza como elementos, así que no hay superficie de XSS (AGENTS.md §5). Cubre lo que el
 * chat necesita: encabezados, párrafos, listas, citas, bloques de código, negrita, cursiva,
 * código en línea y enlaces.
 */

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; text: string }
  | { type: "italic"; text: string }
  | { type: "code"; text: string }
  | { type: "link"; text: string; href: string };

export type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "code"; language: string; code: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "quote"; text: string };

const FENCE = /^```(\w*)\s*$/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const QUOTE = /^\s*>\s?(.*)$/;

const INLINE_TOKEN =
  /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|_[^_\n]+_|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\))/g;

/** Solo se aceptan enlaces http(s), mailto y anclas/rutas relativas del mismo origen. */
export function safeHref(href: string): string | null {
  const trimmed = href.trim();
  return /^(https?:\/\/|mailto:|\/|#)/i.test(trimmed) ? trimmed : null;
}

function decodeToken(token: string): Inline {
  if (token.startsWith("**")) {
    return { type: "bold", text: token.slice(2, -2) };
  }
  if (token.startsWith("`")) {
    return { type: "code", text: token.slice(1, -1) };
  }
  if (token.startsWith("[")) {
    const split = token.indexOf("](");
    const href = safeHref(token.slice(split + 2, -1));
    // Un enlace con esquema no permitido se degrada a texto: nunca llega al DOM como `href`.
    return href === null
      ? { type: "text", text: token }
      : { type: "link", text: token.slice(1, split), href };
  }
  return { type: "italic", text: token.slice(1, -1) };
}

export function parseInline(text: string): Inline[] {
  const segments: Inline[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE_TOKEN)) {
    const index = match.index ?? 0;
    if (index > last) {
      segments.push({ type: "text", text: text.slice(last, index) });
    }
    segments.push(decodeToken(match[0]));
    last = index + match[0].length;
  }
  if (last < text.length) {
    segments.push({ type: "text", text: text.slice(last) });
  }
  return segments.filter((segment) =>
    segment.type !== "text" || segment.text !== ""
  );
}

function isBlockStart(line: string): boolean {
  const trimmed = line.trim();
  return (
    FENCE.test(trimmed) ||
    HEADING.test(trimmed) ||
    QUOTE.test(line) ||
    BULLET.test(line) ||
    ORDERED.test(line)
  );
}

export function parseBlocks(source: string): Block[] {
  const lines = (source ?? "").replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (line.trim() === "") {
      index += 1;
      continue;
    }

    const fence = FENCE.exec(line.trim());
    if (fence !== null) {
      const language = fence[1] ?? "";
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !FENCE.test(lines[index].trim())) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1; // cierra el bloque (o consume el EOF)
      blocks.push({ type: "code", language, code: code.join("\n") });
      continue;
    }

    const heading = HEADING.exec(line.trim());
    if (heading !== null) {
      blocks.push({
        type: "heading",
        level: heading[1].length,
        text: heading[2].trim(),
      });
      index += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      const parts: string[] = [];
      while (index < lines.length && QUOTE.test(lines[index])) {
        parts.push(QUOTE.exec(lines[index])?.[1] ?? "");
        index += 1;
      }
      blocks.push({ type: "quote", text: parts.join(" ").trim() });
      continue;
    }

    if (BULLET.test(line) || ORDERED.test(line)) {
      const ordered = ORDERED.test(line);
      const pattern = ordered ? ORDERED : BULLET;
      const items: string[] = [];
      while (index < lines.length && pattern.test(lines[index])) {
        items.push((pattern.exec(lines[index])?.[1] ?? "").trim());
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    const parts: string[] = [];
    while (
      index < lines.length && lines[index].trim() !== "" &&
      !isBlockStart(lines[index])
    ) {
      parts.push(lines[index].trim());
      index += 1;
    }
    if (parts.length > 0) {
      blocks.push({ type: "paragraph", text: parts.join(" ") });
    } else {
      index += 1; // defensivo: evita un bucle infinito ante una línea inesperada
    }
  }

  return blocks;
}
