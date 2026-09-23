import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type Agent = components["schemas"]["AgentResponse"];

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
