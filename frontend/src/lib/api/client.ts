import createClient from "openapi-fetch";
import type { paths } from "./generated.ts";

/** Cliente HTTP tipado generado desde el contrato OpenAPI del backend. */
export const api = createClient<paths>({
  baseUrl: "/api/v1",
  credentials: "include",
});
