<script>
  // Circle-i help icon shown next to a title. Coloured (cdu-l1) to invite a
  // click; toggles a small popover with explanatory text. Closes on outside
  // click or a second click. Pass the description via `text`.
  let { text = '' } = $props();

  let open = $state(false);

  function toggle(e) {
    e.stopPropagation();
    open = !open;
  }
  function close() { open = false; }

  // Close on any outside click while open.
  $effect(() => {
    if (!open) return;
    const onDoc = () => close();
    document.addEventListener('click', onDoc);
    return () => document.removeEventListener('click', onDoc);
  });
</script>

<span class="relative inline-flex items-center align-middle">
  <button
    type="button"
    onclick={toggle}
    aria-label="More info"
    class="text-cdu-l1 hover:text-cdu-l1/70 transition-colors"
  >
    <svg class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  </button>

  {#if open}
    <div
      onclick={(e) => e.stopPropagation()}
      role="tooltip"
      class="absolute left-0 top-6 z-30 w-80 bg-white border border-gray-200 rounded-lg shadow-lg
             p-3 text-xs leading-relaxed text-gray-600 font-normal normal-case tracking-normal
             whitespace-pre-line"
    >
      {text}
    </div>
  {/if}
</span>
