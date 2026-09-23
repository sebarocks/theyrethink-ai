import { writable } from "svelte/store";
import {
  login as apiLogin,
  logout as apiLogout,
  me,
  type User,
} from "$lib/api/auth.ts";

/**
 * Estado de sesión compartido.
 *
 * Se usa `svelte/store` (y no runes) porque `deno check` no entiende `$state` en archivos
 * `.svelte.ts`; los stores son tipados y funcionan igual en Svelte 5.
 */
export interface SessionState {
  user: User | null;
  ready: boolean;
}

export const session = writable<SessionState>({ user: null, ready: false });

/** Resuelve la sesión al arrancar la app (401 ⇒ anónimo, no es un error). */
export async function loadSession(): Promise<void> {
  session.set({ user: await me(), ready: true });
}

export async function signIn(
  username: string,
  password: string,
): Promise<void> {
  const user = await apiLogin(username, password);
  session.set({ user, ready: true });
}

export async function signOut(): Promise<void> {
  await apiLogout();
  session.set({ user: null, ready: true });
}
