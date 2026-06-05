"""Duty mapping between UI domain and PCB hardware register values.

UI domain
    Pump duty (UI 0~100 %)    - what the user enters in Local UI / Web UI.
    Fan  duty (UI 0~100 %)    - same.

PCB Holding Register value
    0~1000 = 0.0~100.0 % (per PCB.md "Holding Registers", spec stores as x10).

Pump mapping (PCB.md UI / MCG duty mapping):
    The pump's usable band is 17~85 % PWM (Pump spec 4.2.1: 17 %=Nmin,
    85 %=Nmax linear upper bound). The UI 0~100 % maps onto it as:
        UI 0      -> 12 % PWM  (STOP — spec 8~13 % band gives n=0)
        UI (0,100] -> 17 + 0.68*ui  %  (linear Nmin~Nmax), clamped [17,85]
    => UI 0   -> HR 120 (stop)
       UI 100 -> HR 850 (Nmax)
    Mapping UI 0 to the explicit stop band (12 %) — rather than 0 % — also
    removes the old "UI 0 % -> 0-8 % Nmax safety fallback" hazard: a 0 from
    any path now stops the pump instead of running it at full speed.

Fan mapping:
    fan_input_pwm = ui_duty               (direct, fan spec allows 0~100%)
    => HR value = round(ui_duty * 10), no clamp other than [0, 1000].

UI lower bounds: pump now allows 0 (= stop); fan keeps a 10 % operational
floor (FAN_MIN_UI_DUTY) enforced at the UI layer. See
src/local_ui/pages/settings_page.py.
"""

from __future__ import annotations

PUMP_HR_STOP = 120                  # 12 % of 1000 -> Pump spec 8~13 % stop band (n=0)
PUMP_HR_MIN = 170                   # 17 % of 1000 (Pump spec Nmin)
PUMP_HR_MAX = 850                   # 85 % of 1000 (Pump spec Nmax linear upper bound)
PUMP_SLOPE  = 0.68                  # (85-17)/100 — UI 1~100 % -> 17~85 % pump

FAN_HR_MIN = 0
FAN_HR_MAX = 1000

PUMP_MIN_UI_DUTY = 0                # %, 0 = stop (no enforced floor)
FAN_MIN_UI_DUTY  = 10              # %, documented at UI layer


def ui_to_pump_hr(ui_duty: float) -> int:
    """UI pump duty (0-100 %) -> PCB Holding Register value.

    UI 0 -> PUMP_HR_STOP (12 %, pump stops). UI (0,100] -> linear 17~85 %
    (Nmin~Nmax), clamped to [PUMP_HR_MIN, PUMP_HR_MAX].
    """
    ui = float(ui_duty)
    if ui <= 0:
        return PUMP_HR_STOP
    raw = round((17.0 + PUMP_SLOPE * ui) * 10.0)
    return max(PUMP_HR_MIN, min(PUMP_HR_MAX, raw))


def ui_to_fan_hr(ui_duty: float) -> int:
    """UI fan duty (0-100 %) -> PCB Holding Register value (0-1000)."""
    raw = float(ui_duty) * 10.0
    return max(FAN_HR_MIN, min(FAN_HR_MAX, round(raw)))
