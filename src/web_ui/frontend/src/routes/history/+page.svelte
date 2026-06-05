<script>
  // History — Prometheus-style explorer: time range (+custom), metric multi-select,
  // graph-form radio (Line/Table/Timeline), incompatible-form indicator, CSV export.
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import { METRICS, METRIC_GROUPS, FORM_COMPAT, seriesName, seriesColor } from '$lib/metrics.js';
  import LineChart from '$lib/components/LineChart.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import InfoTip from '$lib/components/InfoTip.svelte';

  const INFO = 'Trends for L2A certifiable sensor metrics (coolant temp, flow, fan RPM, ' +
    'pump/fan duty, ambient). Pick a time range (or Custom), select metrics, and choose a graph ' +
    'form. Timeline is for state metrics only, so numeric metrics show an incompatible-form notice. ' +
    'Export the current view as CSV.';

  const RANGES = [
    { label: '15m', minutes: 15,   step: 15  },
    { label: '30m', minutes: 30,   step: 30  },
    { label: '1h',  minutes: 60,   step: 30  },
    { label: '24h', minutes: 1440, step: 300 }
  ];
  const FORMS = ['Line', 'Table', 'Timeline'];

  let rangeKey = $state('1h');                 // '15m'|'30m'|'1h'|'24h'|'custom'
  let customFrom = $state('');                  // datetime-local strings
  let customTo = $state('');
  let form = $state('Line');
  let selectedIds = $state(new Set(['coolant_inlet', 'coolant_outlet']));
  let allSeries = $state([]);
  let loading = $state(false);
  let error = $state('');

  const selectedMetrics = $derived(METRICS.filter((m) => selectedIds.has(m.id)));
  // metrics not displayable in the chosen form
  const incompatible = $derived(selectedMetrics.filter((m) => !FORM_COMPAT[form](m)));
  const compatible = $derived(selectedMetrics.filter((m) => FORM_COMPAT[form](m)));

  function toggle(id) {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    selectedIds = next;
  }

  function rangeOpts() {
    if (rangeKey === 'custom') {
      const start = Math.floor(new Date(customFrom).getTime() / 1000);
      const end = Math.floor(new Date(customTo).getTime() / 1000);
      const step = Math.max(1, Math.round((end - start) / 600)); // ~600 pts
      return { start, end, step, valid: Number.isFinite(start) && Number.isFinite(end) && end > start };
    }
    const r = RANGES.find((x) => x.label === rangeKey);
    return { minutes: r.minutes, step: r.step, valid: true };
  }

  async function load() {
    // only fetch metrics compatible with the current form (others get the banner)
    const metrics = compatible;
    const opts = rangeOpts();
    if (!opts.valid) { error = 'Invalid custom time range'; allSeries = []; return; }
    loading = true; error = '';
    const out = [];
    for (const m of metrics) {
      try {
        const res = await api.getHistory(m.query, opts);
        for (const r of res.result ?? []) {
          out.push({
            name: `${seriesName(m, r.metric)} (${m.unit})`,
            color: seriesColor(m, r.metric),
            dash: m.dash,
            data: r.values.map(([t, v]) => [Number(t), parseFloat(v)]).filter((p) => Number.isFinite(p[1]))
          });
        }
      } catch (e) { error = String(e); }
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
    allSeries = out;
    loading = false;
  }

  // reload on range/metric/form changes (form affects which metrics fetched)
  $effect(() => {
    rangeKey; customFrom; customTo; selectedIds; form;
    load();
  });
  onMount(() => {
    const id = setInterval(() => { if (rangeKey !== 'custom') load(); }, 30000);
    return () => clearInterval(id);
  });

  function downloadCSV() {
    if (allSeries.length === 0) return;
    const ts = [...new Set(allSeries.flatMap((s) => s.data.map((p) => p[0])))].sort((a, b) => a - b);
    const maps = allSeries.map((s) => new Map(s.data));
    const header = ['timestamp_unix', 'iso8601', ...allSeries.map((s) => `"${s.name}"`)];
    const rows = ts.map((t) => [
      t,
      new Date(t * 1000).toISOString(),
      ...maps.map((m) => (m.has(t) ? m.get(t) : ''))
    ]);
    const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `l2a_history_${ts[0] ?? 'na'}_${ts.at(-1) ?? 'na'}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div class="p-5 space-y-4">
  <!-- control bar -->
  <div class="flex items-center gap-2 flex-wrap bg-white border border-gray-200 rounded-md px-4 py-2.5">
    <h1 class="text-[15px] font-semibold text-gray-800">History</h1>
    <InfoTip text={INFO} />
    {#if loading}<span class="text-[11px] text-gray-400">loading…</span>{/if}

    <select bind:value={rangeKey} class="ml-auto border border-gray-300 rounded-md px-2.5 py-1.5 text-[13px]">
      {#each RANGES as r}<option value={r.label}>{r.label}</option>{/each}
      <option value="custom">Custom…</option>
    </select>
    {#if rangeKey === 'custom'}
      <input type="datetime-local" bind:value={customFrom} class="border border-gray-300 rounded-md px-2 py-1.5 text-[13px]" />
      <span class="text-gray-400">~</span>
      <input type="datetime-local" bind:value={customTo} class="border border-gray-300 rounded-md px-2 py-1.5 text-[13px]" />
    {/if}

    <button class="border border-gray-300 rounded-md px-3 py-1.5 text-[13px] font-medium hover:bg-gray-100 disabled:opacity-40"
      disabled={allSeries.length === 0} onclick={downloadCSV}>⬇ CSV</button>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
    <!-- sidebar: metrics + graph form -->
    <div class="lg:col-span-1 space-y-4">
      <div class="bg-white border border-gray-200 rounded-md">
        <div class="px-4 py-2.5 border-b border-gray-100 text-[13px] font-semibold text-gray-700">Graph form</div>
        <div class="p-3 flex gap-1">
          {#each FORMS as f}
            <label class="flex-1 text-center text-[13px] py-1.5 rounded-md cursor-pointer border
              {form === f ? 'bg-cdu-l1 text-white border-cdu-l1' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}">
              <input type="radio" bind:group={form} value={f} class="hidden" />{f}
            </label>
          {/each}
        </div>
      </div>

      <div class="bg-white border border-gray-200 rounded-md">
        <div class="px-4 py-2.5 border-b border-gray-100 text-[13px] font-semibold text-gray-700">Metrics</div>
        <div class="p-3">
          {#each METRIC_GROUPS as g}
            <div class="mb-2">
              <div class="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-0.5">{g}</div>
              {#each METRICS.filter((m) => m.group === g) as m}
                <label class="flex items-center gap-2 text-[13px] py-0.5 cursor-pointer">
                  <input type="checkbox" checked={selectedIds.has(m.id)} onchange={() => toggle(m.id)} />
                  <span>{m.label} <span class="text-gray-400">({m.unit})</span></span>
                </label>
              {/each}
            </div>
          {/each}
        </div>
      </div>
    </div>

    <!-- chart / table area -->
    <div class="lg:col-span-3 bg-white border border-gray-200 rounded-md p-4">
      {#if error}
        <div class="bg-amber-50 border border-amber-200 rounded-md p-3 text-[13px] text-amber-800 mb-3">{error}</div>
      {/if}
      {#if incompatible.length}
        <div class="bg-rose-50 border border-rose-200 rounded-md p-3 text-[13px] text-rose-800 mb-3">
          Incompatible graph form: <b>{incompatible.map((m) => m.label).join(', ')}</b>
          cannot be shown as <b>{form}</b>. (use Line/Table)
        </div>
      {/if}

      {#if selectedMetrics.length === 0}
        <div class="text-center text-gray-400 text-[13px] py-12">Select a metric on the left.</div>
      {:else if compatible.length === 0}
        <div class="text-center text-gray-400 text-[13px] py-12">The selected metrics are not compatible with the {form} form.</div>
      {:else if form === 'Table'}
        <DataTable series={allSeries} />
      {:else if form === 'Line'}
        <LineChart series={allSeries} yLabel="" height={420} />
      {:else}
        <!-- Timeline: state-only; no state metrics currently → handled by banner above -->
        <div class="text-center text-gray-400 text-[13px] py-12">Timeline is for state metrics only.</div>
      {/if}
    </div>
  </div>
</div>
