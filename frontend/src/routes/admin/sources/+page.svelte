<script lang="ts">
  import { onMount } from "svelte";
  import { m } from "$lib/paraglide/messages.js";
  import Modal from "$lib/admin/Modal.svelte";
  import { messageOf } from "$lib/admin/error";
  import {
    createSource,
    deleteSource,
    listSources,
    updateSource,
    type Source,
  } from "$lib/api/sources";

  const input =
    "rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-emerald-500 dark:border-slate-600";

  let sources = $state<Source[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let editing = $state<Source | null>(null);
  let creating = $state(false);
  let form = $state({ name: "", content: "" });

  async function load() {
    loading = true;
    try {
      sources = await listSources();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function openCreate() {
    form = { name: "", content: "" };
    creating = true;
  }

  function openEdit(source: Source) {
    form = { name: source.name, content: source.content };
    editing = source;
  }

  async function submit() {
    error = null;
    try {
      if (editing) {
        await updateSource(editing.id, form);
      } else {
        await createSource(form.name, form.content);
      }
      editing = null;
      creating = false;
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }

  async function remove(source: Source) {
    if (!confirm(`${m.admin_confirmDeleteTitle()} ${source.name}`)) return;
    try {
      await deleteSource(source.id);
      await load();
    } catch (cause) {
      error = messageOf(cause, m.common_error());
    }
  }
</script>

<section>
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">{m.admin_viewKnowledgeBases()}</h1>
    <button
      type="button"
      class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
      onclick={openCreate}
    >
      {m.admin_createSourceTitle()}
    </button>
  </header>
  <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">
    {m.admin_sourceSubtitle()}
  </p>

  {#if error}<p class="mt-3 text-sm text-red-600">{error}</p>{/if}

  {#if loading}
    <p class="mt-4 text-sm text-slate-500">{m.common_loading()}</p>
  {:else if sources.length === 0}
    <p class="mt-4 text-sm text-slate-500">{m.admin_noSources()}</p>
  {:else}
    <div class="mt-4 overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead
          class="border-b border-slate-200 text-slate-500 dark:border-slate-700"
        >
          <tr>
            <th class="py-2 pr-3">{m.admin_baseNameLabel()}</th>
            <th class="py-2 pr-3">{m.admin_colContentExcerpt()}</th>
            <th class="py-2">{m.common_actions()}</th>
          </tr>
        </thead>
        <tbody>
          {#each sources as source (source.id)}
            <tr class="border-b border-slate-100 dark:border-slate-800">
              <td class="py-2 pr-3 font-medium">{source.name}</td>
              <td class="max-w-md truncate py-2 pr-3 text-slate-500">
                {source.content.slice(0, 120) || m.admin_noContentLoaded()}
              </td>
              <td class="py-2">
                <span class="flex gap-2 text-xs">
                  <button
                    type="button"
                    class="rounded border px-2 py-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                    onclick={() => openEdit(source)}
                  >
                    {m.common_edit()}
                  </button>
                  <button
                    type="button"
                    class="rounded border px-2 py-1 text-red-600 hover:bg-red-50"
                    onclick={() => remove(source)}
                  >
                    {m.common_delete()}
                  </button>
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{#if creating || editing}
  <Modal
    title={editing ? m.admin_editSourceTitle() : m.admin_createSourceTitle()}
    onclose={() => {
      creating = false;
      editing = null;
    }}
  >
    <form
      class="flex flex-col gap-3"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_baseNameLabel()}
        <input
          class={input}
          bind:value={form.name}
          placeholder={m.admin_baseNamePlaceholder()}
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        {m.admin_contentDocuments()}
        <textarea
          class={input}
          rows="8"
          bind:value={form.content}
          placeholder={m.admin_contentPlaceholder()}
        ></textarea>
      </label>
      <button
        type="submit"
        class="mt-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
      >
        {m.admin_saveBase()}
      </button>
    </form>
  </Modal>
{/if}
