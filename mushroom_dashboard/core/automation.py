"""Shared automation engine for live and simulated sensor readings.

Both the ESP32 automation endpoint and the dashboard simulator go through
:func:`apply_automation_decisions`. That keeps automatic fan, humidifier and
grow-light behaviour identical no matter where the measurement came from.
"""

from .models import AutomationLog, EnvironmentSettings


def apply_automation_decisions(
    temperature,
    humidity,
    air_quality_ppm=None,
    light_lux=None,
    source='device',
    settings=None,
):
    """Compare readings against thresholds, persist changes, and log them.

    ``source`` is either ``'device'`` for live ESP32 readings or
    ``'simulated'`` for dashboard-generated readings. It only affects the log
    text so the automation history shows where a change came from.

    Returns a dict with the loaded ``settings``, the raw ``decisions``, the
    per-device ``controls`` response and ``state_changed``.
    """
    if settings is None:
        settings = EnvironmentSettings.load()

    decisions = settings.get_automation_decision(
        temperature, humidity, air_quality_ppm
    )
    controls = {}
    state_changed = False
    log_prefix = 'Auto (simulated)' if source == 'simulated' else 'Auto'

    # --- Fan Control ---
    if settings.fan_auto:
        fan_should_be_on = decisions['fan_should_be_on']
        if fan_should_be_on is not None and fan_should_be_on != settings.fan_on:
            settings.fan_on = fan_should_be_on
            state_changed = True

            action = 'VENTILATION_ON' if fan_should_be_on else 'VENTILATION_OFF'
            AutomationLog.objects.create(
                action=action,
                reason=(
                    f"{log_prefix}: "
                    f"{'; '.join([r for r in decisions['reasons'] if 'Temperature' in r or 'Humidity' in r or 'Air quality' in r][:2]) or 'Threshold check'}"
                ),
                temperature_before=temperature,
                humidity_before=humidity,
                co2_before=air_quality_ppm or 0,
                confidence=100.0,
            )

        controls['fan'] = {
            'should_be_on': (
                fan_should_be_on
                if fan_should_be_on is not None
                else settings.fan_on
            ),
            'current_state': settings.fan_on,
            'mode': 'automatic',
            'reason': next(
                (
                    r
                    for r in decisions['reasons']
                    if 'fan' in r.lower()
                    or 'temperature' in r.lower()
                    or 'humidity' in r.lower()
                    and 'exceeds' in r.lower()
                ),
                'Within normal range',
            ),
        }
    else:
        controls['fan'] = {
            'should_be_on': settings.fan_on,
            'current_state': settings.fan_on,
            'mode': 'manual',
            'reason': 'Manual control - dashboard switch state',
        }

    # --- Humidifier Control ---
    if settings.humidifier_auto:
        hum_should_be_on = decisions['humidifier_should_be_on']
        if (
            hum_should_be_on is not None
            and hum_should_be_on != settings.humidifier_on
        ):
            settings.humidifier_on = hum_should_be_on
            state_changed = True

            action = (
                'HUMIDIFIER_ON' if hum_should_be_on else 'HUMIDIFIER_OFF'
            )
            AutomationLog.objects.create(
                action=action,
                reason=(
                    f"{log_prefix}: "
                    f"{'; '.join([r for r in decisions['reasons'] if 'umidity' in r][:1]) or 'Threshold check'}"
                ),
                temperature_before=temperature,
                humidity_before=humidity,
                co2_before=air_quality_ppm or 0,
                confidence=100.0,
            )

        controls['humidifier'] = {
            'should_be_on': (
                hum_should_be_on
                if hum_should_be_on is not None
                else settings.humidifier_on
            ),
            'current_state': settings.humidifier_on,
            'mode': 'automatic',
            'reason': next(
                (r for r in decisions['reasons'] if 'umidity' in r),
                'Within target range',
            ),
        }
    else:
        controls['humidifier'] = {
            'should_be_on': settings.humidifier_on,
            'current_state': settings.humidifier_on,
            'mode': 'manual',
            'reason': 'Manual control - dashboard switch state',
        }

    # --- Grow Light Control (Lux-based) ---
    if settings.lights_auto:
        # Map UI value (0-100%) to an ambient lux target (100-1000 lux).
        target_lux = 100.0 + (
            max(0.0, min(float(settings.lights_value), 100.0)) / 100.0
        ) * 900.0
        lux_hysteresis = 50.0
        lights_should_be_on = settings.lights_on

        if light_lux is None:
            lights_reason = 'Automatic mode enabled, waiting for BH1750 lux data'
        elif light_lux < (target_lux - lux_hysteresis):
            lights_should_be_on = True
            lights_reason = (
                f'Light level {light_lux:.1f} lux is below target '
                f'{target_lux:.0f} lux'
            )
        elif light_lux > (target_lux + lux_hysteresis):
            lights_should_be_on = False
            lights_reason = (
                f'Light level {light_lux:.1f} lux is above target '
                f'{target_lux:.0f} lux'
            )
        else:
            lights_reason = (
                f'Light level {light_lux:.1f} lux is within hysteresis '
                f'around target {target_lux:.0f} lux'
            )

        if lights_should_be_on != settings.lights_on:
            settings.lights_on = lights_should_be_on
            state_changed = True

        controls['lights'] = {
            'should_be_on': lights_should_be_on,
            'current_state': settings.lights_on,
            'mode': 'automatic',
            'reason': lights_reason,
        }
    else:
        controls['lights'] = {
            'should_be_on': settings.lights_on,
            'current_state': settings.lights_on,
            'mode': 'manual',
            'reason': 'Manual control - dashboard switch state',
        }

    if state_changed:
        settings.save()

    return {
        'settings': settings,
        'decisions': decisions,
        'controls': controls,
        'state_changed': state_changed,
    }
