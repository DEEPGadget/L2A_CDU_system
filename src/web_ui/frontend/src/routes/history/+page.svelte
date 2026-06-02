<script>
  // History (M3) — Prometheus time-series via /api/history proxy.
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import LineChart from '$lib/components/LineChart.svelte';

  const RANGES = [
    { label: '15m', minutes: 15,   step: 15 },
    { label: '1h',  minutes: 60,   step: 30 },
    { label: '6h',  minutes: 360,  step: 120 },
    { label: '24h', minutes: 1440, step: 300 }
  ];
  let rangeIdx = $state(1);
  const range = $derived(RANGES[rangeIdx]);

  // Per-loop color convention (docs/UI_Design.md): L1 blue, L2 purple.
  const LOOP_COLOR = { '1': '#1f77b4', '2': '#9467bd' };

  const GROUPS = [
    {
      title: 'Coolant Temperature', unit: '°C',
      metrics: [
        { name: 'sensor_coolant_temp_inlet',  label: 'Inlet' },
        { name: 'sensor_coolant_temp_outlet', label: 'Outlet', dash: true }
      ]
    },
    {
      title: 'Flow Rate', unit: 'L/min',
      metrics: [{ name: 'sensor_flow_rate', label: 'Flow' }]
    },
    {
      title: 'PWM Duty', unit: '%',
      metrics: [
        { name: 'sensor_pump_pwm_duty', label: 'Pump' },
        { name: 'sensor_fan_pwm_duty',  label: 'Fan', dash: true }
      ]
    },
    {
      title: 'Ambient', unit: '°C / % RH',
      metrics: [
        { name: 'sensor_ambient_temp',     label: 'Temp',     color: '#e377c2' },
        { name: 'sensor_ambient_humidity', label: 'Humidity', color: '#17becf' }
      ]
    }
  ];

  let seriesByGroup = $state({});
  let loading = $state(false);
  let error = $state('');

  async function loadGroup(g) {
    const out = [];
    for (const m of g.metrics) {
      let res;
      try {
        res = await api.getHistory(m.name, range.minutes, range.step);
      } catch (e) {
        error = String(e);
        continue;
      }
      for (const r of res.result ?? []) {
        const loop = r.metric.loop;
        out.push({
          name: loop ? `${m.label} L${loop}` : m.label,
          color: m.color ?? LOOP_COLOR[loop] ?? '#1f77b4',
          dash: !!m.dash,
          data: r.values
            .map(([t, v]) => [Number(t), parseFloat(v)])
            .filter((p) => Number.isFinite(p[1]))
        });
      }
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
    return out;
  }

  async function loadAll() {
    loading = true;
    error = '';
    try {
      const entries = await Promise.all(GROUPS.map(async (g) => [g.title, await loadGroup(g)]));
      seriesByGroup = Object.fromEntries(entries);
    } finally {
      loading = false;
    }
  }

  // initial load + reload whenever the range changes
  $effect(() => {
    range;
    loadAll();
  });

  // periodic refresh
  onMount(() => {
    const id = setInterval(loadAll, 30000);
    return () => clearInterval(id);
  });
</script>

<section class="max-w-screen-xl mx-auto p-6 space-y-4">
  <div class="flex items-center gap-3">
    <h1 class="text-2xl font-bold">History</h1>
    {#if loading}<span class="text-xs text-gray-400">loading…</span>{/if}
    <div class="ml-auto inline-flex rounded-lg border border-gray-200 overflow-hidden">
      {#each RANGES as r, i}
        <button
          class="px-3 py-1.5 text-sm font-medium transition-colors
            {rangeIdx === i ? 'bg-cdu-l1 text-white' : 'bg-white text-gray-600 hover:bg-gray-100'}"
          onclick={() => (rangeIdx = i)}
        >{r.label}</button>
      {/each}
    </div>
  </div>

  {#if error}
    <div class="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
      Some series failed to load (Prometheus may be warming up): {error}
    </div>
  {/if}

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    {#each GROUPS as g}
      <div class="bg-white border border-gray-200 rounded-xl p-5">
        <h2 class="text-base font-bold text-gray-800 mb-2">{g.title}<span class="text-xs font-normal text-gray-400 ml-2">{g.unit}</span></h2>
        <LineChart series={seriesByGroup[g.title] ?? []} yLabel={g.unit} />
      </div>
    {/each}
  </div>
</section>
