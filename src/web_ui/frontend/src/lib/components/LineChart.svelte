<script>
  // Dependency-free SVG line chart (offline/kiosk-safe — no chart library).
  // Compact Grafana-style: small fonts, gridlines, dots (when sparse), a
  // Name/Min/Max/Mean legend, hover tooltip, and a fixed time domain.
  // Props:
  //   series         : [{ name, color, data:[[tSeconds, value], ...] }]
  //   height         : px (viewBox height of the plot only)
  //   tStart, tEnd   : force the x-axis domain (selected window) — lines only
  //                    drawn where data exists, axis spans the whole range.
  let { series = [], height = 150, tStart = null, tEnd = null } = $props();

  const W = 820;
  const M = { t: 10, r: 14, b: 24, l: 44 };

  const flat = $derived(series.flatMap((s) => s.data));
  const hasData = $derived(flat.length > 0);

  const fixedDomain = $derived(tStart != null && tEnd != null && tEnd > tStart);
  const tMin = $derived(fixedDomain ? tStart : (hasData ? Math.min(...flat.map((p) => p[0])) : 0));
  const tMax = $derived(fixedDomain ? tEnd : (hasData ? Math.max(...flat.map((p) => p[0])) : 1));
  let yLo = $derived(hasData ? Math.min(...flat.map((p) => p[1])) : 0);
  let yHi = $derived(hasData ? Math.max(...flat.map((p) => p[1])) : 1);

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

  const yTicks = $derived(Array.from({ length: 4 }, (_, i) => yMin + ((yMax - yMin) * i) / 3));
  const xTicks = $derived(
    hasData || fixedDomain ? Array.from({ length: 4 }, (_, i) => tMin + ((tMax - tMin) * i) / 3) : []
  );
  const dec = $derived(Math.abs(yMax - yMin) < 5 ? 1 : 0);
  function hhmm(t) {
    const d = new Date(t * 1000);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }
  function mmddhhmm(t) {
    const d = new Date(t * 1000);
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  function stats(s) {
    const vs = s.data.map((p) => p[1]);
    if (!vs.length) return { min: '–', max: '–', mean: '–' };
    const f = (v) => v.toFixed(dec);
    return { min: f(Math.min(...vs)), max: f(Math.max(...vs)), mean: f(vs.reduce((a, b) => a + b, 0) / vs.length) };
  }

  // ── hover tooltip ──
  const allTs = $derived([...new Set(flat.map((p) => p[0]))].sort((a, b) => a - b));
  const seriesMaps = $derived(series.map((s) => ({ name: s.name, color: s.color, map: new Map(s.data) })));
  let hover = $state(null); // { t, items:[{name,color,value}], cssX, cssY, flip }

  function onMove(e) {
    if (!hasData) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const vbX = ((e.clientX - rect.left) / rect.width) * W;
    const t = tMin + ((vbX - M.l) / plotW) * (tMax - tMin);
    let nearest = allTs[0], best = Infinity;
    for (const ts of allTs) { const d = Math.abs(ts - t); if (d < best) { best = d; nearest = ts; } }
    const items = seriesMaps
      .filter((s) => s.map.has(nearest))
      .map((s) => ({ name: s.name, color: s.color, value: s.map.get(nearest) }));
    if (!items.length) { hover = null; return; }
    const cssX = e.clientX - rect.left;
    hover = { t: nearest, items, cssX, cssY: e.clientY - rect.top, flip: cssX > rect.width * 0.6 };
  }
  function onLeave() { hover = null; }
</script>

<div class="relative w-full">
  <svg viewBox="0 0 {W} {height}" class="w-full" style="height:auto" role="img"
       onmousemove={onMove} onmouseleave={onLeave}>
    <!-- gridlines + y labels -->
    {#each yTicks as ty}
      <line x1={M.l} y1={yOf(ty)} x2={W - M.r} y2={yOf(ty)} stroke="#eee" stroke-width="0.4" />
      <text x={M.l - 5} y={yOf(ty) + 2.5} text-anchor="end" font-size="7.5" fill="#999">{ty.toFixed(dec)}</text>
    {/each}
    <!-- vertical gridlines + x labels -->
    {#each xTicks as tx}
      <line x1={xOf(tx)} y1={M.t} x2={xOf(tx)} y2={height - M.b} stroke="#f4f4f4" stroke-width="0.4" />
      <text x={xOf(tx)} y={height - 5} text-anchor="middle" font-size="7.5" fill="#999">{hhmm(tx)}</text>
    {/each}

    {#if hasData}
      {#each series as s}
        {#if s.data.length}
          <path d={path(s.data)} fill="none" stroke={s.color} stroke-width="0.9" stroke-linejoin="round" />
        {/if}
      {/each}

      {#if hover}
        <line x1={xOf(hover.t)} y1={M.t} x2={xOf(hover.t)} y2={height - M.b}
              stroke="#bbb" stroke-width="1" stroke-dasharray="3 3" />
        {#each hover.items as it}
          <circle cx={xOf(hover.t)} cy={yOf(it.value)} r="2.6" fill={it.color} stroke="#fff" stroke-width="0.8" />
        {/each}
      {/if}
    {:else}
      <text x={W / 2} y={height / 2} text-anchor="middle" font-size="11" fill="#bbb">No data in range</text>
    {/if}
  </svg>

  {#if hover}
    <div class="absolute pointer-events-none z-10 bg-white/95 border border-gray-200 rounded shadow-md p-2 text-[10px] min-w-[120px]"
         style="left:{hover.cssX}px; top:{hover.cssY}px; transform: {hover.flip ? 'translate(-100%, -8px) translateX(-12px)' : 'translate(0, -8px) translateX(12px)'}">
      <div class="font-semibold text-gray-600 mb-1">{mmddhhmm(hover.t)}</div>
      {#each hover.items as it}
        <div class="flex items-center gap-1.5 py-px">
          <span class="w-2 h-2 rounded-full shrink-0" style="background:{it.color}"></span>
          <span class="text-gray-600 truncate">{it.name}</span>
          <span class="ml-auto pl-2 tabular-nums font-medium text-gray-800">{it.value.toFixed(dec)}</span>
        </div>
      {/each}
    </div>
  {/if}

  <!-- legend: Name / Min / Max / Mean -->
  {#if hasData}
    <table class="w-full text-[11.5px] mt-1 border-collapse">
      <thead>
        <tr class="text-gray-400 border-b border-gray-100">
          <th class="text-left font-medium py-0.5">Name</th>
          <th class="text-right font-medium px-2">Min</th>
          <th class="text-right font-medium px-2">Max</th>
          <th class="text-right font-medium pl-2">Mean</th>
        </tr>
      </thead>
      <tbody>
        {#each series as s}
          {@const st = stats(s)}
          <tr class="text-gray-600">
            <td class="py-0.5">
              <span class="inline-flex items-center gap-1.5">
                <svg width="14" height="6"><line x1="0" y1="3" x2="14" y2="3" stroke={s.color} stroke-width="2" /></svg>
                {s.name}
              </span>
            </td>
            <td class="text-right px-2 tabular-nums text-gray-500">{st.min}</td>
            <td class="text-right px-2 tabular-nums text-gray-500">{st.max}</td>
            <td class="text-right pl-2 tabular-nums text-gray-700">{st.mean}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>
