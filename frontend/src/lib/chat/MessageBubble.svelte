<script lang="ts">
  import type { Message } from "$lib/api/threads";

  let { message }: { message: Message } = $props();

  const isUser = $derived(message.role === "user");
</script>

<div class="flex" class:justify-end={isUser}>
  <div
    class={[
      "max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm",
      isUser
        ? "bg-emerald-600 text-white"
        : "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-slate-100",
    ]}
  >
    {message.text}
  </div>
</div>
