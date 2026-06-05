<script>
  // Full-width top header (enterprise admin shell). Product identity on the
  // left, live system status on the right.
  import { live } from '$lib/live.svelte.js';

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
    <span class="px-2.5 py-1 rounded text-[11px] font-semibold uppercase tracking-wide
      {mode === 'auto' ? 'bg-blue-100 text-blue-700'
        : mode === 'manual' ? 'bg-amber-100 text-amber-700'
        : 'bg-rose-100 text-rose-700'}">
      {mode}
    </span>
    <span class="px-2.5 py-1 rounded text-[11px] font-semibold
      {comm === 'ok' ? 'bg-green-100 text-green-700' : 'bg-rose-100 text-rose-700'}">
      PCB: {comm}
    </span>
    <span class="flex items-center gap-1.5 text-[11px] text-gray-500">
      <span class="w-2 h-2 rounded-full {live.connected ? 'bg-cdu-normal' : 'bg-gray-300'}"></span>
      {live.connected ? 'live' : 'reconnecting…'}
    </span>
  </div>
</header>
