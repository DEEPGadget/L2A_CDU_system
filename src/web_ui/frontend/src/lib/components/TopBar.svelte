<script>
  import { page } from '$app/state';

  const tabs = [
    { href: '/',          label: 'Dashboard' },
    { href: '/history/',  label: 'History'   },
    { href: '/settings/', label: 'Settings'  }
  ];

  function isActive(href) {
    if (href === '/') return page.url.pathname === '/';
    return page.url.pathname.startsWith(href);
  }
</script>

<header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
  <div class="text-lg font-bold tracking-wide text-cdu-l1">L2A CDU</div>

  <nav class="flex gap-1">
    {#each tabs as tab}
      <a
        href={tab.href}
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {isActive(tab.href)
          ? 'bg-cdu-l1 text-white'
          : 'text-gray-700 hover:bg-gray-100'}"
      >
        {tab.label}
      </a>
    {/each}
  </nav>
</header>
