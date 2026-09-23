import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type Thread = components["schemas"]["ThreadResponse"];
export type Message = components["schemas"]["MessageResponse"];

export async function listThreads(): Promise<Thread[]> {
  const { data, error, response } = await api.GET("/api/v1/threads");
  if (error) throw toApiError(response, error);
  return data;
}

export async function createThread(
  agentId: number,
  title?: string,
): Promise<Thread> {
  const { data, error, response } = await api.POST("/api/v1/threads", {
    body: title === undefined
      ? { agent_id: agentId }
      : { agent_id: agentId, title },
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function renameThread(
  threadId: number,
  title: string,
): Promise<Thread> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/threads/{thread_id}",
    {
      params: { path: { thread_id: threadId } },
      body: { title },
    },
  );
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteThread(threadId: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/threads/{thread_id}", {
    params: { path: { thread_id: threadId } },
  });
  if (error) throw toApiError(response, error);
}

/** Transcript del hilo, leído del checkpointer (D16). */
export async function listMessages(threadId: number): Promise<Message[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/threads/{thread_id}/messages",
    {
      params: { path: { thread_id: threadId } },
    },
  );
  if (error) throw toApiError(response, error);
  return data;
}
