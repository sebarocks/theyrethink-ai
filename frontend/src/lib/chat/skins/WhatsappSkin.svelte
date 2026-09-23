<script lang="ts">
  import type { Message } from "$lib/api/threads";
  import Chat from "../Chat.svelte";

  let { agentId, agentName }: { agentId: number; agentName: string } = $props();
</script>

<div
  class="mx-auto h-[calc(100vh-3.5rem)] max-w-md border-x border-slate-200 bg-[#efeae2] dark:border-slate-700 dark:bg-slate-900"
>
  {#snippet bubble(message: Message)}
    <div class="flex" class:justify-end={message.role === "user"}>
      <div
        class={[
          "max-w-[80%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm text-slate-900",
          message.role === "user"
            ? "bg-[#d9fdd3]"
            : "bg-white dark:bg-slate-800 dark:text-slate-100",
        ]}
      >
        {message.text}
      </div>
    </div>
  {/snippet}

  <Chat {agentId} {agentName} {bubble} />
</div>
