# Automation Control System Guide

## Overview

This guide explains how the **Manual vs Automatic Mode** system works for the Mushroom Farm IoT Environmental Control System.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐  │
│    │   SENSORS    │         │    DJANGO    │         │  DASHBOARD   │  │
│    │   (ESP32)    │────────▶│   BACKEND    │◀────────│    (Web)     │  │
│    │  DHT22+MQ135 │         │              │         │              │  │
│    └──────────────┘         └──────────────┘         └──────────────┘  │
│           │                        │                        │          │
│           │                        ▼                        │          │
│           │                 ┌──────────────┐                │          │
│           │                 │  AUTOMATION  │                │          │
│           │                 │    LOGIC     │                │          │
│           │                 │              │                │          │
│           │                 │ • Thresholds │                │          │
│           │                 │ • Decisions  │                │          │
│           │                 │ • Logging    │                │          │
│           │                 └──────────────┘                │          │
│           │                        │                        │          │
│           └────────────────────────┼────────────────────────┘          │
│                                    ▼                                   │
│                            ┌──────────────┐                            │
│                            │    RELAYS    │                            │
│                            │ Fan/Hum/Heat │                            │
│                            └──────────────┘                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## How It Works

### Mode Selection

Each device (fan, humidifier, heater) can operate in two modes:

| Mode | Description | Control Logic |
|------|-------------|---------------|
| **Automatic** | System controls based on sensor readings | Backend compares readings against thresholds |
| **Manual** | User controls via dashboard switch | Dashboard switch state is sent directly to relay |

### Data Flow

```
1. ESP32 reads DHT22 sensor → Temperature + Humidity
2. ESP32 POSTs data to /api/automation-decision/
3. Backend checks each device's mode:
   - If AUTO: Compare readings vs thresholds, decide ON/OFF
   - If MANUAL: Return current dashboard switch state
4. Backend returns relay commands to ESP32
5. ESP32 controls relays based on response
```

## API Endpoints

### 1. Automation Decision (Main Endpoint)

**Endpoint:** `POST /api/automation-decision/`

The ESP32 should call this endpoint every 3-5 seconds.

**Request:**
```json
{
    "temperature": 28.5,
    "humidity": 82.3,
    "air_quality_ppm": 450,
    "device_id": "ESP32_FARM_001",
    "save_reading": true
}
```

**Response:**
```json
{
    "status": "success",
    "controls": {
        "fan": {
            "should_be_on": true,
            "current_state": false,
            "mode": "automatic",
            "reason": "Temperature 28.5°C approaching threshold 30.0°C"
        },
        "humidifier": {
            "should_be_on": false,
            "current_state": false,
            "mode": "manual",
            "reason": "Manual control - dashboard switch state"
        },
        "heater": {
            "should_be_on": false,
            "current_state": false,
            "mode": "automatic",
            "reason": "Temperature within target range"
        }
    },
    "sensor_readings": {
        "temperature": 28.5,
        "humidity": 82.3,
        "air_quality_ppm": 450
    },
    "thresholds": {
        "fan_temp_threshold": 30.0,
        "fan_humidity_threshold": 95.0,
        "fan_air_quality_threshold": 600,
        "humidifier_low_threshold": 75.0,
        "humidifier_high_threshold": 90.0,
        "heater_low_threshold": 15.0,
        "heater_high_threshold": 20.0
    },
    "automation_reasons": [
        "Temperature 28.5°C approaching threshold"
    ]
}
```

### 2. Simple Relay Command

**Endpoint:** `GET /api/relay-command/`

Simplified endpoint for simple microcontrollers that just need ON/OFF states.

**Response:**
```json
{
    "status": "success",
    "poll_after_ms": 10000,
    "relays": {
        "fan": true,
        "humidifier": false,
        "heater": false,
        "co2": false,
        "lights": true
    },
    "auto_modes": {
        "fan_auto": true,
        "humidifier_auto": false,
        "heater_auto": true,
        "co2_auto": true,
        "lights_auto": false
    }
}
```

`poll_after_ms` is the delay the device should wait before polling again:
`2000` while an admin has the Environment Control page open, `10000`
otherwise. The ESP32 firmware uses it instead of a hardcoded interval, which
is what makes manual toggles apply in about two seconds without paying for a
fast poll all day.

**Endpoint:** `POST /api/manual-watch/` (admin session, empty body)

Sent by the Environment Control page every 20 s. It arms the fast window for
two minutes; the window expires by itself so idle polling (and the Vercel CPU
cost) returns to normal when the page is closed. Any settings change re-arms it
as well.

### 3. Confirm Action

**Endpoint:** `POST /api/control-confirm/`

ESP32 should call this after executing a relay change. Creates an automation log entry.

**Request:**
```json
{
    "device_id": "ESP32_FARM_001",
    "action": "VENTILATION_ON",
    "success": true
}
```

## Automation Logic

### Fan/Ventilation Control

The fan turns ON automatically when ANY of these conditions are met:

| Condition | Default Threshold | Action |
|-----------|-------------------|--------|
| Temperature > threshold | > 30°C | Fan ON |
| Humidity > threshold | > 95% | Fan ON |
| Air Quality > threshold | > 600 PPM | Fan ON |

The fan turns OFF when ALL conditions return to normal (with hysteresis margin).

### Humidifier Control

| Condition | Default Threshold | Action |
|-----------|-------------------|--------|
| Humidity < low threshold | < 75% | Humidifier ON |
| Humidity > high threshold | > 90% | Humidifier OFF |

### Heater Control

| Condition | Default Threshold | Action |
|-----------|-------------------|--------|
| Temperature < low threshold | < 15°C | Heater ON |
| Temperature > high threshold | > 20°C | Heater OFF |

### Hysteresis

To prevent rapid ON/OFF cycling, the system uses hysteresis:

```
Example: Fan temperature threshold = 30°C, Hysteresis = 2°C

Fan turns ON when: Temperature > 30°C
Fan turns OFF when: Temperature < 28°C (30 - 2)

This prevents the fan from cycling ON/OFF every second when 
temperature hovers around 30°C.
```

## Hardware Wiring

### ESP32 Pin Connections

```
ESP32 Pin    Connection
─────────────────────────
GPIO4   ──── DHT22 Data Pin
GPIO34  ──── MQ-135 Analog Out (optional)
GPIO16  ──── Relay 1 (Fan) IN
GPIO17  ──── Relay 2 (Humidifier) IN
GPIO18  ──── Relay 3 (Heater) IN
GPIO19  ──── Relay 4 (CO2) IN
GPIO21  ──── Relay 5 (Lights) IN
3.3V    ──── DHT22 VCC, MQ-135 VCC
GND     ──── All grounds
5V      ──── Relay Module VCC
```

### Relay Module to Fan

```
RELAY MODULE        5V USB FAN
─────────────       ──────────
COM ────────────────── +5V Power Supply
NO (Normally Open) ─── Fan + Wire
NC (Not used)          Fan - Wire ── GND Power Supply
```

**Note:** The relay acts as a switch. When activated, it connects COM to NO, completing the circuit.

## Configuration via Django Admin

Access Django Admin at `/admin/` to configure thresholds:

1. Go to **Core > Environment Settings**
2. Edit the singleton settings row
3. Configure:
   - `fan_temp_threshold`: Temperature that triggers fan ON
   - `fan_humidity_threshold`: Humidity that triggers fan ON
   - `fan_air_quality_threshold`: Air quality PPM that triggers fan ON
   - `humidifier_low_threshold`: Humidity below which humidifier turns ON
   - `humidifier_high_threshold`: Humidity above which humidifier turns OFF
   - `heater_low_threshold`: Temperature below which heater turns ON
   - `heater_high_threshold`: Temperature above which heater turns OFF
   - `hysteresis_margin`: Margin to prevent rapid ON/OFF cycling

## Best Practices

### 1. Avoiding Mode Conflicts

```python
# The system automatically handles conflicts:
# - If fan_auto = True: Backend controls fan based on sensors
# - If fan_auto = False: Fan follows dashboard switch (fan_on)

# Dashboard toggle changes:
# 1. User toggles "Automation" switch → Updates fan_auto in DB
# 2. If turning OFF automation: fan_on becomes the control value
# 3. If turning ON automation: sensor logic takes over
```

### 2. Manual Override

When you need immediate manual control:

1. Toggle "Automation" switch OFF in dashboard
2. Use the device ON/OFF switch
3. The system will NOT automatically change the state

### 3. Graceful Degradation

If WiFi/server is unreachable:

```cpp
// ESP32 behavior:
if (!wifiConnected || !serverReachable) {
    // Keep current relay states
    // Don't make changes without backend confirmation
    // Retry connection every 10 seconds
}
```

### 4. Logging and Debugging

All automation actions are logged in `AutomationLog`:

```python
# View automation history:
from core.models import AutomationLog

logs = AutomationLog.objects.order_by('-timestamp')[:20]
for log in logs:
    print(f"{log.timestamp}: {log.action} - {log.reason}")
```

## Testing the System

### 1. Test API Manually

```bash
# Test automation decision endpoint
curl -X POST http://localhost:8000/api/automation-decision/ \
  -H "Content-Type: application/json" \
  -d '{"temperature": 32, "humidity": 90, "device_id": "TEST"}'

# Expected response: fan should_be_on = true (temp > 30)
```

### 2. Test Mode Switching

```bash
# Set manual mode via environment API
curl -X POST http://localhost:8000/api/environment/ \
  -H "Content-Type: application/json" \
  -d '{"fan_auto": false, "fan_on": true}'

# Now fan is manually ON, sensor readings won't change it
```

### 3. Monitor Serial Output

Connect to ESP32 serial monitor (115200 baud) to see:
- Sensor readings every 5 seconds
- Automation decisions from backend
- Relay state changes

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Fan not turning on | Check: WiFi connection, relay wiring, threshold values |
| Fan cycling rapidly | Increase `hysteresis_margin` in admin settings |
| Manual mode not working | Ensure `fan_auto = false` in environment settings |
| Sensor readings incorrect | Re-calibrate DHT22, check wiring |
| ESP32 not connecting | Verify WiFi credentials, server URL, firewall |

## Summary

1. **Frontend (Dashboard)**: Users toggle Manual/Auto mode and ON/OFF switches
2. **Backend (Django)**: Receives sensor data, applies thresholds, stores settings
3. **Microcontroller (ESP32)**: Reads sensors, polls backend, controls relays

The automation logic lives in the **backend** - this allows:
- Easy threshold configuration via admin
- Consistent logic across all devices
- Centralized logging and monitoring
- No firmware update needed to change thresholds
