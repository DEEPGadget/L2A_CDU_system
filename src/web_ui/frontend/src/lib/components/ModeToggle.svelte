<script>
  import { api } from '$lib/api.js';

  let { mode = $bindable('auto'), onchange = () => {} } = $props();
  let saving = $state(false);
  let error = $state('');

  async function toggle() {
    const next = mode === 'auto' ? 'manual' : 'auto';
    saving = true;
    error = '';
    try {
      await api.putMode(next);
      mode = next;
      onchange(next);
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }

  const isEmergency = $derived(mode === 'emergency');
  const isAuto      = $derived(mode === 'auto');
</script>

<div class="bg-white border border-gray-200 rounded-xl px-5 py-4 flex items-center gap-5">
  <div class="text-xs font-bold text-gray-500 tracking-widest uppercase">Control Mode</div>

  <div class="text-lg font-bold {isEmergency ? 'text-cdu-critical' : 'text-gray-900'}">
    {isEmergency ? 'Emergency' : isAuto ? 'Auto' : 'Manual'}
  </div>

  <div class="flex-1"></div>

  {#if !isEmergency}
    <button
      type="button"
      onclick={toggle}
      disabled={saving}
      aria-pressed={isAuto}
      class="relative inline-flex items-center h-7 w-14 rounded-full transition-colors disabled:opacity-50
             {isAuto ? 'bg-cdu-l1' : 'bg-gray-300'}"
    >
      <span
        class="inline-block h-6 w-6 transform rounded-full bg-white shadow transition-transform
               {isAuto ? 'translate-x-7' : 'translate-x-1'}"
      ></span>
    </button>
  {:else}
    <span class="text-sm text-cdu-critical font-semibold">Toggle disabled</span>
  {/if}
</div>

{#if error}
  <div class="text-xs text-cdu-critical mt-1">{error}</div>
{/if}
