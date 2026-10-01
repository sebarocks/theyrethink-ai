<script lang="ts">
  import { m } from "$lib/paraglide/messages.js";
  import { listAgents, type Agent } from "$lib/api/agents";
  import { session } from "$lib/session";

  let agents = $state<Agent[]>([]);
  let termsOpen = $state(false);

  $effect(() => {
    if ($session.user) {
      void listAgents().then((result) => (agents = result));
    }
  });

  // Las funciones se evalúan en el render para que el cambio de idioma se refleje.
  const features = [
    {
      title: () => m.features_f1Title(),
      description: () => m.features_f1Desc(),
      foot: () => m.features_f1Foot(),
    },
    {
      title: () => m.features_f2Title(),
      description: () => m.features_f2Desc(),
      foot: () => m.features_f2Foot(),
    },
    {
      title: () => m.features_f3Title(),
      description: () => m.features_f3Desc(),
      foot: () => m.features_f3Foot(),
    },
    {
      title: () => m.features_f4Title(),
      description: () => m.features_f4Desc(),
      foot: () => m.features_f4Foot(),
    },
    {
      title: () => m.features_f5Title(),
      description: () => m.features_f5Desc(),
      foot: () => m.features_f5Foot(),
    },
    {
      title: () => m.features_f6Title(),
      description: () => m.features_f6Desc(),
      foot: () => m.features_f6Foot(),
    },
  ];

  const steps = [
    {
      num: () => m.howItWorks_step1Num(),
      title: () => m.howItWorks_step1Title(),
      description: () => m.howItWorks_step1Desc(),
    },
    {
      num: () => m.howItWorks_step2Num(),
      title: () => m.howItWorks_step2Title(),
      description: () => m.howItWorks_step2Desc(),
    },
    {
      num: () => m.howItWorks_step3Num(),
      title: () => m.howItWorks_step3Title(),
      description: () => m.howItWorks_step3Desc(),
    },
  ];

  const terms = [
    { title: () => m.terms_c1Title(), body: () => m.terms_c1Body() },
    { title: () => m.terms_c2Title(), body: () => m.terms_c2Body() },
    { title: () => m.terms_c3Title(), body: () => m.terms_c3Body() },
    { title: () => m.terms_c4Title(), body: () => m.terms_c4Body() },
    { title: () => m.terms_c5Title(), body: () => m.terms_c5Body() },
    { title: () => m.terms_c6Title(), body: () => m.terms_c6Body() },
  ];
</script>

<main class="mx-auto max-w-5xl space-y-16 px-6 py-12">
  <section class="text-center">
    <p
      class="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
    >
      {m.hero_badge()}
    </p>
    <h1 class="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
      {m.hero_titlePrefix()}
      <span class="text-emerald-600">{m.hero_titleHighlight()}</span>
      {m.hero_titleSuffix()}
    </h1>
    <p class="mx-auto mt-4 max-w-2xl text-slate-600 dark:text-slate-300">
      {m.hero_description()}
    </p>
    <div class="mt-6 flex flex-wrap justify-center gap-3">
      <a
        href="#catalogo"
        class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
      >
        {m.hero_ctaCatalog()}
      </a>
      {#if $session.user}
        {#if $session.user.role === "admin"}
          <a
            href="/admin"
            class="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
          >
            {m.hero_ctaDashboard()}
          </a>
        {/if}
      {:else}
        <a
          href="/login"
          class="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
        >
          {m.hero_ctaLogin()}
        </a>
      {/if}
      <a
        href="#capacidades"
        class="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
      >
        {m.hero_ctaExplore()}
      </a>
    </div>
  </section>

  <section id="capacidades" class="space-y-6">
    <header class="text-center">
      <p class="text-xs font-semibold uppercase tracking-wide text-emerald-600">
        {m.features_badge()}
      </p>
      <h2 class="mt-1 text-2xl font-bold">{m.features_title()}</h2>
      <p
        class="mx-auto mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300"
      >
        {m.features_subtitle()}
      </p>
    </header>
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each features as feature, index (index)}
        <article
          class="rounded-xl border border-slate-200 p-4 dark:border-slate-700"
        >
          <h3 class="font-semibold">{feature.title()}</h3>
          <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {feature.description()}
          </p>
          <p class="mt-3 text-xs font-medium text-emerald-600">
            {feature.foot()}
          </p>
        </article>
      {/each}
    </div>
  </section>

  <section class="space-y-6">
    <header class="text-center">
      <p class="text-xs font-semibold uppercase tracking-wide text-emerald-600">
        {m.howItWorks_badge()}
      </p>
      <h2 class="mt-1 text-2xl font-bold">{m.howItWorks_title()}</h2>
    </header>
    <ol class="grid gap-4 sm:grid-cols-3">
      {#each steps as step, index (index)}
        <li
          class="rounded-xl border border-slate-200 p-4 dark:border-slate-700"
        >
          <span
            class="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white"
          >
            {step.num()}
          </span>
          <h3 class="mt-3 font-semibold">{step.title()}</h3>
          <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {step.description()}
          </p>
        </li>
      {/each}
    </ol>
  </section>

  <section id="catalogo" class="space-y-6">
    <header class="text-center">
      <p class="text-xs font-semibold uppercase tracking-wide text-emerald-600">
        {m.catalog_badge()}
      </p>
      <h2 class="mt-1 text-2xl font-bold">{m.catalog_title()}</h2>
      <p
        class="mx-auto mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300"
      >
        {m.catalog_subtitle()}
      </p>
    </header>

    {#if !$session.user}
      <p class="text-center text-sm text-slate-500">
        <a href="/login" class="underline">{m.catalog_loginToChat()}</a>
      </p>
    {:else if agents.length === 0}
      <p class="text-center text-sm text-slate-500">{m.catalog_noAgents()}</p>
    {:else}
      <ul class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each agents as agent (agent.id)}
          <li
            class="flex flex-col rounded-xl border border-slate-200 p-4 dark:border-slate-700"
          >
            <span class="font-medium">{agent.name}</span>
            <span
              class="mt-1 flex-1 text-sm text-slate-600 dark:text-slate-300"
            >
              {agent.profile.trim() || m.catalog_defaultDescription()}
            </span>
            <span class="mt-3 flex flex-wrap gap-2 text-xs">
              <a
                class="rounded border border-emerald-600 px-2 py-1 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-950"
                href={`/web/${agent.id}`}
              >
                {m.catalog_chatWith({ name: agent.name })}
              </a>
              <a
                class="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
                href={`/whatsapp/${agent.id}`}
              >
                {m.whatsapp_whatsappName()}
              </a>
              <a
                class="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
                href={`/telegram/${agent.id}`}
              >
                {m.whatsapp_telegram()}
              </a>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <footer
    class="border-t border-slate-200 pt-6 text-center text-xs text-slate-500 dark:border-slate-700"
  >
    <button
      type="button"
      class="underline"
      onclick={() => (termsOpen = !termsOpen)}
    >
      {m.terms_useTerms()}
    </button>
    <span class="mx-2">·</span>
    <span>{m.terms_mitLicenseBadge()}</span>
    <p class="mt-2">{m.common_appName()} · {m.common_allRightsReserved()}</p>
  </footer>

  {#if termsOpen}
    <section
      class="space-y-4 rounded-xl border border-slate-200 p-6 text-sm dark:border-slate-700"
      aria-label={m.terms_title()}
    >
      <header class="flex items-center justify-between">
        <h2 class="text-lg font-bold">{m.terms_title()}</h2>
        <button
          type="button"
          class="rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-600"
          onclick={() => (termsOpen = false)}
        >
          {m.common_close()}
        </button>
      </header>
      {#each terms as term, index (index)}
        <article>
          <h3 class="font-semibold">{term.title()}</h3>
          <p class="mt-1 text-slate-600 dark:text-slate-300">{term.body()}</p>
        </article>
      {/each}
    </section>
  {/if}
</main>
