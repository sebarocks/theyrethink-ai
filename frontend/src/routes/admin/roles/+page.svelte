<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import Modal from "$lib/admin/Modal.svelte";
  import { messageOf } from "$lib/admin/error";
  import {
    createRole,
    deleteRole,
    listRoles,
    updateRole,
    type Role,
  } from "$lib/api/roles";

  const input =
    "rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600";

  let roles = $state<Role[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let editing = $state<Role | null>(null);
  let creating = $state(false);
  let form = $state({
    key: "",
    name: "",
    description: "",
    prompt: "",
    is_system: false,
  });

  async function load() {
    loading = true;
    try {
      roles = await listRoles();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function openCreate() {
    form = { key: "", name: "", description: "", prompt: "", is_system: false };
    creating = true;
  }

  function openEdit(role: Role) {
    form = {
      key: role.key,
      name: role.name,
      description: role.description,
      prompt: role.prompt,
      is_system: role.is_system,
    };
    editing = role;
  }

  async function submit() {
    error = null;
    try {
      if (editing) {
        await updateRole(editing.id, {
          name: form.name,
          description: form.description,
          prompt: form.prompt,
          is_system: form.is_system,
        });
      } else {
        await createRole(form);
      }
      editing = null;
      creating = false;
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function remove(role: Role) {
    if (!confirm(`${m.admin_confirmDeleteTitle()} ${role.name}`)) return;
    try {
      await deleteRole(role.id);
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }
</script>

<section>
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">{m.admin_viewRoles()}</h1>
    <button
      type="button"
      class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
      onclick={openCreate}
    >
      {m.common_create()}
    </button>
  </header>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_roleSubtitle()}
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
            <th class="py-2 pr-3">{m.admin_colSystemRole()}</th>
            <th class="py-2 pr-3">{m.admin_uniqueKey()}</th>
            <th class="py-2 pr-3">{m.admin_briefDescription()}</th>
            <th class="py-2 pr-3">{m.admin_colStatus()}</th>
            <th class="py-2">{m.common_actions()}</th>
          </tr>
        </thead>
        <tbody>
          {#each roles as role (role.id)}
            <tr class="border-b border-slate-100 dark:border-slate-800">
              <td class="py-2 pr-3 font-medium">{role.name}</td>
              <td class="py-2 pr-3 font-mono text-xs">{role.key}</td>
              <td class="py-2 pr-3 text-slate-500">{role.description}</td>
              <td class="py-2 pr-3">
                {role.is_system ? m.admin_systemBadge() : m.admin_customBadge()}
              </td>
              <td class="py-2">
                <span class="flex gap-2 text-xs">
                  <button
                    type="button"
                    class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                    onclick={() => openEdit(role)}
                  >
                    {m.common_edit()}
                  </button>
                  <button
                    type="button"
                    class="rounded border px-2 py-1 text-red-600 hover:bg-red-50"
                    onclick={() => remove(role)}
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
    title={editing ? m.admin_editRoleTitle() : m.common_create()}
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
      {#if !editing}
        <label class="flex flex-col gap-1 text-sm">
          {m.admin_uniqueKey()}
          <input
            class={input}
            bind:value={form.key}
            placeholder={m.admin_keyPlaceholder()}
          />
        </label>
      {/if}
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_roleNameLabel()}
        <input
          class={input}
          bind:value={form.name}
          placeholder={m.admin_roleNamePlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_briefDescription()}
        <input
          class={input}
          bind:value={form.description}
          placeholder={m.admin_descriptionPlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_colSystemPrompt()}
        <textarea class={input} rows="6" bind:value={form.prompt}></textarea>
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" bind:checked={form.is_system} />
        {m.common_system()}
      </label>
      <button
        type="submit"
        class="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
      >
        {m.admin_saveRole()}
      </button>
    </form>
  </Modal>
{/if}
