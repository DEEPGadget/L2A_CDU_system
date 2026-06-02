<script>
  // Dependency-free SVG line chart (offline/kiosk-safe — no chart library).
  // Props:
  //   series : [{ name, color, dash?:bool, data:[[tSeconds, value], ...] }]
  //   yLabel : axis unit string
  //   height : px (viewBox height)
  let { series = [], yLabel = '', height = 280 } = $props();

  const W = 820;
  const M = { t: 12, r: 16, b: 28, l: 48 };

  const flat = $derived(series.flatMap((s) => s.data));
  const hasData = $derived(flat.length > 0);

  const tMin = $derived(hasData ? Math.min(...flat.map((p) => p[0])) : 0);
  const tMax = $derived(hasData ? Math.max(...flat.map((p) => p[0])) : 1);
  let yLo = $derived(hasData ? Math.min(...flat.map((p) => p[1])) : 0);
  let yHi = $derived(hasData ? Math.max(...flat.map((p) => p[1])) : 1);

  // pad y-range by 8% (and avoid zero-height when flat)
  const pad = $derived(((yHi - yLo) || Math.abs(yHi) || 1) * 0.08);
  const yMin = $derived(yLo - pad);
  const yMax = $derived(yHi + pad);

  const plotW = W - M.l - M.r;
  const plotH = $derived(height - M.t - M.b);

  function xOf(t) {
    return M.l + (tMax === tMin ? 0.5 : (t - tMin) / (tMax - tMin)) * plotW;
  }
  function yOf(v) {
    return M.t + (yMax === yMin ? 0.5 : 1 - (v - yMin) / (yMax - yMin)) * plotH;
  }
  function path(data) {
    return data.map((p, i) => `${i ? 'L' : 'M'}${xOf(p[0]).toFixed(1)},${yOf(p[1]).toFixed(1)}`).join(' ');
  }

  const yTicks = $derived(
    Array.from({ length: 5 }, (_, i) => yMin + ((yMax - yMin) * i) / 4)
  );
  const xTicks = $derived(
    hasData ? Array.from({ length: 4 }, (_, i) => tMin + ((tMax - tMin) * i) / 3) : []
  );
  function hhmm(t) {
    const d = new Date(t * 1000);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }
</script>

<div class="w-full">
  <svg viewBox="0 0 {W} {height}" class="w-full" style="height:auto" role="img">
    <!-- y gridlines + labels -->
    {#each yTicks as ty}
      <line x1={M.l} y1={yOf(ty)} x2={W - M.r} y2={yOf(ty)} stroke="#eee" stroke-width="1" />
      <text x={M.l - 6} y={yOf(ty) + 3} text-anchor="end" font-size="11" fill="#999">
        {ty.toFixed(Math.abs(yMax - yMin) < 5 ? 1 : 0)}
      </text>
    {/each}
    <!-- x ticks -->
    {#each xTicks as tx}
      <text x={xOf(tx)} y={height - 8} text-anchor="middle" font-size="11" fill="#999">{hhmm(tx)}</text>
    {/each}
    <!-- y axis label -->
    {#if yLabel}
      <text x={4} y={M.t + 4} font-size="10" fill="#bbb">{yLabel}</text>
    {/if}

    {#if hasData}
      {#each series as s}
        {#if s.data.length}
          <path
            d={path(s.data)}
            fill="none"
            stroke={s.color}
            stroke-width="1.8"
            stroke-dasharray={s.dash ? '5 4' : '0'}
            stroke-linejoin="round"
          />
        {/if}
      {/each}
    {:else}
      <text x={W / 2} y={height / 2} text-anchor="middle" font-size="13" fill="#bbb">
        No data in range
      </text>
    {/if}
  </svg>

  <!-- legend -->
  <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 px-2">
    {#each series as s}
      <span class="flex items-center gap-1.5 text-xs text-gray-600">
        <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke={s.color} stroke-width="2" stroke-dasharray={s.dash ? '4 3' : '0'} /></svg>
        {s.name}
      </span>
    {/each}
  </div>
</div>
