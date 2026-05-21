<script>
  // Single tappable numeric field. Operates in the percent (UI) domain even
  // though the parent stores raw x10 values — value rises by integer percent.
  let {
    caption,
    suffix = '',
    value = $bindable(0),
    min = 0,
    max = 100,
    disabled = false,
    dotColor = '#10b981'
  } = $props();
</script>

<label class="flex flex-col gap-1 bg-white border border-gray-200 rounded-xl px-4 py-3
               hover:border-cdu-l1/40 transition-colors cursor-text
               {disabled ? 'opacity-50 pointer-events-none' : ''}">
  <span class="flex items-center gap-2 text-[11px] font-bold text-gray-500 tracking-widest uppercase">
    <span class="inline-block w-2.5 h-2.5 rounded-full" style:background={dotColor}></span>
    {caption}
  </span>
  <span class="flex items-baseline gap-1">
    <input
      type="number"
      bind:value
      {min}
      {max}
      step="1"
      {disabled}
      class="w-full text-2xl font-bold text-gray-900 bg-transparent border-0 outline-none
             focus:ring-0 p-0"
    />
    {#if suffix}<span class="text-base text-gray-500">{suffix}</span>{/if}
  </span>
</label>
