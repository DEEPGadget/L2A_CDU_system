// Cert-sensable numeric metrics for the History page (single registry).
// Only L2A CDU sensing/control values that MCG publishes (Prometheus via
// src/exporter). NO water_level / leak / alarm / pH / conductivity.
// All are continuous-numeric → Line/Table compatible, Timeline incompatible.

const LOOP_COLOR = { '1': '#1f77b4', '2': '#9467bd' };

export const METRICS = [
  { id: 'coolant_inlet',  group: 'Coolant Temp', label: 'Inlet',   unit: '°C',    query: 'sensor_coolant_temp_inlet',  dash: false },
  { id: 'coolant_outlet', group: 'Coolant Temp', label: 'Outlet',  unit: '°C',    query: 'sensor_coolant_temp_outlet', dash: true  },
  { id: 'flow_total',     group: 'Flow',         label: 'Flow',    unit: 'L/min', query: 'sensor_flow_rate',           dash: false },
  { id: 'flow_branch',    group: 'Flow',         label: 'Flow',    unit: 'L/min', query: 'sensor_flow_rate_branch',    dash: true  },
  { id: 'fan_rpm',        group: 'Fan',          label: 'Fan RPM', unit: 'RPM',   query: 'sensor_fan_rpm',             dash: false },
  { id: 'pump_duty',      group: 'PWM Duty',     label: 'Pump',    unit: '%',     query: 'sensor_pump_pwm_duty',       dash: false },
  { id: 'fan_duty',       group: 'PWM Duty',     label: 'Fan',     unit: '%',     query: 'sensor_fan_pwm_duty',        dash: true  },
  { id: 'ambient_temp',   group: 'Ambient',      label: 'Amb Temp', unit: '°C',   query: 'sensor_ambient_temp',        dash: false, color: '#e377c2' },
  { id: 'ambient_hum',    group: 'Ambient',      label: 'Amb Hum',  unit: '% RH', query: 'sensor_ambient_humidity',    dash: false, color: '#17becf' }
];

// All metrics are 'numeric'. Compatibility with graph forms.
export const FORM_COMPAT = {
  Line:     (m) => m.type !== 'state',     // numeric ok, state not
  Table:    () => true,                    // anything
  Timeline: (m) => m.type === 'state'      // only discrete state; numeric → incompatible
};
// attach type (all numeric here)
METRICS.forEach((m) => { m.type = 'numeric'; });

export const METRIC_GROUPS = [...new Set(METRICS.map((m) => m.group))];

// Build a display name for a Prometheus result series from its labels.
export function seriesName(metric, labels = {}) {
  let n = metric.label;
  if (labels.loop) n += ` L${labels.loop}`;
  if (labels.branch) n += `-${labels.branch}`;
  return n;
}
export function seriesColor(metric, labels = {}) {
  return metric.color ?? LOOP_COLOR[labels.loop] ?? '#1f77b4';
}
