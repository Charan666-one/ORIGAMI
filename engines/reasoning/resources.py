"""ResourceMonitor — lets ORIGAMI adapt to the hardware instead of exhausting it.

Reports RAM / CPU / battery / temperature (best-effort) and a simple `is_low()`
verdict the Brain Manager uses to prefer smaller models or defer heavy reasoning.
Degrades gracefully if psutil (or a given sensor) is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import psutil
except ImportError:  # keep the project usable without the optional dep
    psutil = None


@dataclass
class Resources:
    ram_available_gb: Optional[float]
    ram_percent: Optional[float]
    cpu_percent: Optional[float]
    battery_percent: Optional[float]
    on_battery: Optional[bool]
    temperature_c: Optional[float]


class ResourceMonitor:
    def __init__(self, min_ram_gb: float = 2.0, max_cpu_percent: float = 90.0,
                 min_battery_percent: float = 20.0) -> None:
        self.min_ram_gb = min_ram_gb
        self.max_cpu_percent = max_cpu_percent
        self.min_battery_percent = min_battery_percent

    def snapshot(self) -> Resources:
        if psutil is None:
            return Resources(None, None, None, None, None, None)

        vm = psutil.virtual_memory()
        battery_percent = on_battery = None
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                battery_percent = batt.percent
                on_battery = not batt.power_plugged
        except Exception:
            pass

        temperature_c = None
        try:  # sensors_temperatures is often absent on macOS — best effort only
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            readings = [t.current for group in temps.values() for t in group if t.current]
            if readings:
                temperature_c = max(readings)
        except Exception:
            pass

        return Resources(
            ram_available_gb=round(vm.available / 1_073_741_824, 2),
            ram_percent=vm.percent,
            cpu_percent=psutil.cpu_percent(interval=0.1),
            battery_percent=battery_percent,
            on_battery=on_battery,
            temperature_c=temperature_c,
        )

    def is_low(self) -> bool:
        """True if the machine is under pressure — prefer a smaller model / defer."""
        r = self.snapshot()
        if r.ram_available_gb is not None and r.ram_available_gb < self.min_ram_gb:
            return True
        if r.cpu_percent is not None and r.cpu_percent > self.max_cpu_percent:
            return True
        if (r.on_battery and r.battery_percent is not None
                and r.battery_percent < self.min_battery_percent):
            return True
        return False
