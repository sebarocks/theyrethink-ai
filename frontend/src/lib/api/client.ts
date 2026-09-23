import createClient from "openapi-fetch";
import type { paths } from "./generated.ts";

/**
 * Cliente HTTP tipado generado desde el contrato OpenAPI del backend.
 *
 * `baseUrl` vacío a propósito: las rutas del contrato ya incluyen `/api/v1`, y las cookies de
 * sesión viajan por `credentials: "include"` (D2, mismo origen por D4).
 */
export const api = createClient<paths>({
  baseUrl: "",
  credentials: "include",
});
