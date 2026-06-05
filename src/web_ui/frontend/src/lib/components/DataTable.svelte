<script>
  // Tabular view of time-series. Rows = timestamps (newest first), columns = series.
  // series: [{ name, data:[[tSeconds, value], ...] }]
  let { series = [], maxRows = 500 } = $props();

  // union of timestamps across all series, descending
  const timestamps = $derived(
    [...new Set(series.flatMap((s) => s.data.map((p) => p[0])))]
      .sort((a, b) => b - a)
      .slice(0, maxRows)
  );
  const maps = $derived(series.map((s) => new Map(s.data)));

  function ts(t) {
    const d = new Date(t * 1000);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  const fmt = (v) => (v == null ? '' : Number(v).toFixed(2));
</script>

{#if series.length === 0 || timestamps.length === 0}
  <div class="text-center text-gray-400 py-8">No data in range</div>
{:else}
  <div class="overflow-auto max-h-[60vh] border border-gray-200 rounded-lg">
    <table class="w-full text-sm font-mono">
      <thead class="bg-gray-50 sticky top-0">
        <tr>
          <th class="px-3 py-2 text-left font-semibold text-gray-600">Timestamp</th>
          {#each series as s}
            <th class="px-3 py-2 text-right font-semibold" style="color:{s.color ?? '#374151'}">{s.name}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each timestamps as t}
          <tr class="border-t border-gray-100">
            <td class="px-3 py-1 text-gray-500 whitespace-nowrap">{ts(t)}</td>
            {#each maps as m}
              <td class="px-3 py-1 text-right text-gray-800">{fmt(m.get(t))}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
