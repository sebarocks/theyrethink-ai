import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type User = components["schemas"]["UserResponse"];

export async function login(username: string, password: string): Promise<User> {
  const { data, error, response } = await api.POST("/api/v1/auth/login", {
    body: { username, password },
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function register(
  username: string,
  email: string,
  password: string,
): Promise<User> {
  const { data, error, response } = await api.POST("/api/v1/auth/register", {
    body: { username, email, password },
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function logout(): Promise<void> {
  const { error, response } = await api.POST("/api/v1/auth/logout");
  if (error) throw toApiError(response, error);
}

/** Identidad autenticada, o `null` si no hay sesión válida (401). */
export async function me(): Promise<User | null> {
  const { data, response } = await api.GET("/api/v1/auth/me");
  if (response.status === 401) return null;
  if (!response.ok || !data) throw toApiError(response, null);
  return data;
}
