<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import { listAgents } from "$lib/api/agents";
  import { listRoles } from "$lib/api/roles";
  import { listSources } from "$lib/api/sources";
  import { listUsers } from "$lib/api/users";
  import { listAdminThreads } from "$lib/api/admin";

  let counts = $state<{
    agents: number;
    roles: number;
    sources: number;
    users: number;
    threads: number;
  } | null>(null);
  let error = $state(false);

  onMount(async () => {
    try {
      const [agents, roles, sources, users, threads] = await Promise.all([
        listAgents(),
        listRoles(),
        listSources(),
        listUsers(),
        listAdminThreads(),
      ]);
      counts = {
        agents: agents.length,
        roles: roles.length,
        sources: sources.length,
        users: users.length,
        threads: threads.length,
      };
    } catch {
      error = true;
    }
  });
</script>

<section>
  <h1 class="text-2xl font-bold">{m.admin_systemSummary()}</h1>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_systemSummarySub()}
  </p>

  {#if error}
    <p class="mt-4 text-sm text-red-600">{m.common_error()}</p>
  {:else if counts === null}
    <p class="mt-4 text-sm text-slate-500">{m.common_loading()}</p>
  {:else}
    <div class="mt-6 grid grid-cols-2 gap-4 md:grid-cols-3">
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-3xl font-bold">{counts.agents}</p>
        <p class="mt-1 text-sm text-slate-500">{m.admin_kpiActiveAgents()}</p>
      </div>
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-3xl font-bold">{counts.roles}</p>
        <p class="mt-1 text-sm text-slate-500">{m.admin_kpiPromptsSqlite()}</p>
      </div>
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-3xl font-bold">{counts.sources}</p>
        <p class="mt-1 text-sm text-slate-500">
          {m.admin_kpiModularKnowledge()}
        </p>
      </div>
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-3xl font-bold">{counts.users}</p>
        <p class="mt-1 text-sm text-slate-500">{m.admin_kpiActiveAccounts()}</p>
      </div>
      <div class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
        <p class="text-3xl font-bold">{counts.threads}</p>
        <p class="mt-1 text-sm text-slate-500">{m.admin_colConversations()}</p>
      </div>
    </div>
  {/if}
</section>
