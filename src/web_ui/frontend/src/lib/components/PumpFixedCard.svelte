<script>
  // Auto-mode pump fixed-duty editor — independent L1/L2.
  // Writes control:pump_duty_1/_2 (x10) via PUT /api/control/pump_duty.
  // The UI works in percent; the parent supplies {"1": x10, "2": x10}.
  import { api } from '$lib/api.js';
  import DutyField from './DutyField.svelte';
  import Card from './Card.svelte';

  let { pumpDuty = {}, disabled = false, onsaved = () => {} } = $props();

  const toPct = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n / 10 : 60; };

  let d1 = $state(toPct(pumpDuty['1']));
  let d2 = $state(toPct(pumpDuty['2']));

  // Reset locals only when a value actually changes (cross-UI sync).
  let lastSeen = $state(null);
  $effect(() => {
    const a = toPct(pumpDuty['1']), b = toPct(pumpDuty['2']);
    if (!lastSeen || lastSeen.a !== a || lastSeen.b !== b) { d1 = a; d2 = b; lastSeen = { a, b }; }
  });

  const dirty = $derived(d1 !== toPct(pumpDuty['1']) || d2 !== toPct(pumpDuty['2']));
  let saving = $state(false);
  let error = $state('');

  async function save() {
    saving = true; error = '';
    try {
      const payload = { duty_1: Math.round(d1 * 10), duty_2: Math.round(d2 * 10) };
      await api.putPumpDuty(payload);
      onsaved({ '1': payload.duty_1, '2': payload.duty_2 });
    } catch (e) { error = String(e); }
    finally { saving = false; }
  }
</script>

<Card title="Pump Fixed Duty (Auto)"
      info="In Auto mode each loop's pump runs at its own fixed duty (L1/L2 independent). Lower bound 20 % (Pump spec 4.2.1 Nmin)."
      class={disabled ? 'opacity-60' : ''} bodyClass="px-4 py-3 space-y-3">
  <div class="grid grid-cols-2 gap-3">
    <DutyField caption="Pump L1" suffix="%" bind:value={d1} min={20} max={100} dotColor="#1f77b4" {disabled} />
    <DutyField caption="Pump L2" suffix="%" bind:value={d2} min={20} max={100} dotColor="#9467bd" {disabled} />
  </div>

  {#if error}<div class="text-[11px] text-cdu-critical break-all">{error}</div>{/if}

  <div class="flex justify-end">
    <button type="button" onclick={save}
      disabled={disabled || !dirty || saving}
      class="px-4 py-1.5 rounded-md text-[13px] font-semibold bg-blue-600 text-white
             hover:bg-blue-700 disabled:bg-indigo-200 disabled:cursor-not-allowed">
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</Card>
