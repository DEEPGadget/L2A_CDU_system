<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import { live, startLive } from '$lib/live.svelte.js';
  import ModeToggle    from '$lib/components/ModeToggle.svelte';
  import FanCurveCard  from '$lib/components/FanCurveCard.svelte';
  import PumpFixedCard from '$lib/components/PumpFixedCard.svelte';

  let mode      = $state('auto');
  let fanCurve  = $state({ min_temp: 25, max_temp: 60, min_duty: 100, max_duty: 1000 });
  let pumpDuty  = $state(600);
  let loaded    = $state(false);
  let loadError = $state('');

  async function refresh() {
    try {
      const s = await api.getControl();
      mode     = s.mode;
      fanCurve = s.fan_curve;   // new object ref → cards reset to the synced value
      pumpDuty = s.pump_duty;
      loadError = '';
    } catch (e) {
      loadError = String(e);
    } finally {
      loaded = true;
    }
  }

  onMount(startLive);

  // Initial load + re-sync whenever any control:* change is published —
  // including changes made from the Local (touch) UI. Last-write-wins per
  // ARCHITECTURE.md "Race condition 정책".
  $effect(() => {
    live.controlRev;   // dependency: re-run on every control update
    refresh();
  });

  // Auto-only controls are read-only in Manual / Emergency modes.
  const autoDisabled = $derived(mode !== 'auto');
</script>

<section class="max-w-screen-xl mx-auto p-6 space-y-4">
  {#if !loaded}
    <div class="text-gray-500">Loading…</div>
  {:else if loadError}
    <div class="bg-rose-50 border border-rose-200 text-cdu-critical rounded-xl p-4">
      Failed to load control state: {loadError}
    </div>
  {:else}
    <ModeToggle bind:mode />

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2">
        <FanCurveCard
          {fanCurve}
          disabled={autoDisabled}
          onsaved={(updated) => fanCurve = updated}
        />
      </div>
      <div>
        <PumpFixedCard
          {pumpDuty}
          disabled={autoDisabled}
          onsaved={(updated) => pumpDuty = updated}
        />
      </div>
    </div>

    {#if mode === 'manual'}
      <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        Manual mode: pump and fan duties are set directly from the Dashboard
        (coming in M2). Auto controls above are read-only.
      </div>
    {/if}

    {#if mode === 'emergency'}
      <div class="bg-rose-50 border border-rose-200 rounded-xl p-4 text-sm text-rose-800">
        Emergency mode active. Mode toggle and Auto controls are disabled.
      </div>
    {/if}
  {/if}
</section>
