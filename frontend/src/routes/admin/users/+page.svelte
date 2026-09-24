<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import Modal from "$lib/admin/Modal.svelte";
  import { messageOf } from "$lib/admin/error";
  import {
    createUser,
    deleteUser,
    listUsers,
    updateUser,
    type AdminUser,
  } from "$lib/api/users";

  const input =
    "rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600";

  let users = $state<AdminUser[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let creating = $state(false);
  let editing = $state<AdminUser | null>(null);
  let form = $state({
    username: "",
    email: "",
    password: "",
    role: "usuario" as "admin" | "usuario",
  });

  async function load() {
    loading = true;
    try {
      users = await listUsers();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function openCreate() {
    form = { username: "", email: "", password: "", role: "usuario" };
    creating = true;
  }

  function openEdit(user: AdminUser) {
    form = {
      username: user.username,
      email: user.email,
      password: "",
      role: user.role as "admin" | "usuario",
    };
    editing = user;
  }

  async function submit() {
    error = null;
    try {
      if (editing) {
        await updateUser(editing.id, {
          username: form.username,
          email: form.email,
          role: form.role,
          ...(form.password === "" ? {} : { password: form.password }),
        });
      } else {
        await createUser({
          username: form.username,
          email: form.email,
          password: form.password,
          role: form.role,
        });
      }
      creating = false;
      editing = null;
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function remove(user: AdminUser) {
    if (!confirm(`${m.admin_deleteUserTitle()}: ${user.username}`)) return;
    try {
      await deleteUser(user.id);
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  function roleLabel(role: string): string {
    return role === "admin" ? m.admin_roleAdmin() : m.admin_roleUser();
  }
</script>

<section>
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">{m.admin_colUser()}</h1>
    <button
      type="button"
      class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
      onclick={openCreate}
    >
      {m.admin_configureUser()}
    </button>
  </header>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_profileDetailsSubtitle()}
  </p>

  {#if error}<p class="mt-3 text-sm text-red-600">{error}</p>{/if}

  {#if loading}
    <p class="mt-4 text-sm text-slate-500">{m.common_loading()}</p>
  {:else}
    <div class="mt-4 overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead
          class="border-b border-slate-200 text-slate-500 dark:border-slate-700"
        >
          <tr>
            <th class="py-2 pr-3">{m.admin_usernameLabel()}</th>
            <th class="py-2 pr-3">Email</th>
            <th class="py-2 pr-3">{m.admin_colStatus()}</th>
            <th class="py-2 pr-3">{m.admin_colRegistrationDate()}</th>
            <th class="py-2">{m.common_actions()}</th>
          </tr>
        </thead>
        <tbody>
          {#each users as user (user.id)}
            <tr class="border-b border-slate-100 dark:border-slate-800">
              <td class="py-2 pr-3 font-medium">{user.username}</td>
              <td class="py-2 pr-3 text-slate-500">{user.email}</td>
              <td class="py-2 pr-3">{roleLabel(user.role)}</td>
              <td class="py-2 pr-3 text-slate-500">
                {new Date(user.created_at).toLocaleDateString()}
              </td>
              <td class="py-2">
                <span class="flex gap-2 text-xs">
                  <button
                    type="button"
                    class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                    onclick={() => openEdit(user)}
                  >
                    {m.common_edit()}
                  </button>
                  <button
                    type="button"
                    class="rounded border px-2 py-1 text-red-600 hover:bg-red-50"
                    onclick={() => remove(user)}
                  >
                    {m.common_delete()}
                  </button>
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{#if creating || editing}
  <Modal
    title={editing ? m.admin_editUserTitle() : m.admin_configureUser()}
    onclose={() => {
      creating = false;
      editing = null;
    }}
  >
    <form
      class="flex flex-col gap-3"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_usernameLabel()}
        <input
          class={input}
          bind:value={form.username}
          placeholder={m.admin_usernamePlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        Email
        <input class={input} type="email" bind:value={form.email} />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_newPasswordLabel()}
        <input
          class={input}
          type="password"
          bind:value={form.password}
          placeholder={editing
            ? m.admin_leaveBlankKeepCurrent()
            : m.admin_newPasswordPlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_colStatus()}
        <select class={input} bind:value={form.role}>
          <option value="usuario">{m.admin_roleUser()}</option>
          <option value="admin">{m.admin_roleAdmin()}</option>
        </select>
      </label>
      <button
        type="submit"
        class="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
      >
        {m.admin_saveUser()}
      </button>
    </form>
  </Modal>
{/if}
