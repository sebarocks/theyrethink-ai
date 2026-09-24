import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type AdminThread = components["schemas"]["AdminThreadResponse"];
export type Message = components["schemas"]["MessageResponse"];

/** Todas las conversaciones de la plataforma; `agentId` filtra por agente (D18). */
export async function listAdminThreads(
  agentId?: number,
): Promise<AdminThread[]> {
  const { data, error, response } = await api.GET("/api/v1/admin/threads", {
    params: { query: agentId === undefined ? {} : { agent_id: agentId } },
  });
  if (error) throw toApiError(response, error);
  return data;
}

/** Transcript de cualquier hilo, leído del checkpointer (D16/D18). */
export async function listAdminMessages(threadId: number): Promise<Message[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/admin/threads/{thread_id}/messages",
    { params: { path: { thread_id: threadId } } },
  );
  if (error) throw toApiError(response, error);
  return data;
}
