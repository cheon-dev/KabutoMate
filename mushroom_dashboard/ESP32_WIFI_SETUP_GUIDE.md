# ESP32 Wi-Fi Setup

The ESP32 uses hardcoded Wi-Fi credentials in the Arduino firmware.

## Configure Wi-Fi

1. Open `arduino/mushroom_fan_misting_controller.ino`.
2. Set the `wifiSsid` and `wifiPassword` constants near the server settings.
3. Set `ESP32_API_KEY` in the Django deployment environment and put the same
   value in the firmware `apiKey` constant.
4. Upload the firmware to the ESP32.

The network must provide a 2.4 GHz Wi-Fi connection. A phone's 4G/5G service
provides internet access, but the hotspot itself must be configured for 2.4 GHz.

The Wi-Fi credentials are not managed or stored by the dashboard. Changing the
network requires editing the firmware constants and uploading it again.
