<script>
  import Monitoring from './pages/Monitoring.svelte'
  import History from './pages/History.svelte'

  let currentPage = 'monitoring'
</script>

<nav>
  <button class:active={currentPage === 'monitoring'} on:click={() => (currentPage = 'monitoring')}>
    Monitoring
  </button>
  <button class:active={currentPage === 'history'} on:click={() => (currentPage = 'history')}>
    History
  </button>
</nav>

{#if currentPage === 'monitoring'}
  <Monitoring />
{:else}
  <History />
{/if}

<style>
  :global(body) {
    margin: 0;
    background: #0d1117;
    color: #e6edf3;
    font-family: sans-serif;
  }

  nav {
    display: flex;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: #161b22;
    border-bottom: 1px solid #21262d;
  }

  button {
    padding: 0.4rem 1.2rem;
    background: transparent;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  button.active {
    background: #1f6feb;
    color: #fff;
    border-color: #1f6feb;
  }
</style>
