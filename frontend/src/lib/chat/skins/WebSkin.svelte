<script lang="ts">
  import Chat from "../Chat.svelte";

  let { agentId, agentName }: { agentId: number; agentName: string } = $props();
</script>

<div class="h-[calc(100vh-3.5rem)]">
  <Chat {agentId} {agentName} />
</div>
