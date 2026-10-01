<script lang="ts">
  import { parseBlocks, parseInline, type Inline } from "./markdown.ts";

  let { text }: { text: string } = $props();

  const blocks = $derived(parseBlocks(text ?? ""));
</script>

{#snippet inline(segment: Inline)}
  {#if segment.type === "bold"}
    <strong>{segment.text}</strong>
  {:else if segment.type === "italic"}
    <em>{segment.text}</em>
  {:else if segment.type === "code"}
    <code class="rounded bg-black/10 px-1 py-0.5 text-xs dark:bg-white/10">
      {segment.text}
    </code>
  {:else if segment.type === "link"}
    <a
      class="underline"
      href={segment.href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {segment.text}
    </a>
  {:else}
    {segment.text}
  {/if}
{/snippet}

<div class="markdown space-y-2 break-words text-sm leading-relaxed">
  {#each blocks as block, index (index)}
    {#if block.type === "heading"}
      <p class={block.level <= 2 ? "font-semibold" : "font-medium"}>
        {#each parseInline(block.text) as segment, i (i)}{@render inline(
            segment,
          )}{/each}
      </p>
    {:else if block.type === "code"}
      <pre
        class="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100"><code
          >{block.code}</code
        ></pre>
    {:else if block.type === "list"}
      {#if block.ordered}
        <ol class="list-decimal space-y-1 pl-5">
          {#each block.items as item, i (i)}
            <li>
              {#each parseInline(item) as segment, j (j)}{@render inline(
                  segment,
                )}{/each}
            </li>
          {/each}
        </ol>
      {:else}
        <ul class="list-disc space-y-1 pl-5">
          {#each block.items as item, i (i)}
            <li>
              {#each parseInline(item) as segment, j (j)}{@render inline(
                  segment,
                )}{/each}
            </li>
          {/each}
        </ul>
      {/if}
    {:else if block.type === "quote"}
      <blockquote class="border-l-2 border-slate-400 pl-3 italic">
        {#each parseInline(block.text) as segment, i (i)}{@render inline(
            segment,
          )}{/each}
      </blockquote>
    {:else}
      <p>
        {#each parseInline(block.text) as segment, i (i)}{@render inline(
            segment,
          )}{/each}
      </p>
    {/if}
  {/each}
</div>
