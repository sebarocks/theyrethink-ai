<script lang="ts">
  import { onMount, type Snippet } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import { streamMessage } from "$lib/api/chat";
  import {
    createThread,
    deleteThread,
    listMessages,
    listThreads,
    type Message,
    type Thread,
  } from "$lib/api/threads";
  import Composer from "./Composer.svelte";
  import MessageBubble from "./MessageBubble.svelte";

  /**
   * Lógica única del chat (A10/D3). Las skins solo cambian la cáscara visual: pasan `bubble`
   * y `commands`, nunca ramifican comportamiento.
   */
  let {
    agentId,
    agentName,
    bubble,
    commands = [],
  }: {
    agentId: number;
    agentName: string;
    bubble?: Snippet<[Message]>;
    commands?: string[];
  } = $props();

  let threads = $state<Thread[]>([]);
  let currentId = $state<number | null>(null);
  let messages = $state<Message[]>([]);
  let streaming = $state(false);
  let error = $state<string | null>(null);

  async function refreshThreads() {
    threads = (await listThreads()).filter(
      (thread) => thread.agent_id === agentId,
    );
  }

  async function selectThread(threadId: number) {
    currentId = threadId;
    messages = await listMessages(threadId);
  }

  async function startThread() {
    const thread = await createThread(agentId);
    await refreshThreads();
    await selectThread(thread.id);
  }

  async function removeThread(threadId: number) {
    await deleteThread(threadId);
    if (currentId === threadId) {
      currentId = null;
      messages = [];
    }
    await refreshThreads();
  }

  async function send(text: string) {
    if (currentId === null) await startThread();
    const threadId = currentId;
    if (threadId === null) return;

    messages = [
      ...messages,
      { role: "user", text },
      { role: "assistant", text: "" },
    ];
    const last = messages.length - 1;
    streaming = true;
    error = null;
    try {
      for await (const event of streamMessage(threadId, text)) {
        if (event.type === "chunk") {
          messages[last].text += event.text;
        } else if (event.type === "error") {
          error = event.detail;
        }
      }
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      streaming = false;
      await refreshThreads();
    }
  }

  onMount(async () => {
    await refreshThreads();
    if (threads.length > 0) await selectThread(threads[0].id);
  });
</script>

<div class="flex h-full min-h-0">
  <aside
    class="hidden w-64 flex-col border-r border-slate-200 dark:border-slate-700 sm:flex"
  >
    <button
      type="button"
      class="m-3 rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
      onclick={startThread}
    >
      {m.chat_newChat()}
    </button>
    <ul class="flex-1 overflow-y-auto px-2 pb-2">
      {#each threads as thread (thread.id)}
        <li class="flex items-center gap-1">
          <button
            type="button"
            class="flex-1 truncate rounded px-2 py-1 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            class:font-semibold={thread.id === currentId}
            onclick={() => selectThread(thread.id)}
          >
            {thread.title}
          </button>
          <button
            type="button"
            class="rounded px-2 py-1 text-xs text-slate-500 hover:text-red-600"
            aria-label={m.common_delete()}
            onclick={() => removeThread(thread.id)}
          >
            ×
          </button>
        </li>
      {/each}
    </ul>
  </aside>

  <section class="flex min-h-0 flex-1 flex-col">
    <header
      class="border-b border-slate-200 p-3 font-semibold dark:border-slate-700"
    >
      {agentName}
    </header>

    <div class="flex-1 space-y-3 overflow-y-auto p-4">
      {#if messages.length === 0}
        <p class="text-center text-sm text-slate-500">
          {m.chat_emptyHistory()}
        </p>
      {/if}
      {#each messages as message, index (index)}
        {#if bubble}
          {@render bubble(message)}
        {:else}
          <MessageBubble {message} />
        {/if}
      {/each}
      {#if streaming}
        <p class="text-xs text-slate-500">{m.chat_thinking()}</p>
      {/if}
      {#if error}
        <p class="text-xs text-red-600">{error}</p>
      {/if}
    </div>

    {#if commands.length > 0}
      <div class="flex flex-wrap gap-2 px-3 pt-2">
        {#each commands as command (command)}
          <button
            type="button"
            class="rounded-full border border-slate-300 px-3 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
            onclick={() => send(command)}
          >
            {command}
          </button>
        {/each}
      </div>
    {/if}

    <Composer {agentName} disabled={streaming} onSend={send} />
  </section>
</div>
