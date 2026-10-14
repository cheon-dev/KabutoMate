# ESP32 #2 Water Refill Controller

This board is separate from `arduino/mushroom_fan_misting_controller.ino`.
The existing environmental controller must not be rewired or reflashed for this feature.

## Behavior

- The container float is installed at the desired refill level. Its active state means the container is low.
- The source-jug float is installed at the minimum safe source level. Its active state means the source is low or empty.
- The pump starts only when the container is low and the source is available.
- The pump stops when the container reaches its target, the source becomes low, the float readings are not stable, or the maximum runtime is reached.
- A timeout remains latched until the container reaches its target. Inspect the tubing, pump, and floats before resetting by cycling the controller.
- The local pump decision continues to work without Wi-Fi. Wi-Fi is only used to report status.

## Suggested Connections

Verify the actual ESP32 board pinout before wiring. These pins are defaults in the sketch and can be changed in one place.

| Part | Connection |
| --- | --- |
| Container float | GPIO 32 and GND |
| Source-jug float | GPIO 33 and GND |
| Pump driver input | GPIO 25 |
| ESP32 ground | Driver ground and sensor ground |
| Pump power | Separate supply sized for the pump |

The sketch uses `INPUT_PULLUP`, so each float is expected to close to GND when active. If the installed float behaves differently, change `FLOAT_ACTIVE_LOW` and verify the readings before connecting the pump.

Use a logic-level N-channel MOSFET or a properly rated DC relay module. For a MOSFET low-side driver:

1. Connect GPIO 25 to the gate through the driver circuit.
2. Connect the pump negative lead to the MOSFET drain and the supply negative to the source.
3. Connect the pump positive lead to the separate pump supply positive.
4. Tie the ESP32 ground to the pump-driver ground.
5. Add a flyback diode across a DC pump, with the cathode toward the pump positive lead.
6. Keep the pump supply current out of the ESP32 3.3 V pin.

Set `PUMP_ACTIVE_HIGH` to `false` for an active-low relay input. With the default setting, GPIO 25 is driven LOW during boot and whenever the pump must be off.

## Firmware Configuration

Edit these values locally in `arduino/water_refill_controller.ino` before flashing:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `WATER_REFILL_API_KEY`

Do not commit real Wi-Fi credentials or API keys. Configure the same key as the deployed `WATER_REFILL_API_KEY` environment variable. The device ID must remain `ESP32_WATER_REFILL_001` unless the server setting is changed too.

The sketch requires these Arduino libraries:

- ESP32 board support
- ArduinoJson

The deployment endpoint is:

`https://kabutomate-dan-f468.vercel.app/api/water-refill/report/`

The status request includes the `X-API-Key` header and sends JSON fields accepted by the Django endpoint:

- `device_id`
- `container_status`
- `source_status`
- `refill_state`
- `pump_on`
- `sensor_valid`
- `last_error`

## Commissioning Checklist

1. Flash the sketch with the pump driver disconnected.
2. Confirm both float states are stable in Serial Monitor for at least two seconds.
3. Confirm the pump output is OFF when either sensor is unstable or the source float is active.
4. Test the pump driver with the pump supply disconnected, then test with water present.
5. Confirm the container float stops the pump at the target level.
6. Confirm the source float stops the pump before the source jug runs dry.
7. Confirm a blocked line reaches `TIMEOUT` and leaves the pump OFF.
8. Set `WATER_REFILL_API_KEY` in deployment and verify the admin Environmental Control page shows the controller as ONLINE.

The backend reports the controller as OFFLINE after the configured reporting interval, currently five minutes by default.
