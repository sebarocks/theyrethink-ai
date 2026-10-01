<script lang="ts">
  import { onDestroy, onMount, type Snippet } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import { streamMessage } from "$lib/api/chat";
  import { clearMemory, listMemory, type MemoryFact } from "$lib/api/memory";
  import {
    createThread,
    deleteThread,
    listMessages,
    listThreads,
    renameThread,
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

  // Cancelación y secuenciación: el usuario puede cambiar de hilo mientras el agente
  // responde. Sin esto, los tokens de un hilo se escribirían en el array del otro.
  let controller: AbortController | null = null;
  let requestSeq = 0;
  let loadSeq = 0;

  // Memoria visible y olvidable del usuario para este agente (D10).
  let memoryOpen = $state(false);
  let memoryLoading = $state(false);
  let facts = $state<MemoryFact[]>([]);
  let memoryNotice = $state<string | null>(null);
  let confirmingClear = $state(false);

  // Renombrado de hilo en línea.
  let renaming = $state<number | null>(null);
  let renameValue = $state("");

  function cancelStream() {
    controller?.abort();
    controller = null;
  }

  function isAbort(cause: unknown): boolean {
    return (
      typeof cause === "object" &&
      cause !== null &&
      (cause as { name?: string }).name === "AbortError"
    );
  }

  function describe(cause: unknown): string {
    return cause instanceof Error ? cause.message : String(cause);
  }

  async function refreshThreads() {
    threads = (await listThreads()).filter(
      (thread) => thread.agent_id === agentId,
    );
  }

  async function selectThread(threadId: number) {
    cancelStream();
    streaming = false;
    const seq = ++loadSeq;
    currentId = threadId;
    const loaded = await listMessages(threadId);
    // Otra selección llegó después: esta respuesta ya no es la vigente.
    if (seq === loadSeq) messages = loaded;
  }

  async function startThread() {
    const thread = await createThread(agentId);
    await refreshThreads();
    await selectThread(thread.id);
  }

  async function removeThread(threadId: number) {
    if (threadId === currentId) cancelStream();
    await deleteThread(threadId);
    if (currentId === threadId) {
      currentId = null;
      messages = [];
    }
    await refreshThreads();
  }

  async function toggleMemory() {
    memoryOpen = !memoryOpen;
    memoryNotice = null;
    confirmingClear = false;
    if (memoryOpen) await loadMemory();
  }

  async function loadMemory() {
    memoryLoading = true;
    try {
      facts = await listMemory(agentId);
    } catch (cause) {
      error = describe(cause);
    } finally {
      memoryLoading = false;
    }
  }

  async function forgetMemory() {
    try {
      await clearMemory(agentId);
      facts = [];
      confirmingClear = false;
      memoryNotice = m.chat_memoryCleared();
    } catch (cause) {
      error = describe(cause);
    }
  }

  function startRename(thread: Thread) {
    renaming = thread.id;
    renameValue = thread.title;
  }

  async function confirmRename() {
    const threadId = renaming;
    const title = renameValue.trim();
    renaming = null;
    if (threadId === null || title === "") return;
    try {
      await renameThread(threadId, title);
      await refreshThreads();
    } catch (cause) {
      error = describe(cause);
    }
  }

  async function send(text: string) {
    try {
      if (currentId === null) await startThread();
    } catch (cause) {
      error = describe(cause);
      return;
    }
    const threadId = currentId;
    if (threadId === null) return;

    cancelStream();
    const requestId = ++requestSeq;
    const active = new AbortController();
    controller = active;

    messages = [
      ...messages,
      { role: "user", text },
      { role: "assistant", text: "" },
    ];
    const last = messages.length - 1;
    streaming = true;
    error = null;
    try {
      for await (const event of streamMessage(threadId, text, active.signal)) {
        // Respuesta obsoleta: se cambió de hilo o se lanzó otro envío.
        if (requestId !== requestSeq || currentId !== threadId) return;
        if (event.type === "chunk") {
          messages[last].text += event.text;
        } else if (event.type === "error") {
          error = event.detail;
        }
      }
    } catch (cause) {
      if (!isAbort(cause) && requestId === requestSeq) error = describe(cause);
    } finally {
      if (requestId === requestSeq) {
        streaming = false;
        controller = null;
        await refreshThreads().catch(() => {});
      }
    }
  }

  onMount(async () => {
    try {
      await refreshThreads();
      if (threads.length > 0) await selectThread(threads[0].id);
    } catch (cause) {
      error = describe(cause);
    }
  });

  onDestroy(cancelStream);
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
          {#if renaming === thread.id}
            <form
              class="flex flex-1 items-center gap-1"
              onsubmit={(event) => {
                event.preventDefault();
                void confirmRename();
              }}
            >
              <input
                class="min-w-0 flex-1 rounded border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-600"
                aria-label={m.chat_renameChat()}
                bind:value={renameValue}
              />
              <button
                type="submit"
                class="rounded px-1 text-xs text-emerald-600"
                aria-label={m.common_save()}
              >
                ✓
              </button>
              <button
                type="button"
                class="rounded px-1 text-xs text-slate-500"
                aria-label={m.common_cancel()}
                onclick={() => (renaming = null)}
              >
                ×
              </button>
            </form>
          {:else}
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
              class="rounded px-1 text-xs text-slate-500 hover:text-emerald-600"
              aria-label={m.chat_renameChat()}
              onclick={() => startRename(thread)}
            >
              ✎
            </button>
            <button
              type="button"
              class="rounded px-1 text-xs text-slate-500 hover:text-red-600"
              aria-label={m.common_delete()}
              onclick={() => removeThread(thread.id)}
            >
              ×
            </button>
          {/if}
        </li>
      {/each}
    </ul>
  </aside>

  <section class="flex min-h-0 flex-1 flex-col">
    <header
      class="flex items-center justify-between gap-2 border-b border-slate-200 p-3 dark:border-slate-700"
    >
      <span class="font-semibold">{agentName}</span>
      <button
        type="button"
        class="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
        aria-expanded={memoryOpen}
        onclick={toggleMemory}
      >
        {m.chat_tabMemory()}
      </button>
    </header>

    {#if memoryOpen}
      <section
        class="space-y-2 border-b border-slate-200 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-800/50"
        aria-label={m.chat_tabMemory()}
      >
        <div>
          <h2 class="font-semibold">{m.chat_learnedFacts()}</h2>
          <p class="text-xs text-slate-500">{m.chat_learnedFactsHelp()}</p>
        </div>
        {#if memoryLoading}
          <p class="text-xs text-slate-500">{m.common_loading()}</p>
        {:else if facts.length === 0}
          <p class="text-xs text-slate-500">{m.chat_noLearnedFacts()}</p>
        {:else}
          <ul class="space-y-1">
            {#each facts as fact, index (index)}
              <li class="rounded bg-white px-2 py-1 text-xs dark:bg-slate-900">
                {fact.content}
              </li>
            {/each}
          </ul>
        {/if}
        {#if memoryNotice}
          <p class="text-xs text-emerald-600">{memoryNotice}</p>
        {/if}
        {#if confirmingClear}
          <div class="rounded border border-red-300 p-2 dark:border-red-800">
            <p class="text-xs">{m.chat_clearMemoryConfirm()}</p>
            <div class="mt-2 flex gap-2">
              <button
                type="button"
                class="rounded bg-red-600 px-2 py-1 text-xs text-white"
                onclick={forgetMemory}
              >
                {m.common_confirm()}
              </button>
              <button
                type="button"
                class="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
                onclick={() => (confirmingClear = false)}
              >
                {m.common_cancel()}
              </button>
            </div>
          </div>
        {:else}
          <button
            type="button"
            class="rounded border border-red-300 px-2 py-1 text-xs text-red-600 disabled:opacity-50 dark:border-red-800"
            disabled={facts.length === 0}
            onclick={() => (confirmingClear = true)}
          >
            {m.chat_clearMemory()}
          </button>
        {/if}
      </section>
    {/if}

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
