// Client-side mirror of src/thresholds.py (subset used for dashboard coloring).
// Keep in sync with the Python source of truth.

const T = {
  INLET_NORMAL_LO: 22, INLET_NORMAL_HI: 40, INLET_CRIT_LO: 18, INLET_CRIT_HI: 45,
  OUTLET_WARN_LO: 22, OUTLET_CRIT_LO: 18, OUTLET_NORMAL_HI: 60, OUTLET_CRIT_HI: 65,
  DELTA_LO: 10, DELTA_HI: 14,
  AMB_T_WARN_HI: 40, AMB_T_CRIT_HI: 45,
  AMB_H_CRIT_LO: 8, AMB_H_WARN_HI: 60, AMB_H_CRIT_HI: 80,
};

// status ∈ 'normal' | 'warning' | 'critical' | 'nodata'
export function statusInlet(v) {
  if (v == null) return 'nodata';
  if (v > T.INLET_CRIT_HI || v < T.INLET_CRIT_LO) return 'critical';
  if (v > T.INLET_NORMAL_HI || v < T.INLET_NORMAL_LO) return 'warning';
  return 'normal';
}

export function statusOutlet(v) {
  if (v == null) return 'nodata';
  if (v > T.OUTLET_CRIT_HI || v < T.OUTLET_CRIT_LO) return 'critical';
  if (v > T.OUTLET_NORMAL_HI || v < T.OUTLET_WARN_LO) return 'warning';
  return 'normal';
}

export function statusDelta(v) {
  if (v == null) return 'nodata';
  if (v < T.DELTA_LO || v > T.DELTA_HI) return 'warning';
  return 'normal';
}

export function statusAmbientTemp(v) {
  if (v == null) return 'nodata';
  if (v > T.AMB_T_CRIT_HI) return 'critical';
  if (v > T.AMB_T_WARN_HI) return 'warning';
  return 'normal';
}

export function statusAmbientHum(v) {
  if (v == null) return 'nodata';
  if (v > T.AMB_H_CRIT_HI || v < T.AMB_H_CRIT_LO) return 'critical';
  if (v > T.AMB_H_WARN_HI) return 'warning';
  return 'normal';
}

export function statusWaterLevel(v) {
  // v is the discrete string "2"/"1"/"0"
  if (v === '2') return 'normal';
  if (v === '1') return 'warning';
  if (v === '0') return 'critical';
  return 'nodata';
}

export function statusLeak(v) {
  if (v === 'NORMAL') return 'normal';
  if (v === 'LEAKED') return 'critical';
  return 'nodata';
}

const TEXT_CLASS = {
  normal: 'text-cdu-normal',
  warning: 'text-cdu-warning',
  critical: 'text-cdu-critical',
  nodata: 'text-gray-400',
};
export function textClass(status) {
  // Certification period: threshold/alarm COLORING disabled — all values render
  // neutral (no warning/critical colours). The status* helpers are kept for the
  // post-cert alarm rework. Restore `TEXT_CLASS[status] ?? TEXT_CLASS.nodata`.
  return 'text-gray-800';
}

export const WATER_LABEL = { '2': 'HIGH', '1': 'MIDDLE', '0': 'LOW' };
