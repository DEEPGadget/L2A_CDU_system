<script>
  // Manual-mode pump/fan PWM duty editor (UI %). Writes sensor:*_pwm_duty_*
  // via PUT /api/control/duty. Editable only in manual mode (auto/emergency
  // → read-only). Pump min 0 (=stop), fan min 10.
  import { api } from '$lib/api.js';
  import DutyField from './DutyField.svelte';
  import InfoTip from './InfoTip.svelte';

  let { duty, disabled = false, onsaved = () => {},
        info = 'Set pump/fan PWM directly in manual mode. Pump 0 % = stop (1–100 → 17–85 %), fan ≥ 10 %.' } = $props();

  let pump1 = $state(duty?.pump_1 ?? 78);
  let pump2 = $state(duty?.pump_2 ?? 78);
  let fan1  = $state(duty?.fan_1 ?? 100);
  let fan2  = $state(duty?.fan_2 ?? 100);

  // Reset locals only when a duty VALUE changes (cross-UI sync). Comparing
  // values (not object identity) avoids clobbering the user's typing when the
  // live store reassigns its object every poll cycle.
  let lastSeen = $state(null);
  $effect(() => {
    if (!duty) return;
    if (!lastSeen || duty.pump_1 !== lastSeen.pump_1 || duty.pump_2 !== lastSeen.pump_2 ||
        duty.fan_1 !== lastSeen.fan_1 || duty.fan_2 !== lastSeen.fan_2) {
      pump1 = duty.pump_1; pump2 = duty.pump_2; fan1 = duty.fan_1; fan2 = duty.fan_2;
      lastSeen = { ...duty };
    }
  });

  const dirty = $derived(
    pump1 !== (duty?.pump_1 ?? 78) || pump2 !== (duty?.pump_2 ?? 78) ||
    fan1 !== (duty?.fan_1 ?? 100) || fan2 !== (duty?.fan_2 ?? 100)
  );
  let saving = $state(false);
  let error = $state('');

  async function save() {
    saving = true; error = '';
    try {
      const payload = { pump_1: pump1, pump_2: pump2, fan_1: fan1, fan_2: fan2 };
      await api.putDuty(payload);
      onsaved(payload);
    } catch (e) { error = String(e); }
    finally { saving = false; }
  }
</script>

<div class="bg-white border border-gray-200 rounded-md p-4 space-y-3 {disabled ? 'opacity-60' : ''}">
  <div class="flex items-center gap-2">
    <h2 class="text-[14px] font-semibold text-gray-700">Manual PWM</h2>
    <InfoTip text={info} />
  </div>

  <div class="grid grid-cols-2 gap-3">
    <DutyField caption="Pump L1" suffix="%" bind:value={pump1} min={0}  max={100} dotColor="#1f77b4" {disabled} />
    <DutyField caption="Pump L2" suffix="%" bind:value={pump2} min={0}  max={100} dotColor="#9467bd" {disabled} />
    <DutyField caption="Fan L1"  suffix="%" bind:value={fan1}  min={10} max={100} dotColor="#1f77b4" {disabled} />
    <DutyField caption="Fan L2"  suffix="%" bind:value={fan2}  min={10} max={100} dotColor="#9467bd" {disabled} />
  </div>

  {#if error}<div class="text-xs text-cdu-critical break-all">{error}</div>{/if}

  <div class="flex justify-end">
    <button type="button" onclick={save}
      disabled={disabled || !dirty || saving}
      class="px-4 py-1.5 rounded-md text-[13px] font-semibold bg-cdu-l1 text-white hover:bg-cdu-l1/90
             disabled:bg-gray-300 disabled:cursor-not-allowed">
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</div>
