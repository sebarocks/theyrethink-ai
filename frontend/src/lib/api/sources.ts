import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type Source = components["schemas"]["SourceResponse"];

export async function listSources(): Promise<Source[]> {
  const { data, error, response } = await api.GET("/api/v1/sources");
  if (error) throw toApiError(response, error);
  return data;
}

export async function createSource(
  name: string,
  content: string,
): Promise<Source> {
  const { data, error, response } = await api.POST("/api/v1/sources", {
    body: { name, content },
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function updateSource(
  sourceId: number,
  payload: { name?: string; content?: string },
): Promise<Source> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/sources/{source_id}",
    {
      params: { path: { source_id: sourceId } },
      body: payload,
    },
  );
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteSource(sourceId: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/sources/{source_id}", {
    params: { path: { source_id: sourceId } },
  });
  if (error) throw toApiError(response, error);
}

export async function listAgentSources(agentId: number): Promise<Source[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/agents/{agent_id}/sources",
    { params: { path: { agent_id: agentId } } },
  );
  if (error) throw toApiError(response, error);
  return data;
}

export async function attachSource(
  agentId: number,
  sourceId: number,
): Promise<void> {
  const { error, response } = await api.PUT(
    "/api/v1/agents/{agent_id}/sources/{source_id}",
    { params: { path: { agent_id: agentId, source_id: sourceId } } },
  );
  if (error) throw toApiError(response, error);
}

export async function detachSource(
  agentId: number,
  sourceId: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/agents/{agent_id}/sources/{source_id}",
    { params: { path: { agent_id: agentId, source_id: sourceId } } },
  );
  if (error) throw toApiError(response, error);
}
