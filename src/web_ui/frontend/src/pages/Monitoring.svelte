<script>
  import { onMount, onDestroy } from 'svelte'
  import { fetchSensors, fetchAlarms, fetchComm, setPumpDuty, setFanVoltage } from '../lib/api.js'

  let sensors = {}
  let alarms = {}
  let comm = {}
  let pumpDuty = 0
  let fanVoltage = 0
  let interval

  const SENSOR_LABELS = {
    'sensor:coolant_temp_inlet': 'Coolant Temp (Inlet)',
    'sensor:coolant_temp_outlet': 'Coolant Temp (Outlet)',
    'sensor:ambient_temp': 'Ambient Temp',
    'sensor:ambient_humidity': 'Ambient Humidity',
    'sensor:pressure': 'Pressure',
    'sensor:flow_rate': 'Flow Rate',
    'sensor:water_level': 'Water Level',
    'sensor:leak': 'Leak',
    'sensor:pump_status': 'Pump Status',
    'sensor:fan_status': 'Fan Status',
    'control:pump_duty': 'Pump Duty (%)',
    'control:fan_voltage': 'Fan Voltage (V)',
  }

  const COMM_LABELS = {
    'comm:status': 'Comm Status',
    'comm:consecutive_failures': 'Comm Failures',
    'comm:last_error': 'Last Comm Error',
  }

  onMount(() => {
    refresh()
    interval = setInterval(refresh, 1000)
  })

  onDestroy(() => clearInterval(interval))

  async function refresh() {
    ;[sensors, alarms, comm] = await Promise.all([fetchSensors(), fetchAlarms(), fetchComm()])
    pumpDuty = parseFloat(sensors['control:pump_duty'] ?? 0)
    fanVoltage = parseFloat(sensors['control:fan_voltage'] ?? 0)
  }
</script>

<main>
  {#if Object.keys(alarms).length > 0}
    <section class="alarm-banner">
      {#each Object.keys(alarms) as key}
        <span class="alarm-item">{key}</span>
      {/each}
    </section>
  {/if}

  <section class="sensor-grid">
    {#each Object.entries(SENSOR_LABELS) as [key, label]}
      <div class="card">
        <span class="card-label">{label}</span>
        <span class="card-value">{sensors[key] ?? '--'}</span>
      </div>
    {/each}
    {#each Object.entries(COMM_LABELS) as [key, label]}
      <div class="card">
        <span class="card-label">{label}</span>
        <span class="card-value">{comm[key] ?? '--'}</span>
      </div>
    {/each}
  </section>

  <section class="controls">
    <div class="control-row">
      <label>Pump Duty: <strong>{pumpDuty}%</strong></label>
      <input
        type="range" min="0" max="100" step="1"
        bind:value={pumpDuty}
        on:change={() => setPumpDuty(pumpDuty)}
      />
    </div>
    <div class="control-row">
      <label>Fan Voltage: <strong>{fanVoltage.toFixed(1)} V</strong></label>
      <input
        type="range" min="0" max="12" step="0.1"
        bind:value={fanVoltage}
        on:change={() => setFanVoltage(fanVoltage)}
      />
    </div>
  </section>
</main>

<style>
  main { padding: 1rem; }

  .alarm-banner {
    background: #3d1a1a;
    border: 1px solid #f85149;
    border-radius: 6px;
    padding: 0.5rem 1rem;
    margin-bottom: 1rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .alarm-item {
    background: #f85149;
    color: #fff;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.8rem;
  }

  .sensor-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .card-label { font-size: 0.78rem; color: #8b949e; }
  .card-value { font-size: 1.4rem; font-weight: bold; }

  .controls {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .control-row { display: flex; flex-direction: column; gap: 0.4rem; }
  input[type='range'] { width: 100%; accent-color: #1f6feb; }
</style>
