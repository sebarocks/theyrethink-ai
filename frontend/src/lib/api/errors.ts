/**
 * Envelope de error estable del backend: `{error, code, detail}` (AGENTS.md §5).
 *
 * El backend lo emite desde sus manejadores centralizados, así que no aparece como
 * `response_model` en el OpenAPI y no se puede derivar del cliente generado.
 */
export interface ApiErrorPayload {
  error: string;
  code: string;
  detail: unknown;
}

export function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    "code" in value &&
    "detail" in value
  );
}

/** Mensaje legible para mostrar en UI a partir del `detail` del envelope. */
export function errorMessage(payload: ApiErrorPayload): string {
  if (typeof payload.detail === "string") return payload.detail;
  return payload.code;
}

/** Error tipado de la API, con el `code` del envelope para ramificar en la UI. */
export class ApiError extends Error {
  readonly code: string;
  readonly detail: unknown;

  constructor(payload: ApiErrorPayload) {
    super(errorMessage(payload));
    this.name = "ApiError";
    this.code = payload.code;
    this.detail = payload.detail;
  }
}

/** Convierte la respuesta de error del cliente generado en una excepción tipada. */
export function toApiError(response: Response, error: unknown): ApiError {
  if (isApiErrorPayload(error)) return new ApiError(error);
  return new ApiError({
    error: "request_error",
    code: `http_${response.status}`,
    detail: response.statusText,
  });
}
