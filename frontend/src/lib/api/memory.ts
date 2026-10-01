import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type MemoryFact = components["schemas"]["MemoryFactResponse"];

/** Hechos que el agente recuerda del usuario autenticado (D10). */
export async function listMemory(agentId: number): Promise<MemoryFact[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/agents/{agent_id}/memory",
    { params: { path: { agent_id: agentId } } },
  );
  if (error) throw toApiError(response, error);
  return data.facts;
}

/** Olvida toda la memoria del usuario autenticado para ese agente (D10). */
export async function clearMemory(agentId: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/agents/{agent_id}/memory",
    { params: { path: { agent_id: agentId } } },
  );
  if (error) throw toApiError(response, error);
}
