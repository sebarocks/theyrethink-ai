import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type AdminUser = components["schemas"]["UserAdminResponse"];
export type UserCreate = components["schemas"]["UserCreate"];
export type UserUpdate = components["schemas"]["UserUpdate"];

export async function listUsers(): Promise<AdminUser[]> {
  const { data, error, response } = await api.GET("/api/v1/users");
  if (error) throw toApiError(response, error);
  return data;
}

export async function createUser(payload: UserCreate): Promise<AdminUser> {
  const { data, error, response } = await api.POST("/api/v1/users", {
    body: payload,
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function updateUser(
  userId: number,
  payload: UserUpdate,
): Promise<AdminUser> {
  const { data, error, response } = await api.PATCH("/api/v1/users/{user_id}", {
    params: { path: { user_id: userId } },
    body: payload,
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteUser(userId: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/users/{user_id}", {
    params: { path: { user_id: userId } },
  });
  if (error) throw toApiError(response, error);
}
