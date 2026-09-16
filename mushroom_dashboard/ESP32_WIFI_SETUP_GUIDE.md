# ESP32 Wi-Fi Setup

The ESP32 no longer needs a Wi-Fi SSID or password compiled into the firmware.

## One-Time Setup

1. Set `ESP32_API_KEY` in the Django deployment environment.
2. Put the same value in the firmware `apiKey` constant.
3. Upload the firmware once.
4. Connect a phone or laptop to the ESP32 access point `KabutoMate-Setup`.
5. Open `http://192.168.4.1` and submit the Wi-Fi SSID and password.
6. Wait for the ESP32 to restart and connect to the dashboard.

The ESP32 stores the credentials in its NVS flash storage. The password is not
stored in the Django database as plain text; the server encrypts it before
storing it.

## Change Wi-Fi From The Admin Page

1. Open the administrator `Environmental Control` page.
2. In `ESP32 Wi-Fi Connection`, enter the new SSID and password.
3. Save the credentials while the ESP32 is still connected to the old network.
4. The ESP32 polls the server every 15 seconds, tests the new network, and
   saves it only after the connection succeeds.

If the new credentials fail, the ESP32 keeps the old credentials and retries
later. It does not require a firmware upload.

## Recovery

If the old network is unavailable, open the Serial Monitor at `115200` baud and
send `WIFI RESET`. The ESP32 clears its saved profile and starts the
`KabutoMate-Setup` access point again.

Use a long random value for `ESP32_API_KEY`. The Wi-Fi configuration endpoint
does not return credentials without that device key.
