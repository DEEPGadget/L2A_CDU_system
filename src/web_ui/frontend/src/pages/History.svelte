<script>
  import { fetchHistory } from '../lib/api.js'

  const METRICS = [
    'sensor_coolant_temp_inlet',
    'sensor_coolant_temp_outlet',
    'sensor_ambient_temp',
    'sensor_ambient_humidity',
    'sensor_pressure',
    'sensor_flow_rate',
    'sensor_water_level',
    'control_pump_duty',
    'control_fan_voltage',
    'control_cmd_pump_duty',
    'control_cmd_fan_voltage',
  ]

  const HOURS_OPTIONS = [
    { label: '1h', value: 1 },
    { label: '6h', value: 6 },
    { label: '24h', value: 24 },
    { label: '1 Week', value: 168 },
  ]

  let selectedMetric = METRICS[0]
  let selectedHours = 1
  let rows = []
  let loading = false

  async function load() {
    loading = true
    const result = await fetchHistory(selectedMetric, selectedHours)
    rows = result[0]?.values ?? []
    loading = false
  }

  function formatTs(ts) {
    return new Date(ts * 1000).toLocaleString('ko-KR')
  }
</script>

<main>
  <section class="toolbar">
    <select bind:value={selectedMetric}>
      {#each METRICS as m}
        <option value={m}>{m}</option>
      {/each}
    </select>

    <select bind:value={selectedHours}>
      {#each HOURS_OPTIONS as opt}
        <option value={opt.value}>{opt.label}</option>
      {/each}
    </select>

    <button on:click={load}>Query</button>
  </section>

  {#if loading}
    <p class="status">Loading...</p>
  {:else if rows.length === 0}
    <p class="status">No data</p>
  {:else}
    <table>
      <thead>
        <tr><th>Time</th><th>Value</th></tr>
      </thead>
      <tbody>
        {#each rows as [ts, val]}
          <tr>
            <td>{formatTs(ts)}</td>
            <td>{val}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</main>

<style>
  main { padding: 1rem; }

  .toolbar {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1rem;
    align-items: center;
  }

  select, button {
    padding: 0.4rem 0.8rem;
    background: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    cursor: pointer;
  }

  button:hover { background: #1f6feb; border-color: #1f6feb; }

  .status { color: #8b949e; }

  table { width: 100%; border-collapse: collapse; }

  th, td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #21262d;
    text-align: left;
    font-size: 0.9rem;
  }

  th { color: #8b949e; font-weight: normal; }
</style>
