import random
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from .automation import apply_automation_decisions
from .models import SensorReading, SensorSimulationSettings


SIMULATED_DEVICE_ID = 'SIMULATED_ESP32'
SIMULATION_INTERVAL = timedelta(seconds=10)
REAL_SENSOR_TIMEOUT = timedelta(minutes=5)
# The ESP32 uploads a reading only every 10 minutes, so a short gap must not
# hand automation over to simulated data while the hardware is still alive.
LIVE_AUTOMATION_TIMEOUT = timedelta(minutes=15)


def create_simulated_sensor_reading(force=False):
    """Create one gradual simulated reading when real sensor data is stale."""
    simulation_settings = SensorSimulationSettings.load()
    if not simulation_settings.enabled:
        return None

    now = timezone.now()
    live_reading_is_fresh = SensorReading.objects.exclude(
        device_id=SIMULATED_DEVICE_ID
    ).filter(timestamp__gte=now - REAL_SENSOR_TIMEOUT).exists()
    if not force and live_reading_is_fresh:
        return None

    temperature_min = float(simulation_settings.temperature_min)
    temperature_max = float(simulation_settings.temperature_max)
    humidity_min = float(simulation_settings.humidity_min)
    humidity_max = float(simulation_settings.humidity_max)
    air_quality_min = simulation_settings.air_quality_min
    air_quality_max = simulation_settings.air_quality_max

    latest = SensorReading.objects.filter(
        device_id=SIMULATED_DEVICE_ID
    ).first()
    latest_out_of_range = latest and (
        not temperature_min <= float(latest.temperature) <= temperature_max
        or not humidity_min <= float(latest.humidity) <= humidity_max
        or latest.air_quality_ppm is not None
        and not air_quality_min <= latest.air_quality_ppm <= air_quality_max
    )
    if (
        latest
        and not force
        and not latest_out_of_range
        and now - latest.timestamp < SIMULATION_INTERVAL
    ):
        return None

    temperature = float(latest.temperature) if latest else (temperature_min + temperature_max) / 2
    humidity = float(latest.humidity) if latest else (humidity_min + humidity_max) / 2
    air_quality = (
        latest.air_quality_ppm
        if latest and latest.air_quality_ppm is not None
        else (air_quality_min + air_quality_max) // 2
    )

    temperature = min(temperature_max, max(
        temperature_min,
        temperature + ((temperature_min + temperature_max) / 2 - temperature) * 0.15
        + random.uniform(-0.2, 0.2),
    ))
    humidity = min(humidity_max, max(
        humidity_min,
        humidity + ((humidity_min + humidity_max) / 2 - humidity) * 0.15
        + random.uniform(-0.5, 0.5),
    ))
    air_quality = min(air_quality_max, max(
        air_quality_min,
        air_quality + ((air_quality_min + air_quality_max) // 2 - air_quality) * 0.15
        + random.randint(-8, 8),
    ))

    reading = SensorReading.objects.create(
        temperature=Decimal(str(round(temperature, 1))),
        humidity=Decimal(str(round(humidity, 1))),
        air_quality_ppm=round(air_quality),
        device_id=SIMULATED_DEVICE_ID,
    )

    # Simulated readings drive the same automatic controls as live readings,
    # so demo data can turn the fan/humidifier/lights on and off too. Skip the
    # automation pass while the hardware has reported recently, otherwise
    # simulated and real decisions would fight over the same relays.
    live_automation_source_active = SensorReading.objects.exclude(
        device_id=SIMULATED_DEVICE_ID
    ).filter(timestamp__gte=now - LIVE_AUTOMATION_TIMEOUT).exists()
    if not live_automation_source_active:
        apply_automation_decisions(
            float(reading.temperature),
            float(reading.humidity),
            reading.air_quality_ppm,
            source='simulated',
        )

    return reading


def ensure_dashboard_sensor_reading():
    """Return the latest reading, creating a fallback if physical sensors are stale."""
    create_simulated_sensor_reading()
    if not SensorSimulationSettings.load().enabled:
        return SensorReading.objects.exclude(
            device_id=SIMULATED_DEVICE_ID
        ).first()
    return SensorReading.objects.first()
