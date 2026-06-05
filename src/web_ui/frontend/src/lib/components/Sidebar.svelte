<script>
  // Left navigation rail. Compact rows; the active item is filled solid blue.
  import { page } from '$app/state';

  const nav = [
    { href: '/', label: 'Dashboard',
      path: 'M3 3h7v7H3V3zm0 11h7v7H3v-7zm11-11h7v7h-7V3zm0 11h7v7h-7v-7z' },
    { href: '/history/', label: 'History',
      path: 'M12 8v4l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z' }
  ];

  function isActive(href) {
    if (href === '/') return page.url.pathname === '/';
    return page.url.pathname.startsWith(href);
  }
</script>

<aside class="w-52 shrink-0 bg-white border-r border-gray-200">
  <nav class="p-2.5 space-y-1">
    {#each nav as item}
      <a
        href={item.href}
        class="flex items-center gap-3 px-3 py-2 rounded text-[13px] font-medium transition-colors
          {isActive(item.href)
            ? 'bg-cdu-l1 text-white'
            : 'text-gray-600 hover:bg-gray-100'}"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d={item.path} />
        </svg>
        {item.label}
      </a>
    {/each}
  </nav>
</aside>
