<script>
  import '../app.css';
  import TopHeader from '$lib/components/TopHeader.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';

  let { children } = $props();
</script>

<div class="h-screen flex flex-col">
  <TopHeader />
  <div class="flex flex-1 min-h-0">
    <Sidebar />
    <main class="flex-1 overflow-y-auto bg-gray-50">
      {@render children()}
    </main>
  </div>
</div>
