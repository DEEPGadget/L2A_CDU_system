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

<label class="flex flex-col gap-0.5 bg-white border border-gray-200 rounded-md px-3 py-2
               hover:border-cdu-l1/40 transition-colors cursor-text
               {disabled ? 'opacity-50 pointer-events-none' : ''}">
  <span class="flex items-center gap-1.5 text-[10px] font-bold text-gray-500 tracking-widest uppercase">
    <span class="inline-block w-2 h-2 rounded-full" style:background={dotColor}></span>
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
      class="w-full text-lg font-bold text-gray-900 bg-transparent border-0 outline-none
             focus:ring-0 p-0"
    />
    {#if suffix}<span class="text-sm text-gray-500">{suffix}</span>{/if}
  </span>
</label>
