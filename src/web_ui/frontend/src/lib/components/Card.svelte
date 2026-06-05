<script>
  // Standard panel: a titled header with a bottom rule (NETGEAR-style), then a
  // body. Optional ⓘ help and a right-aligned header slot.
  import InfoTip from './InfoTip.svelte';

  let {
    title = '',
    info = '',
    bodyClass = 'px-4 py-3',
    class: cls = '',
    children,
    actions
  } = $props();
</script>

<div class="bg-white border border-gray-200 rounded-md {cls}">
  {#if title}
    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100">
      <h2 class="text-[14px] font-semibold text-gray-700">{title}</h2>
      {#if info}<InfoTip text={info} />{/if}
      {#if actions}<div class="ml-auto flex items-center gap-2">{@render actions()}</div>{/if}
    </div>
  {/if}
  <div class={bodyClass}>
    {@render children?.()}
  </div>
</div>
