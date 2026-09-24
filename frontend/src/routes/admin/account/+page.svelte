<script lang="ts">
  import { m } from "$lib/paraglide/messages.js";
  import { messageOf } from "$lib/admin/error";
  import { updateProfile } from "$lib/api/auth";
  import { session, setUser } from "$lib/session";

  const input =
    "rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600";

  let username = $state("");
  let email = $state("");
  let currentPassword = $state("");
  let newPassword = $state("");
  let error = $state<string | null>(null);
  let saved = $state(false);
  let busy = $state(false);

  $effect(() => {
    if ($session.user !== null) {
      username = $session.user.username;
      email = $session.user.email;
    }
  });

  async function submit() {
    error = null;
    saved = false;
    busy = true;
    try {
      const updated = await updateProfile({
        username,
        email,
        current_password: currentPassword,
        new_password: newPassword === "" ? null : newPassword,
      });
      setUser(updated);
      currentPassword = "";
      newPassword = "";
      saved = true;
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      busy = false;
    }
  }

  const roleLabel = $derived(
    $session.user?.role === "admin"
      ? m.admin_adminFullAccess()
      : m.admin_standardUser(),
  );
</script>

<section class="max-w-lg">
  <h1 class="text-2xl font-bold">{m.admin_accountSettingsTitle()}</h1>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_updateUsernameOrPassword()}
  </p>

  <form
    class="mt-4 flex flex-col gap-3"
    onsubmit={(event) => {
      event.preventDefault();
      void submit();
    }}
  >
    <label class="flex flex-col gap-1 text-sm">
      {m.admin_usernameLabel()}
      <input
        class={input}
        bind:value={username}
        placeholder={m.admin_usernamePlaceholder()}
      />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      Email
      <input class={input} type="email" bind:value={email} />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      {m.admin_currentPasswordLabel()}
      <input
        class={input}
        type="password"
        bind:value={currentPassword}
        autocomplete="current-password"
      />
    </label>
    <label class="flex flex-col gap-1 text-sm">
      {m.admin_newPasswordLabel()}
      <input
        class={input}
        type="password"
        bind:value={newPassword}
        placeholder={m.admin_newPasswordPlaceholder()}
        autocomplete="new-password"
      />
    </label>
    <p class="text-xs text-slate-500">{m.admin_leaveBlankNoChange()}</p>

    {#if error}<p class="text-sm text-red-600">{error}</p>{/if}
    {#if saved}<p class="text-sm text-emerald-600">{m.common_success()}</p>{/if}

    <button
      type="submit"
      class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      disabled={busy}
    >
      {m.admin_updateProfile()}
    </button>
  </form>

  <p class="mt-6 text-sm text-slate-500">
    {m.admin_activeUserLabel()}: {$session.user?.username ?? "—"} · {roleLabel}
  </p>
</section>
