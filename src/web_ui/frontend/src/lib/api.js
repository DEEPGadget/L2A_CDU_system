const BASE = '/api'

export async function fetchSensors() {
  const res = await fetch(`${BASE}/sensor/`)
  if (!res.ok) return {}
  return res.json()
}

export async function fetchAlarms() {
  const res = await fetch(`${BASE}/sensor/alarms`)
  if (!res.ok) return {}
  return res.json()
}

export async function setPumpDuty(duty) {
  await fetch(`${BASE}/control/pump_duty?duty=${duty}`, { method: 'POST' })
}

export async function setFanVoltage(voltage) {
  await fetch(`${BASE}/control/fan_voltage?voltage=${voltage}`, { method: 'POST' })
}

export async function fetchHistory(metric, hours = 1) {
  const res = await fetch(`${BASE}/history/${metric}?hours=${hours}`)
  if (!res.ok) return []
  return res.json()
}
