<script lang="ts">
  import { goto } from "$app/navigation";
  import { m } from "$lib/paraglide/messages.js";
  import { ApiError } from "$lib/api/errors";
  import { signIn } from "$lib/session";

  let username = $state("");
  let password = $state("");
  let error = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      await signIn(username, password);
      await goto("/");
    } catch (cause) {
      error =
        cause instanceof ApiError
          ? cause.message
          : m.loginPage_invalidCredentials();
    } finally {
      busy = false;
    }
  }
</script>

<main class="mx-auto flex max-w-sm flex-col gap-6 p-8">
  <div>
    <h1 class="text-2xl font-bold">{m.loginPage_title()}</h1>
    <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
      {m.loginPage_subtitle()}
    </p>
  </div>

  <form class="flex flex-col gap-4" onsubmit={submit}>
    <label class="flex flex-col gap-1 text-sm">
      {m.loginPage_userLabel()}
      <input
        class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 outline-none focus:border-emerald-500 dark:border-slate-600"
        placeholder={m.loginPage_userPlaceholder()}
        bind:value={username}
        autocomplete="username"
      />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      {m.loginPage_passwordLabel()}
      <input
        class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 outline-none focus:border-emerald-500 dark:border-slate-600"
        type="password"
        placeholder={m.loginPage_passwordPlaceholder()}
        bind:value={password}
        autocomplete="current-password"
      />
    </label>

    {#if error}
      <p class="text-sm text-red-600">{error}</p>
    {/if}

    <button
      type="submit"
      class="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white disabled:opacity-50"
      disabled={busy}
    >
      {m.loginPage_submitButton()}
    </button>
  </form>
</main>
