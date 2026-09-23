<script lang="ts">
  import WebSkin from "$lib/chat/skins/WebSkin.svelte";
  import type { Agent } from "$lib/api/agents";

  let { data }: { data: { agent: Agent } } = $props();
</script>

<WebSkin agentId={data.agent.id} agentName={data.agent.name} />
