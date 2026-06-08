<script>
  // Full-width top header (enterprise admin shell). Product identity on the
  // left, live system status on the right.
  import { onMount } from 'svelte';
  import { live, startLive } from '$lib/live.svelte.js';

  // Start hydration as early as the shell mounts so the badges fill in fast
  // (avoids a lingering pre-hydration placeholder on hard refresh).
  onMount(startLive);

  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const S = $derived(live.data);
  const mode = $derived(S['control:mode'] ?? 'unknown');
  const comm = $derived(S['comm:status'] ?? 'unknown');
</script>

<header class="h-14 shrink-0 bg-white border-b border-gray-200 flex items-center px-5 gap-3">
  <div class="flex items-baseline gap-2">
    <span class="text-lg font-bold text-cdu-l1 tracking-wide">L2A CDU</span>
    <span class="text-xs text-gray-400 hidden md:inline">In-Rack Cooling Distribution Unit</span>
  </div>

  <div class="ml-auto flex items-center gap-2.5">
    <span class="px-2.5 py-1 rounded text-[11px] font-semibold
      {mode === 'auto' ? 'bg-green-100 text-green-700'
        : mode === 'manual' ? 'bg-blue-100 text-blue-700'
        : mode === 'unknown' ? 'bg-gray-100 text-gray-400'
        : 'bg-red-100 text-red-700'}">
      {mode === 'unknown' ? '—' : cap(mode)}
    </span>
    <span class="px-2.5 py-1 rounded text-[11px] font-semibold
      {comm === 'ok' ? 'bg-green-100 text-green-700'
        : comm === 'unknown' ? 'bg-gray-100 text-gray-400'
        : 'bg-rose-100 text-rose-700'}">
      PCB: {comm === 'unknown' ? '—' : cap(comm)}
    </span>
    <span class="flex items-center gap-1.5 text-[11px] text-gray-500">
      <span class="w-2 h-2 rounded-full {live.connected ? 'bg-cdu-normal' : 'bg-gray-300'}"></span>
      {live.connected ? 'live' : 'reconnecting…'}
    </span>
  </div>
</header>
