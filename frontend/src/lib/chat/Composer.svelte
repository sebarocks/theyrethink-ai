<script lang="ts">
  import { m } from "$lib/paraglide/messages.js";

  let {
    agentName,
    disabled = false,
    onSend,
  }: {
    agentName: string;
    disabled?: boolean;
    onSend: (text: string) => void;
  } = $props();

  let text = $state("");

  function submit(event: SubmitEvent) {
    event.preventDefault();
    const value = text.trim();
    if (value === "" || disabled) return;
    text = "";
    onSend(value);
  }
</script>

<form
  class="flex items-end gap-2 border-t border-slate-200 p-3 dark:border-slate-700"
  onsubmit={submit}
>
  <textarea
    class="min-h-10 flex-1 resize-none rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600"
    rows="1"
    placeholder={m.chat_typePlaceholder({ name: agentName })}
    bind:value={text}
    {disabled}
  ></textarea>
  <button
    type="submit"
    class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
    {disabled}
  >
    {m.chat_send()}
  </button>
</form>
