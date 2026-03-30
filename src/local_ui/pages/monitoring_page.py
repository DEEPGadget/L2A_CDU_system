from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, QSlider, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer
from db.redis_client import RedisClient
from ipc.pcg_client import PcgClient

SENSOR_KEYS = [
    "sensor:coolant_temp_inlet",
    "sensor:coolant_temp_outlet",
    "sensor:ambient_temp",
    "sensor:ambient_humidity",
    "sensor:pressure",
    "sensor:flow_rate",
    "sensor:water_level",
    "sensor:leak",
    "sensor:pump_status",
    "sensor:fan_status",
    "control:pump_duty",
    "control:fan_voltage",
    "control:result:pump_duty",
    "control:result:fan_voltage",
    "comm:status",
    "comm:consecutive_failures",
    "comm:last_error",
]

SENSOR_LABELS = {
    "sensor:coolant_temp_inlet": "Coolant Temp (Inlet)",
    "sensor:coolant_temp_outlet": "Coolant Temp (Outlet)",
    "sensor:ambient_temp": "Ambient Temp",
    "sensor:ambient_humidity": "Ambient Humidity",
    "sensor:pressure": "Pressure",
    "sensor:flow_rate": "Flow Rate",
    "sensor:water_level": "Water Level",
    "sensor:leak": "Leak",
    "sensor:pump_status": "Pump Status",
    "sensor:fan_status": "Fan Status",
    "control:pump_duty": "Pump Duty (%)",
    "control:fan_voltage": "Fan Voltage (V)",
    "control:result:pump_duty": "Pump Cmd Result",
    "control:result:fan_voltage": "Fan Cmd Result",
    "comm:status": "Comm Status",
    "comm:consecutive_failures": "Comm Failures",
    "comm:last_error": "Last Comm Error",
}


class MonitoringPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.redis = RedisClient()
        self.pcg = PcgClient()
        self._build_ui()
        self._start_polling()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # sensor status grid
        sensor_box = QGroupBox("Sensor Status")
        grid = QGridLayout(sensor_box)
        self.value_labels: dict[str, QLabel] = {}
        for i, key in enumerate(SENSOR_KEYS):
            name_label = QLabel(SENSOR_LABELS[key])
            val_label = QLabel("--")
            self.value_labels[key] = val_label
            grid.addWidget(name_label, i // 3, (i % 3) * 2)
            grid.addWidget(val_label, i // 3, (i % 3) * 2 + 1)
        layout.addWidget(sensor_box)

        # control sliders
        ctrl_box = QGroupBox("Control")
        ctrl_layout = QVBoxLayout(ctrl_box)

        ctrl_layout.addWidget(QLabel("Pump Duty (0 ~ 100 %)"))
        self.pump_slider = QSlider(Qt.Horizontal)
        self.pump_slider.setRange(0, 100)
        self.pump_slider.sliderReleased.connect(self._on_pump_released)
        ctrl_layout.addWidget(self.pump_slider)

        ctrl_layout.addWidget(QLabel("Fan Voltage (0 ~ 12 V)"))
        self.fan_slider = QSlider(Qt.Horizontal)
        self.fan_slider.setRange(0, 120)  # 0.1V resolution (x10)
        self.fan_slider.sliderReleased.connect(self._on_fan_released)
        ctrl_layout.addWidget(self.fan_slider)

        layout.addWidget(ctrl_box)

    def _start_polling(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)

    def _refresh(self):
        data = self.redis.get_all(SENSOR_KEYS)
        for key, label in self.value_labels.items():
            label.setText(data.get(key) or "--")

    def _on_pump_released(self):
        self.pcg.send_control("set_pump_duty", self.pump_slider.value())

    def _on_fan_released(self):
        self.pcg.send_control("set_fan_voltage", self.fan_slider.value() / 10.0)
