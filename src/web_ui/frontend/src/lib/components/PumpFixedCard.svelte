<script>
  // Pump fixed-duty editor. Same data contract as
  // src/local_ui/pages/settings_page.py PumpFixedCard:
  //   control:pump_duty = string (x10 integer, 0~1000). UI works in percent.
  // Lower bound 20 % (Pump spec 4.2.1 Nmin via 0.85x mapping).
  import { api } from '$lib/api.js';
  import DutyField from './DutyField.svelte';
  import InfoTip from './InfoTip.svelte';

  let { pumpDuty, disabled = false, onsaved = () => {} } = $props();

  let dutyPct = $state(pumpDuty / 10);
  let lastSeen = $state(pumpDuty);
  $effect(() => {
    if (pumpDuty !== lastSeen) {
      dutyPct  = pumpDuty / 10;
      lastSeen = pumpDuty;
    }
  });

  const dirty  = $derived(dutyPct !== pumpDuty / 10);
  let saving   = $state(false);
  let error    = $state('');

  async function save() {
    saving = true;
    error  = '';
    try {
      await api.putPumpDuty(dutyPct * 10);
      onsaved(dutyPct * 10);
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }
</script>

<div class="bg-white border border-gray-200 rounded-md p-4 space-y-3 {disabled ? 'opacity-60' : ''}">
  <div class="flex items-center gap-2">
    <h2 class="text-[14px] font-semibold text-gray-700">Pump Fixed Duty (Auto)</h2>
    <InfoTip text="In Auto mode the pump PWM duty runs at a fixed value. Lower bound 20 % (Pump spec 4.2.1 Nmin)." />
  </div>

  <fieldset class="bg-blue-50/50 border border-blue-200 rounded-md p-3">
    <legend class="px-2 text-xs font-bold text-blue-700 tracking-widest uppercase">Pump</legend>
    <DutyField caption="Pump Duty" suffix="%"
               bind:value={dutyPct} min={20} max={100}
               dotColor="#3b82f6" {disabled} />
  </fieldset>

  {#if error}
    <div class="text-xs text-cdu-critical break-all">{error}</div>
  {/if}

  <div class="flex justify-end">
    <button
      type="button"
      onclick={save}
      disabled={disabled || !dirty || saving}
      class="px-4 py-1.5 rounded-md text-[13px] font-semibold bg-cdu-l1 text-white
             hover:bg-cdu-l1/90 disabled:bg-gray-300 disabled:cursor-not-allowed"
    >
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</div>
