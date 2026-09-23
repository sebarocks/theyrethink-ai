<script lang="ts">
  import type { Message } from "$lib/api/threads";
  import Chat from "../Chat.svelte";

  let { agentId, agentName }: { agentId: number; agentName: string } = $props();

  // Atajos de comandos, no lógica propia (A10/D3).
  const commands = ["/start", "/bases", "/memoria"];
</script>

<div
  class="mx-auto h-[calc(100vh-3.5rem)] max-w-md border-x border-slate-200 bg-[#517da2] dark:border-slate-700 dark:bg-slate-900"
>
  {#snippet bubble(message: Message)}
    <div class="flex" class:justify-end={message.role === "user"}>
      <div
        class={[
          "max-w-[80%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm text-white",
          message.role === "user" ? "bg-[#2b5278]" : "bg-[#182533]",
        ]}
      >
        {message.text}
      </div>
    </div>
  {/snippet}

  <Chat {agentId} {agentName} {bubble} {commands} />
</div>
