// Map live Redis state → cooling_health.svg {TOKEN} placeholders (value + _C color).
// Ports src/local_ui/widgets/cooling_health.py (_KEY_TO_PLACEHOLDER + _update_colors).
// Absent keys render as "--" (no-data); pH/conductivity are "-" (not measured).
import * as th from './thresholds.js';

const HEX = { normal: '#27ae60', warning: '#e67e22', critical: '#e74c3c', nodata: '#000000' };
const hex = (status) => HEX[status] ?? HEX.nodata;

function num(data, key) {
  const n = parseFloat(data[key]);
  return Number.isFinite(n) ? n : null;
}
const f1 = (v) => (v == null ? '--' : v.toFixed(1));
const i0 = (v) => (v == null ? '--' : String(Math.round(v)));

// The Web diagram is display-only — the ⚙ control indicator is always hidden
// (control lives in the Control cards). `mode` is accepted for signature parity.
export function buildTokens(data, mode = 'manual') {
  const inlet1 = num(data, 'sensor:coolant_temp_inlet_1');
  const inlet2 = num(data, 'sensor:coolant_temp_inlet_2');
  const outlet1 = num(data, 'sensor:coolant_temp_outlet_1');
  const outlet2 = num(data, 'sensor:coolant_temp_outlet_2');
  const wl = data['sensor:water_level'];
  const gear = '';

  return {
    // Reservoir
    WATER_LEVEL: th.WATER_LABEL[wl] ?? '--',
    WATER_LEVEL_C: hex(th.statusWaterLevel(wl)),
    PH: '-', PH_C: HEX.nodata,
    CONDUCTIVITY: '-', CONDUCTIVITY_C: HEX.nodata,
    // Pump
    PUMP_DUTY_1: i0(num(data, 'sensor:pump_pwm_duty_1')),
    PUMP_DUTY_2: i0(num(data, 'sensor:pump_pwm_duty_2')),
    // Inlet / Outlet manifold
    INLET_1: f1(inlet1), INLET_1_C: hex(th.statusInlet(inlet1)),
    INLET_2: f1(inlet2), INLET_2_C: hex(th.statusInlet(inlet2)),
    OUTLET_1: f1(outlet1), OUTLET_1_C: hex(th.statusOutlet(outlet1)),
    OUTLET_2: f1(outlet2), OUTLET_2_C: hex(th.statusOutlet(outlet2)),
    // Flow (total + branches)
    FLOW_1: f1(num(data, 'sensor:flow_rate_1')),
    FLOW_2: f1(num(data, 'sensor:flow_rate_2')),
    FLOW_1_1: f1(num(data, 'sensor:flow_rate_1_1')),
    FLOW_1_2: f1(num(data, 'sensor:flow_rate_1_2')),
    FLOW_2_1: f1(num(data, 'sensor:flow_rate_2_1')),
    FLOW_2_2: f1(num(data, 'sensor:flow_rate_2_2')),
    // Fan + Radiator
    FAN_RPM_1: i0(num(data, 'sensor:fan_rpm_1')),
    FAN_RPM_2: i0(num(data, 'sensor:fan_rpm_2')),
    FAN_DUTY_1: i0(num(data, 'sensor:fan_pwm_duty_1')),
    FAN_DUTY_2: i0(num(data, 'sensor:fan_pwm_duty_2')),
    GEAR: gear
  };
}
