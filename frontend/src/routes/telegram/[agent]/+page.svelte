<script lang="ts">
  import TelegramSkin from "$lib/chat/skins/TelegramSkin.svelte";
  import type { Agent } from "$lib/api/agents";

  let { data }: { data: { agent: Agent } } = $props();
</script>

<TelegramSkin agentId={data.agent.id} agentName={data.agent.name} />
