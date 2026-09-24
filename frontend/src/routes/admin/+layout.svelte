<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { m } from "$lib/paraglide/messages.js";
  import { session } from "$lib/session";

  let { children } = $props();

  const links = [
    { href: "/admin", label: () => m.common_dashboard() },
    { href: "/admin/agents", label: () => m.admin_allAgents() },
    { href: "/admin/roles", label: () => m.admin_viewRoles() },
    { href: "/admin/sources", label: () => m.admin_viewKnowledgeBases() },
    { href: "/admin/users", label: () => m.admin_colUser() },
    { href: "/admin/transcripts", label: () => m.admin_historyMaintainer() },
    { href: "/admin/account", label: () => m.admin_myAccountProfile() },
  ];

  const current = $derived(page.url.pathname);

  // Guarda de administración (D17/D18): un usuario normal vuelve al inicio.
  $effect(() => {
    if (
      $session.ready &&
      $session.user !== null &&
      $session.user.role !== "admin"
    ) {
      void goto("/");
    }
  });
</script>

<div class="mx-auto flex max-w-6xl flex-col gap-6 p-6 md:flex-row">
  <nav
    class="flex shrink-0 gap-1 overflow-x-auto md:w-56 md:flex-col"
    aria-label={m.common_dashboard()}
  >
    {#each links as link (link.href)}
      {@const exact = link.href === "/admin"}
      {@const active = exact
        ? current === link.href
        : current.startsWith(link.href)}
      <a
        href={link.href}
        class="rounded-lg px-3 py-2 text-sm whitespace-nowrap hover:bg-slate-100 dark:hover:bg-slate-800 {active
          ? 'bg-slate-100 font-semibold dark:bg-slate-800'
          : ''}"
      >
        {link.label()}
      </a>
    {/each}
  </nav>
  <main class="min-w-0 flex-1">
    {@render children()}
  </main>
</div>
