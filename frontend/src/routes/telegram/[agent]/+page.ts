import { getAgent } from "$lib/api/agents.ts";

// Ruta dinámica: no se prerenderiza; la sirve el *fallback* de la SPA (D8).
export const prerender = false;

export async function load({ params }: { params: { agent: string } }) {
  return { agent: await getAgent(Number(params.agent)) };
}
