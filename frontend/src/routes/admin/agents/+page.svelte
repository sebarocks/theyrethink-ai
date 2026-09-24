<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import Modal from "$lib/admin/Modal.svelte";
  import { messageOf } from "$lib/admin/error";
  import {
    agentAvatarUrl,
    createAgent,
    deleteAgent,
    deleteAgentAvatar,
    listAgents,
    updateAgent,
    uploadAgentAvatar,
    type Agent,
  } from "$lib/api/agents";
  import { listRoles, type Role } from "$lib/api/roles";
  import {
    attachSource,
    detachSource,
    listAgentSources,
    listSources,
    type Source,
  } from "$lib/api/sources";

  const input =
    "rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600";

  let agents = $state<Agent[]>([]);
  let roles = $state<Role[]>([]);
  let sources = $state<Source[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let creating = $state(false);
  let editing = $state<Agent | null>(null);
  let managing = $state<Agent | null>(null);
  let attached = $state<number[]>([]);
  let avatarFile = $state<File | null>(null);

  let form = $state({
    name: "",
    profile: "",
    role_key: "" as string,
    custom_identity: "",
  });

  async function load() {
    loading = true;
    try {
      [agents, roles, sources] = await Promise.all([
        listAgents(),
        listRoles(),
        listSources(),
      ]);
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function openCreate() {
    form = { name: "", profile: "", role_key: "", custom_identity: "" };
    avatarFile = null;
    creating = true;
  }

  function openEdit(agent: Agent) {
    form = {
      name: agent.name,
      profile: agent.profile,
      role_key: agent.role_key ?? "",
      custom_identity: agent.custom_identity ?? "",
    };
    avatarFile = null;
    editing = agent;
  }

  async function submit() {
    error = null;
    const payload = {
      name: form.name,
      profile: form.profile,
      role_key: form.role_key === "" ? null : form.role_key,
      custom_identity:
        form.custom_identity === "" ? null : form.custom_identity,
    };
    try {
      const agent = editing
        ? await updateAgent(editing.id, payload)
        : await createAgent(payload);
      if (avatarFile !== null) await uploadAgentAvatar(agent.id, avatarFile);
      creating = false;
      editing = null;
      avatarFile = null;
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function removeAvatar(agent: Agent) {
    try {
      await deleteAgentAvatar(agent.id);
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function remove(agent: Agent) {
    if (!confirm(`${m.admin_deleteAgentTitle()}: ${agent.name}`)) return;
    try {
      await deleteAgent(agent.id);
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function openManage(agent: Agent) {
    editing = null;
    creating = false;
    managing = agent;
    try {
      attached = (await listAgentSources(agent.id)).map((source) => source.id);
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function toggleSource(source: Source) {
    if (managing === null) return;
    try {
      if (attached.includes(source.id)) {
        await detachSource(managing.id, source.id);
        attached = attached.filter((id) => id !== source.id);
      } else {
        await attachSource(managing.id, source.id);
        attached = [...attached, source.id];
      }
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }
</script>

<section>
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">{m.admin_allAgents()}</h1>
    <button
      type="button"
      class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
      onclick={openCreate}
    >
      {m.admin_createAgentTitle()}
    </button>
  </header>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_agentConfigSubtitle()}
  </p>

  {#if error}<p class="mt-3 text-sm text-red-600">{error}</p>{/if}

  {#if loading}
    <p class="mt-4 text-sm text-slate-500">{m.common_loading()}</p>
  {:else if agents.length === 0}
    <p class="mt-4 text-sm text-slate-500">{m.admin_noAgents()}</p>
  {:else}
    <div class="mt-4 grid gap-3 md:grid-cols-2">
      {#each agents as agent (agent.id)}
        <article
          class="rounded-xl border border-slate-200 p-4 dark:border-slate-700"
        >
          <div class="flex items-center gap-3">
            {#if agent.avatar_url}
              <img
                src={agentAvatarUrl(agent.id)}
                alt={agent.name}
                class="h-10 w-10 rounded-full object-cover"
              />
            {/if}
            <div class="min-w-0">
              <p class="truncate font-semibold">{agent.name}</p>
              <p class="truncate text-xs text-slate-500">
                {agent.role_key ?? m.admin_defaultBasic()}
              </p>
            </div>
          </div>
          <p
            class="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-300"
          >
            {agent.profile || m.admin_noDescription()}
          </p>
          <div class="mt-3 flex flex-wrap gap-2 text-xs">
            <button
              type="button"
              class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
              onclick={() => openManage(agent)}
            >
              {m.admin_associatedKnowledgeBases()}
            </button>
            <button
              type="button"
              class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
              onclick={() => openEdit(agent)}
            >
              {m.common_edit()}
            </button>
            {#if agent.avatar_url}
              <button
                type="button"
                class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                onclick={() => removeAvatar(agent)}
              >
                {m.admin_remove()}
              </button>
            {/if}
            <button
              type="button"
              class="rounded border px-2 py-1 text-red-600 hover:bg-red-50"
              onclick={() => remove(agent)}
            >
              {m.common_delete()}
            </button>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</section>

{#if creating || editing}
  <Modal
    title={editing ? m.admin_editAgentTitle() : m.admin_createAgentTitle()}
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
        {m.admin_uniqueAgentName()}
        <input
          class={input}
          bind:value={form.name}
          placeholder={m.admin_agentNamePlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_identityRoleLabel()}
        <select class={input} bind:value={form.role_key}>
          <option value="">—</option>
          {#each roles as role (role.id)}
            <option value={role.key}>{role.name}</option>
          {/each}
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_infoPersonality()}
        <textarea
          class={input}
          rows="5"
          bind:value={form.profile}
          placeholder={m.admin_infoPersonalityPlaceholder()}
        ></textarea>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_customPrompt()}
        <textarea
          class={input}
          rows="5"
          bind:value={form.custom_identity}
          placeholder={m.admin_customPromptPlaceholder()}
        ></textarea>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_agentImageAvatar()}
        <input
          class="text-sm"
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          onchange={(event) => {
            avatarFile = event.currentTarget.files?.[0] ?? null;
          }}
        />
      </label>
      <button
        type="submit"
        class="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
      >
        {m.admin_saveAgent()}
      </button>
    </form>
  </Modal>
{/if}

{#if managing}
  <Modal
    title={`${m.admin_associatedKnowledgeBases()} · ${managing.name}`}
    onclose={() => (managing = null)}
  >
    {#if sources.length === 0}
      <p class="text-sm text-slate-500">{m.admin_noSources()}</p>
    {:else}
      <ul class="flex flex-col gap-2">
        {#each sources as source (source.id)}
          <li>
            <label class="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={attached.includes(source.id)}
                onchange={() => void toggleSource(source)}
              />
              {source.name}
            </label>
          </li>
        {/each}
      </ul>
    {/if}
  </Modal>
{/if}
