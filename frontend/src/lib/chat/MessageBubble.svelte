<script lang="ts">
  import type { Message } from "$lib/api/threads";
  import Markdown from "./Markdown.svelte";

  let { message }: { message: Message } = $props();

  const isUser = $derived(message.role === "user");
</script>

<div class="flex" class:justify-end={isUser}>
  <div
    class={[
      "max-w-[80%] rounded-2xl px-4 py-2 text-sm",
      isUser
        ? "bg-emerald-600 text-white"
        : "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-slate-100",
    ]}
  >
    {#if isUser}
      <p class="whitespace-pre-wrap">{message.text}</p>
    {:else}
      <Markdown text={message.text} />
    {/if}
  </div>
</div>
