<script>
  // History — Prometheus-style explorer: time range (+custom), metric multi-select,
  // graph-form radio (Line/Table/Timeline), incompatible-form indicator, CSV export.
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import { METRICS, METRIC_GROUPS, FORM_COMPAT, seriesName } from '$lib/metrics.js';
  import LineChart from '$lib/components/LineChart.svelte';
  import DataTable from '$lib/components/DataTable.svelte';
  import InfoTip from '$lib/components/InfoTip.svelte';
  import DateTimeSelect from '$lib/components/DateTimeSelect.svelte';

  // Distinct colour per selected series (no dashes).
  const PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
                   '#e377c2', '#17becf', '#bcbd22', '#393b79', '#637939', '#8c6d31'];

  const INFO = 'Trends for L2A certifiable sensor metrics (coolant temp, flow, fan RPM, ' +
    'pump/fan duty, ambient). Pick a time range (or Custom), select metrics, and choose a graph ' +
    'form. Timeline is for state metrics only, so numeric metrics show an incompatible-form notice. ' +
    'Export the current view as CSV.';

  // 1-minute resolution everywhere (step = 60 s).
  const RANGES = [
    { label: '15m', minutes: 15,   step: 60 },
    { label: '30m', minutes: 30,   step: 60 },
    { label: '1h',  minutes: 60,   step: 60 },
    { label: '24h', minutes: 1440, step: 60 }
  ];
  const FORMS = ['Line', 'Table', 'Timeline'];

  // unix seconds → "YYYY-MM-DD HH:MM" (local time, minute resolution)
  function fmtTime(s) {
    const d = new Date(s * 1000);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  let rangeKey = $state('30m');                // '15m'|'30m'|'1h'|'24h'|'custom'
  let customFrom = $state('');                  // datetime-local strings
  let customTo = $state('');
  let form = $state('Line');
  let selectedIds = $state(new Set(['coolant_inlet', 'coolant_outlet', 'flow_1', 'flow_2']));
  let allSeries = $state([]);
  let loading = $state(false);
  let error = $state('');
  let shownRange = $state('');                  // "YYYY-MM-DD HH:MM ~ ..." of the fetched window
  let tStart = $state(0);                        // selected window (unix sec) → chart x-domain
  let tEnd = $state(0);

  const selectedMetrics = $derived(METRICS.filter((m) => selectedIds.has(m.id)));
  // metrics not displayable in the chosen form
  const incompatible = $derived(selectedMetrics.filter((m) => !FORM_COMPAT[form](m)));
  const compatible = $derived(selectedMetrics.filter((m) => FORM_COMPAT[form](m)));

  // One chart per (group, unit) among the SELECTED metrics — group first, split
  // by unit when a group mixes units (e.g. Ambient = °C + % RH). Driven by the
  // selection (not the returned data) so a panel shows immediately on load and
  // renders "No data" rather than vanishing when a series is momentarily empty.
  const chartGroups = $derived.by(() => {
    const out = [];
    for (const g of METRIC_GROUPS) {
      const units = [...new Set(compatible.filter((m) => m.group === g).map((m) => m.unit))];
      for (const u of units) {
        out.push({ title: `${g} (${u})`, unit: u, series: allSeries.filter((s) => s.group === g && s.unit === u) });
      }
    }
    return out;
  });

  function toggle(id) {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    selectedIds = next;
  }

  function rangeOpts() {
    if (rangeKey === 'custom') {
      // Accept "YYYY-MM-DD HH:MM" (space or T) as local time.
      const parse = (s) => Math.floor(new Date(String(s).trim().replace(' ', 'T')).getTime() / 1000);
      const start = parse(customFrom);
      const end = parse(customTo);
      const step = Math.max(60, Math.ceil((end - start) / 10000)); // 1-min, capped for long spans
      return { start, end, step, valid: Number.isFinite(start) && Number.isFinite(end) && end > start };
    }
    const r = RANGES.find((x) => x.label === rangeKey);
    return { minutes: r.minutes, step: r.step, valid: true };
  }

  async function load() {
    // only fetch metrics compatible with the current form (others get the banner)
    const metrics = compatible;
    const o = rangeOpts();
    if (!o.valid) { error = 'Invalid custom time range'; allSeries = []; shownRange = ''; return; }
    // Resolve ONE absolute [start,end] for the whole load so every metric query
    // shares the same Prometheus grid → timestamps line up across series (one
    // CSV/table row per minute, not one per metric).
    let startSec, endSec;
    if (rangeKey === 'custom') {
      startSec = o.start; endSec = o.end;
    } else {
      endSec = Math.floor(Date.now() / 1000);
      endSec -= endSec % o.step;                       // snap to the step grid
      startSec = endSec - RANGES.find((r) => r.label === rangeKey).minutes * 60;
    }
    const opts = { start: startSec, end: endSec, step: o.step };
    tStart = startSec; tEnd = endSec;
    shownRange = `${fmtTime(startSec)} ~ ${fmtTime(endSec)}`;
    loading = true; error = '';
    const out = [];
    for (const m of metrics) {
      try {
        const res = await api.getHistory(m.query, opts);
        for (const r of res.result ?? []) {
          out.push({
            name: `${seriesName(m, r.metric)} (${m.unit})`,
            group: m.group,
            unit: m.unit,
            data: r.values.map(([t, v]) => [Number(t), parseFloat(v)]).filter((p) => Number.isFinite(p[1]))
          });
        }
      } catch (e) { error = String(e); }
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
    out.forEach((s, i) => { s.color = PALETTE[i % PALETTE.length]; s.dash = false; });
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
    // One row per timestamp (wide): time column + one column per series.
    const ts = [...new Set(allSeries.flatMap((s) => s.data.map((p) => p[0])))].sort((a, b) => a - b);
    const maps = allSeries.map((s) => new Map(s.data));
    const header = ['time', ...allSeries.map((s) => `"${s.name}"`)];
    const rows = ts.map((t) => [fmtTime(t), ...maps.map((m) => (m.has(t) ? m.get(t) : ''))]);
    const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    const stamp = (t) => fmtTime(t).replace(/[: ]/g, '-');
    a.download = `l2a_history_${ts[0] ? stamp(ts[0]) : 'na'}_${ts.at(-1) ? stamp(ts.at(-1)) : 'na'}.csv`;
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
      <DateTimeSelect bind:value={customFrom} />
      <span class="text-gray-400">~</span>
      <DateTimeSelect bind:value={customTo} />
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

    <!-- chart / table area (no outer box; charts span full width, stacked) -->
    <div class="lg:col-span-3 space-y-3">
      {#if shownRange}
        <div class="text-[12px] text-gray-500 font-mono">{shownRange}</div>
      {/if}
      {#if error}
        <div class="bg-amber-50 border border-amber-200 rounded-md p-3 text-[13px] text-amber-800">{error}</div>
      {/if}
      {#if incompatible.length}
        <div class="bg-rose-50 border border-rose-200 rounded-md p-3 text-[13px] text-rose-800">
          Incompatible graph form: <b>{incompatible.map((m) => m.label).join(', ')}</b>
          cannot be shown as <b>{form}</b>. (use Line/Table)
        </div>
      {/if}

      {#if selectedMetrics.length === 0}
        <div class="bg-white border border-gray-200 rounded-md text-center text-gray-400 text-[13px] py-12">Select a metric on the left.</div>
      {:else if compatible.length === 0}
        <div class="bg-white border border-gray-200 rounded-md text-center text-gray-400 text-[13px] py-12">The selected metrics are not compatible with the {form} form.</div>
      {:else if form === 'Table'}
        <div class="bg-white border border-gray-200 rounded-md p-3">
          <DataTable series={allSeries} />
        </div>
      {:else if form === 'Line'}
        {#each chartGroups as cg}
          <div class="bg-white border border-gray-200 rounded-md p-3">
            <div class="text-[12px] font-semibold text-gray-600 mb-1">{cg.title}</div>
            <LineChart series={cg.series} height={170} {tStart} {tEnd} />
          </div>
        {/each}
      {:else}
        <!-- Timeline: state-only; no state metrics currently → handled by banner above -->
        <div class="bg-white border border-gray-200 rounded-md text-center text-gray-400 text-[13px] py-12">Timeline is for state metrics only.</div>
      {/if}
    </div>
  </div>
</div>
