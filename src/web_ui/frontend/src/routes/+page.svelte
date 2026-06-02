<script>
  // Dashboard — live monitoring (M2). Hydrates from /api/state, then applies
  // /ws deltas. Colors mirror src/thresholds.py via $lib/thresholds.js.
  import { onMount } from 'svelte';
  import { live, startLive } from '$lib/live.svelte.js';
  import * as th from '$lib/thresholds.js';

  onMount(startLive);

  const S = $derived(live.data);

  function num(key) {
    const n = parseFloat(S[key]);
    return Number.isFinite(n) ? n : null;
  }
  function fmt(v, d = 1) { return v == null ? '--' : v.toFixed(d); }
  function delta(loop) {
    const o = num(`sensor:coolant_temp_outlet_${loop}`);
    const i = num(`sensor:coolant_temp_inlet_${loop}`);
    return (o == null || i == null) ? null : Math.round((o - i) * 10) / 10;
  }

  const comm = $derived(S['comm:status'] ?? 'unknown');
  const mode = $derived(S['control:mode'] ?? 'unknown');
  const alarms = $derived(
    Object.keys(S).filter((k) => k.startsWith('alarm:')).map((k) => k.slice(6)).sort()
  );
  function alarmLevel(name) {
    return /(_critical|_detected|_disconnected)$/.test(name) ? 'critical' : 'warning';
  }
</script>

{#snippet metric(label, valueStr, unit, status)}
  <div class="flex items-baseline justify-between py-1.5 border-b border-gray-100 last:border-0">
    <span class="text-sm text-gray-500">{label}</span>
    <span class="font-mono text-lg font-semibold {th.textClass(status)}">
      {valueStr}<span class="text-xs text-gray-400 ml-1">{unit}</span>
    </span>
  </div>
{/snippet}

{#snippet ambientCard()}
  {@const at = num('sensor:ambient_temp')}
  {@const ah = num('sensor:ambient_humidity')}
  <div class="bg-white border border-gray-200 rounded-xl p-5">
    <h2 class="text-base font-bold text-gray-800 mb-3">Ambient (internal)</h2>
    {@render metric('Temp', fmt(at), '°C', th.statusAmbientTemp(at))}
    {@render metric('Humidity', fmt(ah), '% RH', th.statusAmbientHum(ah))}
  </div>
{/snippet}

{#snippet statusCard()}
  {@const wl = S['sensor:water_level']}
  {@const leak = S['sensor:leak']}
  <div class="bg-white border border-gray-200 rounded-xl p-5">
    <h2 class="text-base font-bold text-gray-800 mb-3">Status</h2>
    {@render metric('Coolant level', th.WATER_LABEL[wl] ?? '--', '', th.statusWaterLevel(wl))}
    {@render metric('Leak', leak === 'LEAKED' ? 'DETECTED' : leak === 'NORMAL' ? 'None' : '--', '', th.statusLeak(leak))}
  </div>
{/snippet}

{#snippet loopCard(loop, accent)}
  {@const inlet = num(`sensor:coolant_temp_inlet_${loop}`)}
  {@const outlet = num(`sensor:coolant_temp_outlet_${loop}`)}
  {@const dt = delta(loop)}
  {@const flow = num(`sensor:flow_rate_${loop}`)}
  {@const pump = num(`sensor:pump_pwm_duty_${loop}`)}
  {@const fan = num(`sensor:fan_pwm_duty_${loop}`)}
  {@const rpm = num(`sensor:fan_rpm_${loop}`)}
  <div class="bg-white border border-gray-200 rounded-xl p-5">
    <div class="flex items-center gap-2 mb-3">
      <span class="w-3 h-3 rounded-full" style="background:{accent}"></span>
      <h2 class="text-base font-bold text-gray-800">Loop {loop}</h2>
    </div>
    {@render metric('Inlet', fmt(inlet), '°C', th.statusInlet(inlet))}
    {@render metric('Outlet', fmt(outlet), '°C', th.statusOutlet(outlet))}
    {@render metric('ΔT', fmt(dt), '°C', th.statusDelta(dt))}
    {@render metric('Flow', fmt(flow), 'L/min', flow == null ? 'nodata' : 'normal')}
    {@render metric('Pump duty', fmt(pump, 0), '%', pump == null ? 'nodata' : 'normal')}
    {@render metric('Fan duty', fmt(fan, 0), '%', fan == null ? 'nodata' : 'normal')}
    {@render metric('Fan RPM', fmt(rpm, 0), 'rpm', rpm == null ? 'nodata' : 'normal')}
  </div>
{/snippet}

<section class="max-w-screen-xl mx-auto p-6 space-y-4">
  <!-- status bar -->
  <div class="flex flex-wrap items-center gap-3">
    <h1 class="text-2xl font-bold mr-2">Dashboard</h1>
    <span class="px-2.5 py-1 rounded-md text-xs font-semibold uppercase tracking-wide
      {mode === 'auto' ? 'bg-blue-100 text-blue-700' : mode === 'manual' ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'}">
      {mode}
    </span>
    <span class="px-2.5 py-1 rounded-md text-xs font-semibold
      {comm === 'ok' ? 'bg-green-100 text-green-700' : 'bg-rose-100 text-rose-700'}">
      PCB: {comm}
    </span>
    <span class="ml-auto flex items-center gap-1.5 text-xs text-gray-500">
      <span class="w-2 h-2 rounded-full {live.connected ? 'bg-cdu-normal' : 'bg-gray-300'}"></span>
      {live.connected ? 'live' : 'reconnecting…'}
    </span>
  </div>

  <!-- active alarms -->
  {#if alarms.length}
    <div class="bg-rose-50 border border-rose-200 rounded-xl p-4">
      <div class="text-sm font-semibold text-rose-800 mb-2">Active alarms ({alarms.length})</div>
      <div class="flex flex-wrap gap-2">
        {#each alarms as a}
          <span class="px-2 py-1 rounded-md text-xs font-medium
            {alarmLevel(a) === 'critical' ? 'bg-cdu-critical text-white' : 'bg-cdu-warning text-white'}">
            {a}
          </span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- per-loop + side panels -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    {@render loopCard(1, '#1f77b4')}
    {@render loopCard(2, '#9467bd')}

    <!-- Ambient -->
    {@render ambientCard()}
    <!-- Status -->
    {@render statusCard()}
  </div>

  <p class="text-xs text-gray-400">
    Live values via WebSocket. History charts on the
    <a href="/history/" class="underline hover:text-gray-600">History</a> page.
  </p>
</section>
