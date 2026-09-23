/**
 * Parser incremental de Server-Sent Events.
 *
 * Puro y sin dependencias: el transporte vive en `$lib/api/chat.ts`. Tolera eventos partidos
 * entre chunks (un `data:` puede llegar a medias) y separadores `\r\n` o `\n`.
 */
export interface SseEvent {
  event: string;
  data: string;
}

/** Devuelve una función que acumula chunks y emite los eventos ya completos. */
export function createSseParser(): (chunk: string) => SseEvent[] {
  let buffer = "";
  return (chunk: string): SseEvent[] => {
    buffer += chunk.replaceAll("\r\n", "\n");
    const events: SseEvent[] = [];
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseEvent(raw);
      if (event !== null) events.push(event);
      boundary = buffer.indexOf("\n\n");
    }
    return events;
  };
}

function parseEvent(raw: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data.push(line.slice("data:".length).trimStart());
    }
  }
  if (data.length === 0) return null;
  return { event, data: data.join("\n") };
}
