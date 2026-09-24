import { api } from "./client.ts";
import { toApiError } from "./errors.ts";
import type { components } from "./generated.ts";

export type Role = components["schemas"]["RoleResponse"];
export type RoleCreate = components["schemas"]["RoleCreate"];
export type RoleUpdate = components["schemas"]["RoleUpdate"];

export async function listRoles(): Promise<Role[]> {
  const { data, error, response } = await api.GET("/api/v1/roles");
  if (error) throw toApiError(response, error);
  return data;
}

export async function createRole(payload: RoleCreate): Promise<Role> {
  const { data, error, response } = await api.POST("/api/v1/roles", {
    body: payload,
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function updateRole(
  roleId: number,
  payload: RoleUpdate,
): Promise<Role> {
  const { data, error, response } = await api.PATCH("/api/v1/roles/{role_id}", {
    params: { path: { role_id: roleId } },
    body: payload,
  });
  if (error) throw toApiError(response, error);
  return data;
}

export async function deleteRole(roleId: number): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/roles/{role_id}", {
    params: { path: { role_id: roleId } },
  });
  if (error) throw toApiError(response, error);
}
