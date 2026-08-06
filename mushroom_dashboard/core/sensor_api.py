"""
API Views for DHT22 Sensor Data Integration
Handles incoming sensor readings from ESP32/Arduino devices
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
from .models import SensorReading, Notification
from .notification_service import evaluate_environment_notifications

# Optional: Add your API key here for basic authentication
API_KEY = None  # Change this to a secure key


@csrf_exempt  # Exempt from CSRF for external devices
@require_http_methods(["POST"])
def receive_sensor_data(request):
    """
    API endpoint to receive DHT22 sensor data from ESP32
    
    Expected JSON payload:
    {
        "temperature": 16.5,
        "humidity": 85.2,
        "device_id": "ESP32_001" (optional)
    }
    """
    try:
        # Optional: Check API key for authentication
        api_key = request.headers.get('X-API-Key')
        if API_KEY and api_key != API_KEY:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid API key'
            }, status=401)
        
        # Parse JSON data
        data = json.loads(request.body)
        
        # Validate required fields
        if 'temperature' not in data or 'humidity' not in data:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields: temperature and humidity'
            }, status=400)
        
        # Extract data
        temperature = Decimal(str(data['temperature']))
        humidity = Decimal(str(data['humidity']))
        air_quality_ppm = data.get('air_quality_ppm', None)  # MQ-135 air quality (optional)
        device_id = data.get('device_id', 'DHT22_MQ135_ESP32')
        
        # Create sensor reading
        reading = SensorReading.objects.create(
            temperature=temperature,
            humidity=humidity,
            air_quality_ppm=air_quality_ppm,
            device_id=device_id,
            co2_ppm=None  # DHT22 doesn't measure CO2
        )
        
        # Evaluate environmental notifications with cooldown and recovery handling
        notification_events = evaluate_environment_notifications(reading)
        alerts = [event['description'] for event in notification_events]

        if temperature < 10:
            alerts.append("Temperature critically low")
        elif temperature > 21:
            alerts.append("Temperature critically high")
        elif not reading.is_temperature_optimal:
            alerts.append("Temperature outside optimal range (13-18°C)")

        if humidity < 70:
            alerts.append("Humidity too low")
        elif humidity > 98:
            alerts.append("Humidity too high")
        elif not reading.is_humidity_optimal:
            alerts.append("Humidity outside optimal range (80-95%)")

        if air_quality_ppm is not None:
            if air_quality_ppm >= 800:
                alerts.append("Air quality is poor - increase ventilation")
            elif air_quality_ppm >= 400:
                alerts.append("Air quality acceptable")
        
        # Prepare response
        response_data = {
            'status': 'success',
            'message': 'Sensor data received successfully',
            'data': {
                'id': reading.id,
                'timestamp': reading.timestamp.isoformat(),
                'temperature': float(reading.temperature),
                'humidity': float(reading.humidity),
                'air_quality_ppm': air_quality_ppm,
                'condition_status': reading.condition_status,
                'alerts': alerts
            }
        }
        
        return JsonResponse(response_data, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_latest_sensor_data(request):
    """
    API endpoint to get the latest sensor readings
    Returns the last 10 readings by default
    """
    try:
        limit = int(request.GET.get('limit', 10))
        readings = SensorReading.objects.all()[:limit]
        
        data = [{
            'id': reading.id,
            'timestamp': reading.timestamp.isoformat(),
            'temperature': float(reading.temperature),
            'humidity': float(reading.humidity),
            'device_id': reading.device_id,
            'condition_status': reading.condition_status
        } for reading in readings]
        
        return JsonResponse({
            'status': 'success',
            'count': len(data),
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_sensor_statistics(request):
    """
    API endpoint to get sensor statistics
    Returns min, max, and average values
    """
    try:
        from django.db.models import Avg, Min, Max
        from datetime import timedelta
        
        # Get statistics for the last 24 hours by default
        hours = int(request.GET.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        stats = SensorReading.objects.filter(
            timestamp__gte=since
        ).aggregate(
            avg_temp=Avg('temperature'),
            min_temp=Min('temperature'),
            max_temp=Max('temperature'),
            avg_humidity=Avg('humidity'),
            min_humidity=Min('humidity'),
            max_humidity=Max('humidity')
        )
        
        return JsonResponse({
            'status': 'success',
            'period_hours': hours,
            'statistics': {
                'temperature': {
                    'average': round(float(stats['avg_temp'] or 0), 1),
                    'minimum': float(stats['min_temp'] or 0),
                    'maximum': float(stats['max_temp'] or 0)
                },
                'humidity': {
                    'average': round(float(stats['avg_humidity'] or 0), 1),
                    'minimum': float(stats['min_humidity'] or 0),
                    'maximum': float(stats['max_humidity'] or 0)
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ==========================================
# ESP32 Control State Endpoints
# ==========================================

@csrf_exempt
@require_http_methods(["GET"])
def get_control_states(request):
    """
    API endpoint for ESP32 to fetch current control states.
    The ESP32 polls this endpoint to know when to turn fan/humidifier/heater ON/OFF.
    
    Returns JSON:
    {
        "status": "success",
        "controls": {
            "fan_on": true/false,
            "fan_value": 0-100,
            "humidifier_on": true/false,
            "heater_on": true/false,
            "co2_on": true/false,
            "lights_on": true/false
        }
    }
    """
    try:
        from .models import EnvironmentSettings
        settings = EnvironmentSettings.load()
        
        return JsonResponse({
            'status': 'success',
            'controls': {
                'fan_on': settings.fan_on,
                'fan_auto': settings.fan_auto,
                'fan_value': settings.fan_value,
                'humidifier_on': settings.humidifier_on,
                'humidifier_auto': settings.humidifier_auto,
                'humidifier_value': settings.humidifier_value,
                'heater_on': settings.heater_on,
                'heater_auto': settings.heater_auto,
                'heater_value': settings.heater_value,
                'co2_on': settings.co2_on,
                'lights_on': settings.lights_on,
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_control_action(request):
    """
    ESP32 confirms it executed a control action.
    Useful for logging and verification that hardware responded.
    
    Expected JSON payload:
    {
        "device_id": "ESP32_001",
        "action": "FAN_ON" or "FAN_OFF" or "HUMIDIFIER_ON" etc.,
        "success": true/false
    }
    """
    try:
        data = json.loads(request.body)
        device_id = data.get('device_id', 'ESP32_001')
        action = data.get('action', 'UNKNOWN')
        success = data.get('success', True)
        
        # Log the action
        from .models import AutomationLog
        AutomationLog.objects.create(
            action=action,
            reason=f'ESP32 device {device_id} executed command (success: {success})',
            triggered_by=f'ESP32_{device_id}'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Action {action} logged for device {device_id}'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


# ==========================================
# Automation Decision Endpoint (Core Logic)
# ==========================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def get_automation_decision(request):
    """
    Core automation endpoint that ESP32/Arduino polls to get relay control commands.
    
    This endpoint implements the Manual vs Automatic mode logic:
    
    AUTOMATIC MODE (fan_auto=True):
    - Reads latest sensor data from database
    - Compares against configured thresholds
    - Returns whether relay should be ON or OFF
    - Automatically updates EnvironmentSettings state
    
    MANUAL MODE (fan_auto=False):
    - Returns the manual switch state from dashboard
    - Sensor data does NOT override manual control
    
    GET: Returns current control states with automation decisions
    POST: Accepts sensor data and returns immediate automation decision
    
    Response JSON:
    {
        "status": "success",
        "mode": "automatic" or "manual",
        "controls": {
            "fan": {
                "should_be_on": true/false,
                "current_state": true/false,
                "mode": "auto/manual",
                "reason": "explanation"
            },
            "humidifier": {...},
            "heater": {...},
            "lights": {...}
        },
        "sensor_readings": {
            "temperature": 28.5,
            "humidity": 85.2,
            "air_quality_ppm": 450,
            "light_lux": 320.5
        },
        "thresholds": {
            "fan_temp": 30.0,
            "fan_humidity": 95.0,
            ...
        }
    }
    """
    try:
        from .models import EnvironmentSettings, SensorReading, AutomationLog
        
        settings = EnvironmentSettings.load()
        
        # Get sensor readings - either from POST body or from database
        if request.method == 'POST':
            # ESP32 is sending live sensor data
            data = json.loads(request.body)
            temperature = float(data.get('temperature', 0))
            humidity = float(data.get('humidity', 0))
            air_quality_ppm = data.get('air_quality_ppm', None)
            light_lux_raw = data.get('light_lux', None)
            try:
                light_lux = float(light_lux_raw) if light_lux_raw is not None else None
            except (TypeError, ValueError):
                light_lux = None
            device_id = data.get('device_id', 'ESP32_001')
            
            # Optionally save the reading to database
            if data.get('save_reading', True):
                SensorReading.objects.create(
                    temperature=temperature,
                    humidity=humidity,
                    air_quality_ppm=air_quality_ppm,
                    device_id=device_id
                )
        else:
            # GET request - use latest sensor reading from database
            latest_reading = SensorReading.objects.order_by('-timestamp').first()
            if latest_reading:
                temperature = float(latest_reading.temperature)
                humidity = float(latest_reading.humidity)
                air_quality_ppm = latest_reading.air_quality_ppm
                # SensorReading model currently does not store light lux.
                light_lux = None
            else:
                # No sensor data available
                return JsonResponse({
                    'status': 'error',
                    'message': 'No sensor data available. Send sensor readings via POST or wait for ESP32 data.'
                }, status=400)
        
        # Get automation decisions
        decisions = settings.get_automation_decision(temperature, humidity, air_quality_ppm)
        
        # Build response for each control
        controls_response = {}
        state_changed = False
        
        # --- Fan Control ---
        if settings.fan_auto:
            fan_should_be_on = decisions['fan_should_be_on']
            if fan_should_be_on is not None and fan_should_be_on != settings.fan_on:
                # State change needed - update settings
                settings.fan_on = fan_should_be_on
                state_changed = True
                
                # Log the automation action
                action = 'VENTILATION_ON' if fan_should_be_on else 'VENTILATION_OFF'
                AutomationLog.objects.create(
                    action=action,
                    reason=f"Auto: {'; '.join([r for r in decisions['reasons'] if 'Temperature' in r or 'Humidity' in r or 'Air quality' in r][:2]) or 'Threshold check'}",
                    temperature_before=temperature,
                    humidity_before=humidity,
                    co2_before=air_quality_ppm or 0,
                    confidence=100.0
                )
            
            controls_response['fan'] = {
                'should_be_on': fan_should_be_on if fan_should_be_on is not None else settings.fan_on,
                'current_state': settings.fan_on,
                'mode': 'automatic',
                'reason': next((r for r in decisions['reasons'] if 'fan' in r.lower() or 'temperature' in r.lower() or 'humidity' in r.lower() and 'exceeds' in r.lower()), 'Within normal range')
            }
        else:
            # Manual mode - just return current switch state
            controls_response['fan'] = {
                'should_be_on': settings.fan_on,
                'current_state': settings.fan_on,
                'mode': 'manual',
                'reason': 'Manual control - dashboard switch state'
            }
        
        # --- Humidifier Control ---
        if settings.humidifier_auto:
            hum_should_be_on = decisions['humidifier_should_be_on']
            if hum_should_be_on is not None and hum_should_be_on != settings.humidifier_on:
                settings.humidifier_on = hum_should_be_on
                state_changed = True
                
                action = 'HUMIDIFIER_ON' if hum_should_be_on else 'HUMIDIFIER_OFF'
                AutomationLog.objects.create(
                    action=action,
                    reason=f"Auto: {'; '.join([r for r in decisions['reasons'] if 'umidity' in r][:1]) or 'Threshold check'}",
                    temperature_before=temperature,
                    humidity_before=humidity,
                    co2_before=air_quality_ppm or 0,
                    confidence=100.0
                )
            
            controls_response['humidifier'] = {
                'should_be_on': hum_should_be_on if hum_should_be_on is not None else settings.humidifier_on,
                'current_state': settings.humidifier_on,
                'mode': 'automatic',
                'reason': next((r for r in decisions['reasons'] if 'umidity' in r), 'Within target range')
            }
        else:
            controls_response['humidifier'] = {
                'should_be_on': settings.humidifier_on,
                'current_state': settings.humidifier_on,
                'mode': 'manual',
                'reason': 'Manual control - dashboard switch state'
            }
        
        # --- Heater Control ---
        if settings.heater_auto:
            heater_should_be_on = decisions['heater_should_be_on']
            if heater_should_be_on is not None and heater_should_be_on != settings.heater_on:
                settings.heater_on = heater_should_be_on
                state_changed = True
                
                action = 'HEATER_ON' if heater_should_be_on else 'HEATER_OFF'
                AutomationLog.objects.create(
                    action=action,
                    reason=f"Auto: {'; '.join([r for r in decisions['reasons'] if 'Temperature' in r and 'threshold' in r][:1]) or 'Threshold check'}",
                    temperature_before=temperature,
                    humidity_before=humidity,
                    co2_before=air_quality_ppm or 0,
                    confidence=100.0
                )
            
            controls_response['heater'] = {
                'should_be_on': heater_should_be_on if heater_should_be_on is not None else settings.heater_on,
                'current_state': settings.heater_on,
                'mode': 'automatic',
                'reason': next((r for r in decisions['reasons'] if 'heater' in r.lower() or ('temperature' in r.lower() and 'below' in r.lower())), 'Within target range')
            }
        else:
            controls_response['heater'] = {
                'should_be_on': settings.heater_on,
                'current_state': settings.heater_on,
                'mode': 'manual',
                'reason': 'Manual control - dashboard switch state'
            }

        # --- Grow Light Control (Lux-based) ---
        if settings.lights_auto:
            # Map UI value (0-100%) to an ambient lux target (100-1000 lux).
            target_lux = 100.0 + (max(0.0, min(float(settings.lights_value), 100.0)) / 100.0) * 900.0
            lux_hysteresis = 50.0
            lights_should_be_on = settings.lights_on

            if light_lux is None:
                lights_reason = 'Automatic mode enabled, waiting for BH1750 lux data'
            elif light_lux < (target_lux - lux_hysteresis):
                lights_should_be_on = True
                lights_reason = f'Light level {light_lux:.1f} lux is below target {target_lux:.0f} lux'
            elif light_lux > (target_lux + lux_hysteresis):
                lights_should_be_on = False
                lights_reason = f'Light level {light_lux:.1f} lux is above target {target_lux:.0f} lux'
            else:
                lights_reason = f'Light level {light_lux:.1f} lux is within hysteresis around target {target_lux:.0f} lux'

            if lights_should_be_on != settings.lights_on:
                settings.lights_on = lights_should_be_on
                state_changed = True

            controls_response['lights'] = {
                'should_be_on': lights_should_be_on,
                'current_state': settings.lights_on,
                'mode': 'automatic',
                'reason': lights_reason
            }
        else:
            controls_response['lights'] = {
                'should_be_on': settings.lights_on,
                'current_state': settings.lights_on,
                'mode': 'manual',
                'reason': 'Manual control - dashboard switch state'
            }
        
        # Save settings if any state changed
        if state_changed:
            settings.save()
        
        return JsonResponse({
            'status': 'success',
            'controls': controls_response,
            'sensor_readings': {
                'temperature': temperature,
                'humidity': humidity,
                'air_quality_ppm': air_quality_ppm,
                'light_lux': light_lux
            },
            'thresholds': {
                'fan_temp_threshold': float(settings.fan_temp_threshold),
                'fan_humidity_threshold': float(settings.fan_humidity_threshold),
                'fan_air_quality_threshold': settings.fan_air_quality_threshold,
                'humidifier_low_threshold': float(settings.humidifier_low_threshold),
                'humidifier_high_threshold': float(settings.humidifier_high_threshold),
                'heater_low_threshold': float(settings.heater_low_threshold),
                'heater_high_threshold': float(settings.heater_high_threshold),
            },
            'target_values': decisions.get('target_values', {
                'fan_target_temp': settings.fan_value,
                'target_humidity': settings.humidifier_value,
                'target_temperature': settings.heater_value,
                'target_co2': settings.co2_value,
                'light_intensity': settings.lights_value,
                'light_target_lux': 100.0 + (max(0.0, min(float(settings.lights_value), 100.0)) / 100.0) * 900.0
            }),
            'automation_reasons': decisions['reasons']
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_relay_command(request):
    """
    Simplified endpoint for ESP32/Arduino to get relay ON/OFF commands.
    Returns simple boolean values that the microcontroller can directly use.
    
    This is the endpoint the ESP32 should poll every few seconds.
    
    Response JSON:
    {
        "fan": true/false,
        "humidifier": true/false,
        "heater": true/false,
        "co2": true/false,
        "lights": true/false
    }
    """
    try:
        from .models import EnvironmentSettings
        settings = EnvironmentSettings.load()
        
        return JsonResponse({
            'status': 'success',
            'relays': {
                'fan': settings.fan_on,
                'humidifier': settings.humidifier_on,
                'heater': settings.heater_on,
                'co2': settings.co2_on,
                'lights': settings.lights_on
            },
            'target_values': {
                'fan_target_temp': settings.fan_value,
                'target_humidity': settings.humidifier_value,
                'target_temperature': settings.heater_value,
                'target_co2': settings.co2_value,
                'light_intensity': settings.lights_value
            },
            'auto_modes': {
                'fan_auto': settings.fan_auto,
                'humidifier_auto': settings.humidifier_auto,
                'heater_auto': settings.heater_auto,
                'co2_auto': settings.co2_auto,
                'lights_auto': settings.lights_auto
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
