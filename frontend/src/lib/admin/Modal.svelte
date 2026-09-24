<script lang="ts">
  import type { Snippet } from "svelte";
  import { m } from "$lib/paraglide/messages.js";

  let {
    title,
    onclose,
    children,
  }: { title: string; onclose: () => void; children: Snippet } = $props();
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
  role="presentation"
  onclick={onclose}
>
  <div
    class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-slate-900"
    role="dialog"
    aria-modal="true"
    onclick={(event) => event.stopPropagation()}
  >
    <header class="mb-4 flex items-center justify-between">
      <h2 class="text-lg font-bold">{title}</h2>
      <button
        type="button"
        class="rounded px-2 py-1 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
        onclick={onclose}
      >
        {m.common_close()}
      </button>
    </header>
    {@render children()}
  </div>
</div>
