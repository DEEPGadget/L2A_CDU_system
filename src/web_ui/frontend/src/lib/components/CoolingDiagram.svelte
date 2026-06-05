<script>
  // Live cooling diagram — same SVG as the Local UI (fetched from /api/diagram),
  // {TOKEN} placeholders substituted from the live store. Display only; the SVG
  // is forced responsive (width:100%) so it scales to the card.
  import { onMount } from 'svelte';
  import { live, startLive } from '$lib/live.svelte.js';
  import { buildTokens } from '$lib/diagramTokens.js';
  import { api } from '$lib/api.js';

  let svgTemplate = $state('');
  onMount(async () => {
    startLive();
    try { svgTemplate = await api.getDiagram(); } catch { /* keep empty */ }
  });

  const mode = $derived(live.data['control:mode'] ?? 'manual');

  const rendered = $derived.by(() => {
    if (!svgTemplate) return '';
    const tokens = buildTokens(live.data, mode);
    let s = svgTemplate;
    for (const [k, v] of Object.entries(tokens)) s = s.replaceAll(`{${k}}`, v);
    return s.replace(/\{[A-Z0-9_]+\}/g, ''); // strip any leftover token
  });
</script>

<div class="diagram w-full overflow-hidden">
  {#if rendered}
    {@html rendered}
  {:else}
    <div class="p-8 text-center text-gray-400">Loading diagram…</div>
  {/if}
</div>

<style>
  /* Force the injected SVG (fixed 1280×608 attrs) to scale to the card width. */
  .diagram :global(svg) {
    width: 100%;
    height: auto;
    display: block;
  }
</style>
