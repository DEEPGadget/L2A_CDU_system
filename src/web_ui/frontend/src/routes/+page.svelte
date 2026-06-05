<script>
  // Dashboard — merged live monitoring + control, enterprise card grid.
  // Hydrates from /api/state, applies /ws deltas. Cooling diagram is display-
  // only; all actuator control lives in the Control cards.
  import { onMount } from 'svelte';
  import { live, startLive } from '$lib/live.svelte.js';
  import { api } from '$lib/api.js';
  import * as th from '$lib/thresholds.js';
  import Card from '$lib/components/Card.svelte';
  import CoolingDiagram from '$lib/components/CoolingDiagram.svelte';
  import ModeToggle from '$lib/components/ModeToggle.svelte';
  import FanCurveCard from '$lib/components/FanCurveCard.svelte';
  import PumpFixedCard from '$lib/components/PumpFixedCard.svelte';
  import ManualDutyCard from '$lib/components/ManualDutyCard.svelte';

  onMount(startLive);

  const S = $derived(live.data);

  // ── live read helpers ──
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
  const alarms = $derived(
    Object.keys(S).filter((k) => k.startsWith('alarm:')).map((k) => k.slice(6)).sort()
  );
  function alarmLevel(name) {
    return /(_critical|_detected|_disconnected)$/.test(name) ? 'critical' : 'warning';
  }

  // ── control state (from /api/control, re-synced on every control:* change) ──
  let mode      = $state('auto');
  let fanCurve  = $state({ min_temp: 25, max_temp: 60, min_duty: 100, max_duty: 1000 });
  let pumpDuty  = $state(600);
  let loaded    = $state(false);
  let loadError = $state('');

  function di(key, dflt) {
    const n = parseInt(live.data[key] ?? '', 10);
    return Number.isFinite(n) ? n : dflt;
  }
  const duty = $derived({
    pump_1: di('sensor:pump_pwm_duty_1', 78), pump_2: di('sensor:pump_pwm_duty_2', 78),
    fan_1:  di('sensor:fan_pwm_duty_1', 100), fan_2:  di('sensor:fan_pwm_duty_2', 100)
  });

  async function refresh() {
    try {
      const s = await api.getControl();
      mode = s.mode; fanCurve = s.fan_curve; pumpDuty = s.pump_duty;
      loadError = '';
    } catch (e) { loadError = String(e); }
    finally { loaded = true; }
  }
  $effect(() => { live.controlRev; refresh(); });

  const autoDisabled = $derived(mode !== 'auto');
  const manualDisabled = $derived(mode !== 'manual');

  const INFO = {
    diagram: 'Live cooling structure. Boxes show measured temperature, flow and fan RPM; ' +
             'colour follows the alarm thresholds. Display only — use the Control cards to drive actuators.',
    mode: 'Auto: fan follows the temperature curve and the pump holds a fixed duty. ' +
          'Manual: set pump/fan PWM directly. Emergency: actuators forced, controls locked.',
    auto: 'Active in Auto mode only. Fan duty interpolates between min/max temperature; the pump runs at the fixed duty.',
    manual: 'Active in Manual mode only. Set pump/fan PWM per loop. Pump 0 % = stop (1–100 → 17–85 %), fan ≥ 10 %.'
  };
</script>

{#snippet kv(label, value, unit, status)}
  <div class="flex items-center justify-between py-[5px]">
    <span class="text-[13px] text-gray-500">{label}</span>
    <span class="text-[13px] font-semibold {th.textClass(status)}">
      {value}{#if unit}<span class="text-[11px] text-gray-400 ml-1">{unit}</span>{/if}
    </span>
  </div>
{/snippet}

<div class="p-5 space-y-4">

  {#if alarms.length}
    <div class="bg-rose-50 border border-rose-200 rounded-md p-3">
      <div class="text-[13px] font-semibold text-rose-800 mb-2">Active alarms ({alarms.length})</div>
      <div class="flex flex-wrap gap-2">
        {#each alarms as a}
          <span class="px-2 py-0.5 rounded text-[11px] font-medium
            {alarmLevel(a) === 'critical' ? 'bg-cdu-critical text-white' : 'bg-cdu-warning text-white'}">
            {a}
          </span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Row 1: diagram (wide) + system summary -->
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
    <Card title="Cooling Structure" info={INFO.diagram} class="xl:col-span-2" bodyClass="p-3">
      <CoolingDiagram />
    </Card>

    <Card title="System">
      {@render kv('Control mode', mode === 'auto' ? 'Auto' : mode === 'manual' ? 'Manual' : 'Emergency',
                  '', mode === 'emergency' ? 'critical' : 'normal')}
      {@render kv('PCB link', comm, '', comm === 'ok' ? 'normal' : 'critical')}
      {@render kv('Data link', live.connected ? 'Connected' : 'Reconnecting', '', live.connected ? 'normal' : 'warning')}
      {@render kv('Active alarms', String(alarms.length), '', alarms.length ? 'warning' : 'normal')}
    </Card>
  </div>

  <!-- Row 2: per-loop + ambient + status -->
  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
    {#each [1, 2] as loop}
      {@const accent = loop === 1 ? '#1f77b4' : '#9467bd'}
      <div class="bg-white border border-gray-200 rounded-md">
        <div class="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100">
          <span class="w-2.5 h-2.5 rounded-full" style="background:{accent}"></span>
          <h2 class="text-[14px] font-semibold text-gray-700">Loop {loop}</h2>
        </div>
        <div class="px-4 py-3">
        {@render kv('Inlet', fmt(num(`sensor:coolant_temp_inlet_${loop}`)), '°C', th.statusInlet(num(`sensor:coolant_temp_inlet_${loop}`)))}
        {@render kv('Outlet', fmt(num(`sensor:coolant_temp_outlet_${loop}`)), '°C', th.statusOutlet(num(`sensor:coolant_temp_outlet_${loop}`)))}
        {@render kv('ΔT', fmt(delta(loop)), '°C', th.statusDelta(delta(loop)))}
        <div class="flex items-start justify-between py-[5px]">
          <span class="text-[13px] text-gray-500">Flow</span>
          <span class="text-right">
            <span class="text-[13px] font-semibold {num(`sensor:flow_rate_${loop}`) == null ? 'text-gray-400' : 'text-gray-800'}">
              {fmt(num(`sensor:flow_rate_${loop}`))}<span class="text-[11px] text-gray-400 ml-1">L/min</span>
            </span>
            <span class="block text-[10px] text-gray-400 leading-tight">1 : {fmt(num(`sensor:flow_rate_${loop}_1`))}</span>
            <span class="block text-[10px] text-gray-400 leading-tight">2 : {fmt(num(`sensor:flow_rate_${loop}_2`))}</span>
          </span>
        </div>
        {@render kv('Pump duty', fmt(num(`sensor:pump_pwm_duty_${loop}`), 0), '%', num(`sensor:pump_pwm_duty_${loop}`) == null ? 'nodata' : 'normal')}
        {@render kv('Fan duty', fmt(num(`sensor:fan_pwm_duty_${loop}`), 0), '%', num(`sensor:fan_pwm_duty_${loop}`) == null ? 'nodata' : 'normal')}
        {@render kv('Fan RPM', fmt(num(`sensor:fan_rpm_${loop}`), 0), 'rpm', num(`sensor:fan_rpm_${loop}`) == null ? 'nodata' : 'normal')}
        </div>
      </div>
    {/each}

    <Card title="Ambient (internal)">
      {@render kv('Temp', fmt(num('sensor:ambient_temp')), '°C', th.statusAmbientTemp(num('sensor:ambient_temp')))}
      {@render kv('Humidity', fmt(num('sensor:ambient_humidity')), '% RH', th.statusAmbientHum(num('sensor:ambient_humidity')))}
    </Card>

    <Card title="Status">
      {@render kv('Coolant level', th.WATER_LABEL[S['sensor:water_level']] ?? '--', '', th.statusWaterLevel(S['sensor:water_level']))}
      {@render kv('Leak', S['sensor:leak'] === 'LEAKED' ? 'DETECTED' : S['sensor:leak'] === 'NORMAL' ? 'None' : '--', '', th.statusLeak(S['sensor:leak']))}
    </Card>
  </div>

  <!-- Row 3: control -->
  <div class="flex items-center gap-2 pt-1">
    <h2 class="text-[15px] font-semibold text-gray-800">Control</h2>
  </div>

  {#if !loaded}
    <div class="text-gray-500 text-[13px]">Loading…</div>
  {:else if loadError}
    <div class="bg-rose-50 border border-rose-200 text-cdu-critical rounded-md p-3 text-[13px]">
      Failed to load control state: {loadError}
    </div>
  {:else}
    <div class="space-y-4">
      <ModeToggle bind:mode />
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="lg:col-span-2">
          <FanCurveCard {fanCurve} disabled={autoDisabled} onsaved={(u) => fanCurve = u} info={INFO.auto} />
        </div>
        <div>
          <PumpFixedCard {pumpDuty} disabled={autoDisabled} onsaved={(u) => pumpDuty = u} />
        </div>
      </div>
      <ManualDutyCard {duty} disabled={manualDisabled} info={INFO.manual} />
      {#if mode === 'emergency'}
        <div class="bg-rose-50 border border-rose-200 rounded-md p-3 text-[13px] text-rose-800">
          Emergency mode active. Mode toggle and Auto controls are disabled.
        </div>
      {/if}
    </div>
  {/if}

  <p class="text-[11px] text-gray-400">
    Live values via WebSocket. Trend charts and CSV export on the
    <a href="/history/" class="underline hover:text-gray-600">History</a> page.
  </p>
</div>
