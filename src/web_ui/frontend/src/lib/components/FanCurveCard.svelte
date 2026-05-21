<script>
  // 2-point linear fan curve editor. Same data contract as
  // src/local_ui/pages/settings_page.py FanCurveCard:
  //   control:fan_curve = hash { min_temp, max_temp, min_duty, max_duty }
  //   *_duty stored as x10 integer (0~1000). UI works in percent (0~100).
  import { api } from '$lib/api.js';
  import DutyField from './DutyField.svelte';

  let { fanCurve, disabled = false, onsaved = () => {} } = $props();

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

<div class="bg-white border border-gray-200 rounded-2xl p-6 space-y-4 {disabled ? 'opacity-60' : ''}">
  <div>
    <h2 class="text-lg font-bold text-gray-900">Fan Curve (Auto)</h2>
    <p class="text-sm text-gray-500 mt-1">
      Below idle temp &rarr; idle PWM. Above warning temp &rarr; max PWM.
      Linear interpolation between.
    </p>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
    <fieldset class="bg-emerald-50/50 border border-emerald-200 rounded-xl p-3 space-y-3">
      <legend class="px-2 text-xs font-bold text-emerald-700 tracking-widest uppercase">Idle</legend>
      <DutyField caption="Idle Temp" suffix="°C"
                 bind:value={minTemp} min={0} max={100}
                 dotColor="#10b981" {disabled} />
      <DutyField caption="Idle PWM"  suffix="%"
                 bind:value={minDutyPct} min={10} max={100}
                 dotColor="#10b981" {disabled} />
    </fieldset>

    <fieldset class="bg-rose-50/50 border border-rose-200 rounded-xl p-3 space-y-3">
      <legend class="px-2 text-xs font-bold text-rose-700 tracking-widest uppercase">Warning</legend>
      <DutyField caption="Warning Temp" suffix="°C"
                 bind:value={maxTemp} min={0} max={100}
                 dotColor="#f43f5e" {disabled} />
      <DutyField caption="Max PWM"      suffix="%"
                 bind:value={maxDutyPct} min={10} max={100}
                 dotColor="#f43f5e" {disabled} />
    </fieldset>
  </div>

  {#if validationError && dirty}
    <div class="text-xs text-cdu-critical">{validationError}</div>
  {/if}
  {#if error}
    <div class="text-xs text-cdu-critical break-all">{error}</div>
  {/if}

  <div class="flex justify-end">
    <button
      type="button"
      onclick={save}
      disabled={disabled || !dirty || saving || !!validationError}
      class="px-5 py-2 rounded-lg font-semibold bg-cdu-l1 text-white
             hover:bg-cdu-l1/90 disabled:bg-gray-300 disabled:cursor-not-allowed"
    >
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</div>
