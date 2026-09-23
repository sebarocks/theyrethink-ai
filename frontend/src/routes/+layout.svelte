<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { m } from "$lib/paraglide/messages.js";
  import { getLocale, locales, setLocale } from "$lib/paraglide/runtime.js";
  import { loadSession, session, signOut } from "$lib/session";
  import { toggleTheme } from "$lib/theme";

  let { children } = $props();

  const isLogin = $derived(page.url.pathname === "/login");

  onMount(() => {
    // En modo SPA no hay SSR que fije `<html lang>`; se sincroniza al montar.
    document.documentElement.lang = getLocale();
    void loadSession();
  });

  // Guarda de sesión: sin usuario, a `/login`; con usuario, fuera de `/login`.
  $effect(() => {
    if (!$session.ready) return;
    if ($session.user === null && !isLogin) void goto("/login");
    if ($session.user !== null && isLogin) void goto("/");
  });
</script>

<header
  class="flex items-center justify-between border-b border-slate-200 px-4 py-2 dark:border-slate-700"
>
  <a href="/" class="font-bold tracking-tight">{m.common_appName()}</a>
  <div class="flex items-center gap-3 text-sm">
    <nav class="flex gap-1" aria-label={m.common_selectLanguage()}>
      {#each locales as locale (locale)}
        <button
          type="button"
          class="rounded px-1 hover:bg-slate-100 dark:hover:bg-slate-800"
          class:font-bold={locale === getLocale()}
          onclick={() => setLocale(locale)}
        >
          {locale}
        </button>
      {/each}
    </nav>
    <button
      type="button"
      class="rounded px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
      onclick={() => toggleTheme()}
    >
      {m.common_switchTheme()}
    </button>
    {#if $session.user}
      <span class="text-slate-500">{$session.user.username}</span>
      <button
        type="button"
        class="rounded px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
        onclick={() => signOut()}
      >
        {m.common_logout()}
      </button>
    {:else}
      <a
        href="/login"
        class="rounded px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        {m.common_login()}
      </a>
    {/if}
  </div>
</header>

{@render children()}
