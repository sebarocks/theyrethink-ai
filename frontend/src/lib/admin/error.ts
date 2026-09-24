import { ApiError } from "$lib/api/errors.ts";

/** Mensaje legible de un error de formulario, con texto de reserva por recurso. */
export function messageOf(cause: unknown, fallback: string): string {
  return cause instanceof ApiError ? cause.message : fallback;
}
