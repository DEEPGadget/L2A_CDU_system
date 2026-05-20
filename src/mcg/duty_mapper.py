"""Duty mapping between UI domain and PCB hardware register values.

UI domain
    Pump duty (UI 0~100 %)    - what the user enters in Local UI / Web UI.
    Fan  duty (UI 0~100 %)    - same.

PCB Holding Register value
    0~1000 = 0.0~100.0 % (per PCB.md "Holding Registers", spec stores as x10).

Pump mapping (PCB.md "Flow estimation > UI/MCG duty mapping"):
    pump_input_pwm = 0.85 * ui_duty      (direct proportion + 85% cap)
    => HR value = round(0.85 * ui_duty * 10) clamped to [170, 850]
    The clamp is the "hard guard" referenced in the Hazard box of PCB.md -
    it guarantees that even if a faulty path writes 0 or 100 to the duty
    redis key, the value sent to the PCB stays inside the safe Nmin~Nmax
    band of Pump spec 4.2.1 (avoids both the 95-100% no-use region and the
    0-8% Nmax safety fallback trigger).

Fan mapping:
    fan_input_pwm = ui_duty               (direct, fan spec allows 0~100%)
    => HR value = round(ui_duty * 10), no clamp other than [0, 1000].

UI lower bounds (FAN_MIN_UI_DUTY / PUMP_MIN_UI_DUTY) are enforced at the UI
layer (NumpadDialog + Settings page). They mirror the values used by
src/local_ui/pages/settings_page.py for documentation; the hard guard above
remains independent.
"""

from __future__ import annotations

PUMP_MAPPING_FACTOR = 0.85          # ui_duty -> pump_input_pwm
PUMP_HR_MIN = 170                   # 17 % of 1000 (Pump spec Nmin)
PUMP_HR_MAX = 850                   # 85 % of 1000 (Pump spec linear upper bound)

FAN_HR_MIN = 0
FAN_HR_MAX = 1000

PUMP_MIN_UI_DUTY = 20               # %, documented at UI layer
FAN_MIN_UI_DUTY  = 10               # %, documented at UI layer


def ui_to_pump_hr(ui_duty: float) -> int:
    """UI pump duty (0-100 %) -> PCB Holding Register value (170-850).

    Always clamped to [PUMP_HR_MIN, PUMP_HR_MAX]. Even ui_duty=0 maps to
    PUMP_HR_MIN (Nmin) instead of 0, which would trigger the spec 0-8%
    safety fallback and run the pump at full speed.
    """
    raw = PUMP_MAPPING_FACTOR * float(ui_duty) * 10.0
    return max(PUMP_HR_MIN, min(PUMP_HR_MAX, round(raw)))


def ui_to_fan_hr(ui_duty: float) -> int:
    """UI fan duty (0-100 %) -> PCB Holding Register value (0-1000)."""
    raw = float(ui_duty) * 10.0
    return max(FAN_HR_MIN, min(FAN_HR_MAX, round(raw)))


def loop_flow_lpm(ui_duty: float, max_loop_lpm: float = 35.0) -> float:
    """Derive per-loop flow in L/min from pump UI duty.

    PCB.md A5: `flow_loop_lpm = max_loop_lpm * (ui_duty / 100)`
    Default max 35 LPM/loop -> total max 70 LPM with two loops.
    """
    duty = max(0.0, min(100.0, float(ui_duty)))
    return max_loop_lpm * duty / 100.0
