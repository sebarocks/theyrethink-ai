<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import { messageOf } from "$lib/admin/error";
  import { listAgents, type Agent } from "$lib/api/agents";
  import {
    listAdminMessages,
    listAdminThreads,
    type AdminThread,
    type Message,
  } from "$lib/api/admin";

  let agents = $state<Agent[]>([]);
  let threads = $state<AdminThread[]>([]);
  let messages = $state<Message[]>([]);
  let selected = $state<AdminThread | null>(null);
  let agentFilter = $state("");
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function loadThreads() {
    loading = true;
    try {
      threads = await listAdminThreads(
        agentFilter === "" ? undefined : Number(agentFilter),
      );
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    try {
      agents = await listAgents();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
    await loadThreads();
  });

  async function select(thread: AdminThread) {
    selected = thread;
    messages = [];
    try {
      messages = await listAdminMessages(thread.id);
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }
</script>

<section>
  <h1 class="text-2xl font-bold">{m.admin_historyMaintainer()}</h1>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_selectThreadToInspect()}
  </p>

  <label class="mt-4 flex items-center gap-2 text-sm">
    {m.admin_filterByAgent()}
    <select
      class="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600"
      bind:value={agentFilter}
      onchange={() => void loadThreads()}
    >
      <option value="">{m.admin_allAgents()}</option>
      {#each agents as agent (agent.id)}
        <option value={String(agent.id)}>{agent.name}</option>
      {/each}
    </select>
  </label>

  {#if error}<p class="mt-3 text-sm text-red-600">{error}</p>{/if}

  <div class="mt-4 grid gap-4 md:grid-cols-[18rem_1fr]">
    <div
      class="max-h-[70vh] overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700"
    >
      {#if loading}
        <p class="p-3 text-sm text-slate-500">{m.common_loading()}</p>
      {:else if threads.length === 0}
        <p class="p-3 text-sm text-slate-500">{m.admin_noMessagesYet()}</p>
      {:else}
        <ul>
          {#each threads as thread (thread.id)}
            <li>
              <button
                type="button"
                class="w-full border-b border-slate-100 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800 {selected?.id ===
                thread.id
                  ? 'bg-slate-100 dark:bg-slate-800'
                  : ''}"
                onclick={() => void select(thread)}
              >
                <span class="block truncate font-medium">{thread.title}</span>
                <span class="block truncate text-xs text-slate-500">
                  {thread.agent_name} · {thread.username} · {thread.message_count}
                  {m.admin_messagesWord()}
                </span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <h2 class="text-sm font-semibold">{m.admin_sessionMessagesExplorer()}</h2>
      {#if selected === null}
        <p class="mt-3 text-sm text-slate-500">
          {m.admin_selectConversation()}
        </p>
      {:else if messages.length === 0}
        <p class="mt-3 text-sm text-slate-500">{m.admin_noMessagesYet()}</p>
      {:else}
        <ul class="mt-3 flex flex-col gap-3">
          {#each messages as message, index (index)}
            <li
              class="rounded-lg px-3 py-2 text-sm {message.role === 'user'
                ? 'bg-slate-100 dark:bg-slate-800'
                : ''}"
            >
              <p class="text-xs font-semibold text-slate-500">{message.role}</p>
              <p class="whitespace-pre-wrap">{message.text}</p>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </div>
</section>
