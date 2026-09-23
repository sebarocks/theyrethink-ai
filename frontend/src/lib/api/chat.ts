import { createSseParser, type SseEvent } from "$lib/chat/sse.ts";
import { api } from "./client.ts";

/** Evento de dominio del stream de chat (nunca tipos de SSE ni del backend). */
export type ChatEvent =
  | { type: "chunk"; text: string }
  | { type: "done" }
  | { type: "error"; code: string; detail: string };

function toChatEvent(event: SseEvent): ChatEvent | null {
  if (event.event === "chunk") {
    const data = JSON.parse(event.data) as { text?: string };
    return { type: "chunk", text: data.text ?? "" };
  }
  if (event.event === "done") return { type: "done" };
  if (event.event === "error") {
    const data = JSON.parse(event.data) as { code?: string; detail?: string };
    return {
      type: "error",
      code: data.code ?? "chat_stream_failed",
      detail: data.detail ?? "",
    };
  }
  return null; // heartbeat y eventos desconocidos
}

/**
 * Envía un mensaje y consume la respuesta en streaming (D5).
 *
 * Usa el cliente generado con `parseAs: "stream"` para no escribir un `fetch` a mano
 * (AGENTS.md §3.5); el cuerpo se parsea con el parser de SSE puro.
 */
export async function* streamMessage(
  threadId: number,
  text: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const { response } = await api.POST("/api/v1/threads/{thread_id}/messages", {
    params: { path: { thread_id: threadId } },
    body: { text },
    parseAs: "stream",
    signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`chat stream failed: HTTP ${response.status}`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parse = createSseParser();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const event of parse(value)) {
        const chatEvent = toChatEvent(event);
        if (chatEvent !== null) yield chatEvent;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
