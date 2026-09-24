import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type Agent = components["schemas"]["AgentResponse"];
export type AgentCreate = components["schemas"]["AgentCreate"];
export type AgentUpdate = components["schemas"]["AgentUpdate"];

export async function listAgents(): Promise<Agent[]> {
  const { data, error, response } = await api.GET("/api/v1/agents");
  if (error) throw toApiError(response, error);
  return data;
}

export async function getAgent(agentId: number): Promise<Agent> {
  const { data, error, response } = await api.GET("/api/v1/agents/{agent_id}", {
    params: { path: { agent_id: agentId } },
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function createAgent(payload: AgentCreate): Promise<Agent> {
  const { data, error, response } = await api.POST("/api/v1/agents", {
    body: payload,
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function updateAgent(
  agentId: number,
  payload: AgentUpdate,
): Promise<Agent> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/agents/{agent_id}",
    {
      params: { path: { agent_id: agentId } },
      body: payload,
    },
  );
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteAgent(agentId: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/agents/{agent_id}", {
    params: { path: { agent_id: agentId } },
  });
  if (error) throw toApiError(response, error);
}

export async function uploadAgentAvatar(
  agentId: number,
  file: File,
): Promise<Agent> {
  const { data, error, response } = await api.POST(
    "/api/v1/agents/{agent_id}/avatar",
    {
      params: { path: { agent_id: agentId } },
      // FastAPI emite `contentMediaType: application/octet-stream`, que el generador tipa
      // como `string`; en runtime `openapi-fetch` arma un `FormData` con el archivo.
      body: { file: file as unknown as string },
    },
  );
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteAgentAvatar(agentId: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/agents/{agent_id}/avatar",
    { params: { path: { agent_id: agentId } } },
  );
  if (error) throw toApiError(response, error);
}

export function agentAvatarUrl(agentId: number): string {
  return `/api/v1/agents/${agentId}/avatar`;
}
