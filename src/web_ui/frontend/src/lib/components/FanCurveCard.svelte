<script>
  // 2-point linear fan curve editor. Same data contract as
  // src/local_ui/pages/settings_page.py FanCurveCard:
  //   control:fan_curve = hash { min_temp, max_temp, min_duty, max_duty }
  //   *_duty stored as x10 integer (0~1000). UI works in percent (0~100).
  import { api } from '$lib/api.js';
  import DutyField from './DutyField.svelte';
  import Card from './Card.svelte';

  let { fanCurve, disabled = false, onsaved = () => {},
        info = 'Below idle temp → idle PWM. Above warning temp → max PWM. Linear interpolation between.' } = $props();

  // Local working copy, in percent for duty fields.
  let minTemp     = $state(fanCurve.min_temp);
  let maxTemp     = $state(fanCurve.max_temp);
  let minDutyPct  = $state(fanCurve.min_duty / 10);
  let maxDutyPct  = $state(fanCurve.max_duty / 10);

  // Reset locals when the parent supplies a refreshed snapshot (post-save / re-mount).
  let lastSeen = $state(fanCurve);
  $effect(() => {
    if (fanCurve !== lastSeen) {
      minTemp    = fanCurve.min_temp;
      maxTemp    = fanCurve.max_temp;
      minDutyPct = fanCurve.min_duty / 10;
      maxDutyPct = fanCurve.max_duty / 10;
      lastSeen   = fanCurve;
    }
  });

  const dirty = $derived(
    minTemp    !== fanCurve.min_temp     ||
    maxTemp    !== fanCurve.max_temp     ||
    minDutyPct !== fanCurve.min_duty / 10 ||
    maxDutyPct !== fanCurve.max_duty / 10
  );

  let saving = $state(false);
  let error  = $state('');

  const validationError = $derived.by(() => {
    if (minTemp    >= maxTemp)    return 'Idle Temp must be < Warning Temp';
    if (minDutyPct >= maxDutyPct) return 'Idle PWM must be < Max PWM';
    return '';
  });

  async function save() {
    if (validationError) { error = validationError; return; }
    saving = true;
    error  = '';
    try {
      await api.putFanCurve({
        min_temp: minTemp,
        max_temp: maxTemp,
        min_duty: minDutyPct * 10,
        max_duty: maxDutyPct * 10
      });
      onsaved({ min_temp: minTemp, max_temp: maxTemp,
                min_duty: minDutyPct * 10, max_duty: maxDutyPct * 10 });
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }
</script>

<Card title="Fan Curve (Auto)" {info} class={disabled ? 'opacity-60' : ''} bodyClass="px-4 py-3 space-y-3">
  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
    <fieldset class="border border-gray-200 rounded-md p-3 space-y-2">
      <legend class="px-1.5 text-[10px] font-bold text-emerald-700 tracking-widest uppercase">Idle</legend>
      <DutyField caption="Idle Temp" suffix="°C"
                 bind:value={minTemp} min={0} max={100}
                 dotColor="#10b981" {disabled} />
      <DutyField caption="Idle PWM"  suffix="%"
                 bind:value={minDutyPct} min={10} max={100}
                 dotColor="#10b981" {disabled} />
    </fieldset>

    <fieldset class="border border-gray-200 rounded-md p-3 space-y-2">
      <legend class="px-1.5 text-[10px] font-bold text-rose-700 tracking-widest uppercase">Warning</legend>
      <DutyField caption="Warning Temp" suffix="°C"
                 bind:value={maxTemp} min={0} max={100}
                 dotColor="#f43f5e" {disabled} />
      <DutyField caption="Max PWM"      suffix="%"
                 bind:value={maxDutyPct} min={10} max={100}
                 dotColor="#f43f5e" {disabled} />
    </fieldset>
  </div>

  {#if validationError && dirty}
    <div class="text-[11px] text-cdu-critical">{validationError}</div>
  {/if}
  {#if error}
    <div class="text-[11px] text-cdu-critical break-all">{error}</div>
  {/if}

  <div class="flex justify-end">
    <button
      type="button"
      onclick={save}
      disabled={disabled || !dirty || saving || !!validationError}
      class="px-4 py-1.5 rounded-md text-[13px] font-semibold bg-cdu-l1 text-white
             hover:bg-cdu-l1/90 disabled:bg-gray-300 disabled:cursor-not-allowed"
    >
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</Card>
