<script>
  // English-only date/time selector. The native <input type="datetime-local">
  // renders in the browser's OS language (Korean here) even with lang="en", so
  // we use plain <select> dropdowns (numeric options → no locale text at all).
  // value is a "YYYY-MM-DDTHH:MM" string, compatible with new Date().
  let { value = $bindable('') } = $props();

  const pad = (n) => String(n).padStart(2, '0');
  const nowY = new Date().getFullYear();
  const years  = [nowY - 1, nowY, nowY + 1];
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  const days   = Array.from({ length: 31 }, (_, i) => i + 1);
  const hours  = Array.from({ length: 24 }, (_, i) => i);
  const mins   = Array.from({ length: 60 }, (_, i) => i);

  function parse(v) {
    const d = v ? new Date(v) : new Date();
    const dd = isNaN(d.getTime()) ? new Date() : d;
    return { y: dd.getFullYear(), m: dd.getMonth() + 1, d: dd.getDate(),
             h: dd.getHours(), mi: dd.getMinutes() };
  }
  let p = $state(parse(value));

  // Recompose the string value whenever a part changes.
  $effect(() => { value = `${p.y}-${pad(p.m)}-${pad(p.d)}T${pad(p.h)}:${pad(p.mi)}`; });

  const sel = 'border border-gray-300 rounded px-1 py-1 text-[13px] bg-white';
</script>

<span class="inline-flex items-center gap-0.5">
  <select bind:value={p.y} class={sel}>{#each years as y}<option value={y}>{y}</option>{/each}</select>
  <span class="text-gray-400">-</span>
  <select bind:value={p.m} class={sel}>{#each months as m}<option value={m}>{pad(m)}</option>{/each}</select>
  <span class="text-gray-400">-</span>
  <select bind:value={p.d} class={sel}>{#each days as d}<option value={d}>{pad(d)}</option>{/each}</select>
  <select bind:value={p.h} class="{sel} ml-1">{#each hours as h}<option value={h}>{pad(h)}</option>{/each}</select>
  <span class="text-gray-400">:</span>
  <select bind:value={p.mi} class={sel}>{#each mins as mi}<option value={mi}>{pad(mi)}</option>{/each}</select>
</span>
