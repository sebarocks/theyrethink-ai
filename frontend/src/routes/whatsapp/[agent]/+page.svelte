<script lang="ts">
  import WhatsappSkin from "$lib/chat/skins/WhatsappSkin.svelte";
  import type { Agent } from "$lib/api/agents";

  let { data }: { data: { agent: Agent } } = $props();
</script>

<WhatsappSkin agentId={data.agent.id} agentName={data.agent.name} />
