<script>
  import '../app.css';
  import TopBar from '$lib/components/TopBar.svelte';

  let { children } = $props();
</script>

<div class="min-h-screen flex flex-col">
  <TopBar />
  <main class="flex-1">
    {@render children()}
  </main>
</div>
