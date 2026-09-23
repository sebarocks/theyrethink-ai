<script lang="ts">
  import { m } from "$lib/paraglide/messages.js";
  import { listAgents, type Agent } from "$lib/api/agents";
  import { session } from "$lib/session";

  let agents = $state<Agent[]>([]);

  $effect(() => {
    if ($session.user) {
      void listAgents().then((result) => (agents = result));
    }
  });
</script>

<main class="mx-auto max-w-3xl p-8">
  <h1 class="text-2xl font-bold">{m.common_appName()}</h1>
  <p class="mt-1 text-slate-600 dark:text-slate-300">{m.common_tagline()}</p>

  <ul class="mt-8 space-y-3">
    {#each agents as agent (agent.id)}
      <li
        class="flex items-center justify-between rounded-lg border border-slate-200 p-4 dark:border-slate-700"
      >
        <span class="font-medium">{agent.name}</span>
        <span class="flex gap-2 text-sm">
          <a
            class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
            href={`/web/${agent.id}`}
          >
            Web
          </a>
          <a
            class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
            href={`/whatsapp/${agent.id}`}
          >
            WhatsApp
          </a>
          <a
            class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
            href={`/telegram/${agent.id}`}
          >
            Telegram
          </a>
        </span>
      </li>
    {/each}
  </ul>
</main>
