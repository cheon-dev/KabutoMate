/*
 * ESP32 DHT22 + MQ-135 + BH1750 + Fan + Misting + GROW LIGHT Control
 * for Mushroom Farming Dashboard
 * 
 * This sketch reads temperature/humidity from DHT22, air quality from MQ-135,
 * and light intensity (lux) from BH1750,
 * sends the data to your Django server, and controls fan, misting system, and
 * grow lights
 * via relays based on dashboard settings with AUTOMATIC and MANUAL mode support.
 * 
 * =============================================================================
 * AUTOMATION MODES (applies to Fan, Misting, and Grow Lights):
 * =============================================================================
 * - AUTOMATIC MODE: Actuators turn ON/OFF based on sensor readings vs thresholds
 *   - Fan: ON when temperature > threshold OR humidity > threshold OR air quality > threshold
 *   - Misting: ON when humidity < low threshold, OFF when humidity > high threshold
 *   - Mist: ON when humidity < low threshold, OFF when humidity > high threshold
 * - MANUAL MODE: Actuators respond only to dashboard switch (user control)
 * 
 * =============================================================================
 * HARDWARE REQUIREMENTS:
 * =============================================================================
 * - ESP32 Development Board
 * - DHT22 Temperature & Humidity Sensor
 * - MQ-135 Air Quality Sensor
 * - BH1750 Light Sensor (I2C)
 * - 6-Channel Relay Module (or individual relay modules)
 * - 5V USB Fan (connected via Relay 1)
 * - Two 24V DC Misting Actuators (connected via Relays 2 and 5)
 * - Mist fan (connected via Relay 6)
 * - Active buzzer (connected to GPIO 14)
 * - Relay 3 is unused (kept OFF)
 * - 24V DC 1A Power Supply for misting
 * - 5V Power Supply for fan
 * - Power supply for fan and grow light
 * 
 * =============================================================================
 * WIRING DIAGRAM:
 * =============================================================================
 * 
 * DHT22 SENSOR:
 * ┌─────────────┬────────────────┐
 * │ DHT22 Pin   │ ESP32 Pin      │
 * ├─────────────┼────────────────┤
 * │ VCC         │ 3.3V           │
 * │ GND         │ GND            │
 * │ DATA        │ GPIO 4         │
 * └─────────────┴────────────────┘
 * 
 * MQ-135 AIR QUALITY SENSOR:
 * ┌─────────────┬────────────────┐
 * │ MQ-135 Pin  │ ESP32 Pin      │
 * ├─────────────┼────────────────┤
 * │ VCC         │ 5V (VIN)       │
 * │ GND         │ GND            │
 * │ AOUT        │ GPIO 34        │
 * └─────────────┴────────────────┘
 * 
 * BH1750 LIGHT SENSOR (I2C):
 * ┌─────────────┬────────────────┐
 * │ BH1750 Pin  │ ESP32 Pin      │
 * ├─────────────┼────────────────┤
 * │ VCC         │ 3.3V           │
 * │ GND         │ GND            │
 * │ SDA         │ GPIO 21        │
 * │ SCL         │ GPIO 22        │
 * └─────────────┴────────────────┘
 * 
 * RELAY MODULE (6-Channel):
 * ┌─────────────┬────────────────┐
 * │ Relay Pin   │ ESP32 Pin      │
 * ├─────────────┼────────────────┤
 * │ VCC         │ 5V (VIN)       │
 * │ GND         │ GND            │
 * │ IN1 (Fan)   │ GPIO 26        │
 * │ IN2 (Mist 1)│ GPIO 27        │
 * │ IN3 (unused)│ GPIO 25        │
 * │ IN4 (Light) │ GPIO 33        │
 * │ IN5 (Mist 2)│ GPIO 32        │
 * │ IN6 (Mist Fan)│ GPIO 13      │
 * └─────────────┴────────────────┘
 *
 * ACTIVE BUZZER:
 * ┌──────────────┬────────────────┐
 * │ Buzzer Pin   │ ESP32 Pin      │
 * ├──────────────┼────────────────┤
 * │ Signal       │ GPIO 14        │
 * │ GND          │ GND            │
 * └──────────────┴────────────────┘
 * 
 * =============================================================================
 * RELAY 1 → FAN (5V USB Fan):
 * =============================================================================
 * 
 *     ┌─────────────────────────────────────────────────────┐
 *     │                    5V POWER SUPPLY                  │
 *     │                   (USB or adapter)                  │
 *     │          (+5V) ─────────┬─────────── (GND)          │
 *     └─────────────────────────│───────────────────────────┘
 *                               │
 *                    ┌──────────┴──────────┐
 *                    │                     │
 *              ┌─────▼─────┐               │
 *              │  RELAY 1  │               │
 *              │   COM ────┘               │
 *              │   NO ─────────┐           │
 *              │   NC          │           │
 *              └───────────────┤           │
 *                              │           │
 *                    ┌─────────▼─────────┐ │
 *                    │      5V FAN       │ │
 *                    │  RED (+) ─────────┤ │
 *                    │  BLACK (-) ───────┴─┘
 *                    └───────────────────┘
 * 
 * =============================================================================
 * RELAY 2 → MISTING ACTUATOR (24V DC):
 * =============================================================================
 * 
 * YOUR ACTUATOR WIRES:
 *   - RED wire   = Positive (+24V)
 *   - WHITE wire = Negative (GND)
 * 
 * ⚠️  NOTE: If misting doesn't work, swap the wires - polarity might be reversed!
 * 
 * ⚠️  SAFETY WARNING: 24V DC can cause burns and damage equipment!
 *     - Double-check polarity before powering on
 *     - Use proper gauge wire (18-20 AWG minimum for 1A)
 *     - Ensure relay is rated for 24V DC @ 1A or higher
 *     - Add a flyback diode across the actuator for protection
 * 
 *     ┌─────────────────────────────────────────────────────┐
 *     │                 24V DC POWER SUPPLY                 │
 *     │                    (1A minimum)                     │
 *     │          (+24V) ────────┬─────────── (GND)          │
 *     └─────────────────────────│───────────────────────────┘
 *                               │                     │
 *                    ┌──────────┴──────────┐          │
 *                    │                     │          │
 *              ┌─────▼─────┐               │          │
 *              │  RELAY 2  │               │          │
 *              │   COM ────┘               │          │
 *              │   NO ─────────┐           │          │
 *              │   NC          │           │          │
 *              └───────────────┤           │          │
 *                              │           │          │
 *                    ┌─────────▼─────────┐ │          │
 *                    │ MISTING ACTUATOR  │ │          │
 *                    │ RED (+) ──────────┤ │          │
 *                    │ WHITE (-) ────────┴─┴──────────┘
 *                    └───────────────────┘
 * 
 *                    OPTIONAL: Add 1N4007 flyback diode
 *                    (cathode to RED, anode to WHITE)
 * 
 * WIRING STEPS FOR MISTING (3 CONNECTIONS):
 * 1. 24V Power Supply (+) → Relay 2 COM terminal
 * 2. Relay 2 NO terminal  → Misting Actuator RED wire
 * 3. Misting Actuator WHITE wire → 24V Power Supply GND
 * 
 * When relay activates: COM connects to NO, completing the circuit
 * 
 * =============================================================================
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Wire.h>
#include <BH1750.h>
#include <ArduinoJson.h>  // Install via Library Manager: "ArduinoJson" by Benoit Blanchon
#include <string.h>

// =============================================================================
// CONFIGURATION
// =============================================================================

// WiFi credentials
const char* ssid = "Converge_2.4GHz_sH5Hfb";           // Replace with your WiFi network name
const char* password = "PQKZz6TT";   // Replace with your WiFi password

// Server settings
const char* serverUrl = "https://kabutomate-dan-f468.vercel.app/api/sensor-data/receive/";
const char* automationDecisionUrl = "https://kabutomate-dan-f468.vercel.app/api/automation-decision/";
const char* relayCommandUrl = "https://kabutomate-dan-f468.vercel.app/api/relay-command/";
const char* apiKey = "6h544gCB1x0hH8lStsH95_e-5Jwmum6GwLxA24F5j1I";
const char* deviceId = "ESP32_FARM_001";

// =============================================================================
// PIN DEFINITIONS
// =============================================================================

// DHT22 Sensor
#define DHTPIN 4          // GPIO pin connected to DHT22 data pin
#define DHTTYPE DHT22     // DHT 22 (AM2302)

// MQ-135 Air Quality Sensor
#define MQ135PIN 34       // GPIO pin connected to MQ-135 analog output (ADC1)

// BH1750 Light Sensor (I2C)
#define BH1750_SDA_PIN 21 // GPIO pin connected to BH1750 SDA
#define BH1750_SCL_PIN 22 // GPIO pin connected to BH1750 SCL

// Relay Control Pins
#define FAN_RELAY_PIN 26      // GPIO pin for Fan Relay (Relay 1)
#define MIST1_RELAY_PIN 27    // GPIO pin for Misting Relay 1 (Relay 2)
#define SPARE_RELAY_PIN 25    // Relay 3 - unused (heater removed), held OFF
#define LIGHT_RELAY_PIN 33    // GPIO pin for Grow Light Relay (Relay 4)
#define MIST2_RELAY_PIN 32    // GPIO pin for Misting Relay 2 (Relay 5)
#define MIST_FAN_RELAY_PIN 13 // GPIO pin for the fan that runs with misting (Relay 6)

// Relay behavior: Most relay modules are ACTIVE LOW (LOW = relay ON, HIGH = relay OFF)
// Set to true if your relay module activates on LOW signal
#define RELAY_ACTIVE_LOW false

// Active buzzer for environmental alerts
#define BUZZER_PIN 14

// =============================================================================
// SENSOR FRESHNESS
// =============================================================================
// Automation stops acting on sensor data that has gone stale, so a dead DHT22
// cannot leave the board driving relays from an old reading forever.
#define SENSOR_STALE_TIMEOUT 90000      // Ignore readings older than 90 seconds

// =============================================================================
// GLOBAL OBJECTS AND VARIABLES
// =============================================================================

DHT dht(DHTPIN, DHTTYPE);
BH1750 lightMeter;
WiFiClientSecure secureClient;
void connectWiFi();
void triggerEnvironmentalAlert();
void updateAlertBuzzer();

// Timing intervals (milliseconds)
const unsigned long sensorReadInterval = 5000;      // Read sensors locally every 5 seconds (no network cost)
const unsigned long sensorUploadInterval = 600000;  // POST a reading to Vercel every 10 minutes
const unsigned long automationPollInterval = 30000; // Poll automation + relay command every 30 seconds (Vercel CPU budget)
const unsigned long wifiReconnectInterval = 30000; // Retry hardcoded Wi-Fi after outages
unsigned long lastSensorReadTime = 0;
unsigned long lastSensorUploadTime = 0;
unsigned long lastGoodSensorRead = 0;
unsigned long lastAutomationPollTime = 0;
unsigned long lastWifiReconnectTime = 0;

// Control states - Fan
bool fanOn = false;
bool fanAutoMode = true;

// Control states - Misting
bool mistOn = false;
bool mistAutoMode = true;

// Control states - Grow Light
bool lightsOn = false;
bool lightsAutoMode = true;

// Alert buzzer state (three short beeps, handled without blocking the main loop)
bool alertBuzzerOn = false;
uint8_t alertBeepsRemaining = 0;
unsigned long nextAlertBuzzerChange = 0;

// Current sensor readings (stored for automation polling)
float currentTemperature = 0;
float currentHumidity = 0;
float currentAirQualityPPM = 0;
float currentLightLux = 0;
bool bh1750Initialized = false;
bool hasSensorData = false;   // True once the DHT22 has produced a valid reading

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=============================================");
  Serial.println("ESP32 DHT22 + MQ-135 + BH1750 + Fan + Mist + Light");
  Serial.println("Mushroom Farming Dashboard v2.0");
  Serial.println("=============================================\n");
  
  // Initialize DHT sensor
  dht.begin();
  Serial.println("✓ DHT22 sensor initialized");
  
  // Initialize MQ-135 sensor
  pinMode(MQ135PIN, INPUT);
  Serial.println("✓ MQ-135 air quality sensor initialized");

  // Initialize BH1750 light sensor on custom I2C pins
  Wire.begin(BH1750_SDA_PIN, BH1750_SCL_PIN);
  bh1750Initialized = lightMeter.begin();
  if (bh1750Initialized) {
    Serial.println("✓ BH1750 light sensor initialized (SDA=21, SCL=22)");
  } else {
    Serial.println("⚠️  BH1750 light sensor not detected - check wiring");
  }
  
  // Initialize relay pins
  pinMode(FAN_RELAY_PIN, OUTPUT);
  pinMode(MIST1_RELAY_PIN, OUTPUT);
  pinMode(SPARE_RELAY_PIN, OUTPUT);   // Relay 3 - unused, driven OFF
  pinMode(LIGHT_RELAY_PIN, OUTPUT);
  pinMode(MIST2_RELAY_PIN, OUTPUT);
  pinMode(MIST_FAN_RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("✓ Fan relay pin (GPIO 26) initialized");
  Serial.println("✓ Misting relay 1 pin (GPIO 27) initialized");
  Serial.println("✓ Grow light relay pin (GPIO 33) initialized");
  Serial.println("✓ Misting relay 2 pin (GPIO 32) initialized");
  Serial.println("✓ Misting fan relay pin (GPIO 13) initialized");
  
  // ===== RELAY HARDWARE TEST =====
  Serial.println("\n>>> TESTING ALL RELAYS - Listen for clicks! <<<");
  
  Serial.println("Test: Fan Relay ON");
  setRelay(FAN_RELAY_PIN, true);
  delay(1000);
  
  Serial.println("Test: Fan Relay OFF");
  setRelay(FAN_RELAY_PIN, false);
  delay(500);
  
  Serial.println("Test: Misting Relays and Mist Fan ON");
  setMistSystemState(true);
  delay(1000);
  
  Serial.println("Test: Misting Relays and Mist Fan OFF");
  setMistSystemState(false);
  delay(500);

  Serial.println("Test: Light Relay ON");
  setRelay(LIGHT_RELAY_PIN, true);
  delay(1000);

  Serial.println("Test: Light Relay OFF");
  setRelay(LIGHT_RELAY_PIN, false);
  delay(500);
  
  Serial.println(">>> RELAY TEST COMPLETE <<<\n");
  // ===== END TEST =====
  
  // Start with all actuators OFF
  setRelay(FAN_RELAY_PIN, false);
  setMistSystemState(false);
  setRelay(SPARE_RELAY_PIN, false);
  setRelay(LIGHT_RELAY_PIN, false);
  Serial.println("✓ All relays set to OFF");
  
  // ===== WIFI AUTO-CONNECT AT POWER ON =====
  WiFi.persistent(false);       // Wi-Fi credentials are defined in this firmware
  WiFi.setAutoReconnect(true);  // Automatically reconnect after any drop
  WiFi.setSleep(false);         // Disable modem sleep for a stable radio link
  secureClient.setInsecure();   // Hosted API uses HTTPS; certificate validation is omitted

  WiFi.mode(WIFI_STA);        // Station mode: connect to the router
  WiFi.begin(ssid, password);
  connectWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Hardcoded Wi-Fi is unavailable; the ESP32 will keep retrying.");
  }
  
  // Read sensors immediately on boot instead of waiting one full interval.
  // The first reading is also uploaded right away (one extra request per boot)
  // so the dashboard shows fresh data immediately.
  lastSensorReadTime = millis() - sensorReadInterval;
  lastSensorUploadTime = millis() - sensorUploadInterval;

  Serial.print("✓ Local sensor read every ");
  Serial.print(sensorReadInterval / 1000);
  Serial.println("s, upload to server every 10 min");
  Serial.println("✓ Dashboard manual control works even without sensor data\n");
}

// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  unsigned long currentTime = millis();

  updateAlertBuzzer();

  // Task 1: Read sensors locally every 5 s (free - no network traffic).
  // Upload to the server stays on the 10-minute interval below.
  if (currentTime - lastSensorReadTime >= sensorReadInterval) {
    lastSensorReadTime = currentTime;
    
    // Read sensor data
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();  // Celsius by default
    int airQualityRaw = analogRead(MQ135PIN);   // Read MQ-135 analog value (0-4095)
    float lightLux = currentLightLux;

    if (bh1750Initialized) {
      float luxReading = lightMeter.readLightLevel();
      if (!isnan(luxReading) && luxReading >= 0) {
        lightLux = luxReading;
      } else {
        static unsigned long lastBh1750Warning = 0;
        if (millis() - lastBh1750Warning > 30000) {
          lastBh1750Warning = millis();
          Serial.println("⚠️  BH1750 read failed, keeping last valid lux value");
        }
      }
    }
    
    // Convert air quality reading to PPM (simplified conversion)
    float airQualityPPM = map(airQualityRaw, 0, 4095, 0, 1000);
    
    // Check if readings are valid
    if (isnan(humidity) || isnan(temperature)) {
      static unsigned long lastDhtError = 0;
      if (millis() - lastDhtError > 30000) {
        lastDhtError = millis();
        Serial.println("❌ Failed to read from DHT sensor! Check wiring / pull-up resistor.");
      }
    } else {
      // Store current readings for automation polling
      currentTemperature = temperature;
      currentHumidity = humidity;
      currentAirQualityPPM = airQualityPPM;
      currentLightLux = lightLux;
      lastGoodSensorRead = currentTime;

      if (!hasSensorData) {
        hasSensorData = true;
        Serial.println("✓ Valid sensor data received - automation polling enabled");
      }
      
      // Keep the serial log readable: full report every 30 s, not every 5 s
      static unsigned long lastSensorPrint = 0;
      if (currentTime - lastSensorPrint >= 30000) {
        lastSensorPrint = currentTime;
        printSensorReadings(temperature, humidity, airQualityRaw, airQualityPPM, lightLux);
        checkGrowingConditions(temperature, humidity, airQualityPPM);
      }
      
      // Upload a reading to the server only every 10 minutes
      if (WiFi.status() == WL_CONNECTED) {
        if (currentTime - lastSensorUploadTime >= sensorUploadInterval) {
          lastSensorUploadTime = currentTime;
          sendSensorData(temperature, humidity, airQualityPPM, lightLux);
        }
      } else {
        Serial.println("❌ WiFi disconnected! Attempting to reconnect...");
        connectWiFi();
      }
    }
  }
  
  // Task 2: Poll automation decision + relay commands every 30 seconds
  if (currentTime - lastAutomationPollTime >= automationPollInterval) {
    lastAutomationPollTime = currentTime;
    pollAutomationDecision();
    pollRelayCommands();
  }

  if (WiFi.status() != WL_CONNECTED &&
      currentTime - lastWifiReconnectTime >= wifiReconnectInterval) {
    lastWifiReconnectTime = currentTime;
    connectWiFi();
  }
}

// =============================================================================
// RELAY CONTROL
// =============================================================================

void setRelay(int pin, bool on) {
  if (RELAY_ACTIVE_LOW) {
    // Active LOW: LOW = ON, HIGH = OFF
    digitalWrite(pin, on ? LOW : HIGH);
  } else {
    // Active HIGH: HIGH = ON, LOW = OFF
    digitalWrite(pin, on ? HIGH : LOW);
  }
}

// Both misting actuators and the dedicated mist fan always run together.
void setMistSystemState(bool on) {
  setRelay(MIST1_RELAY_PIN, on);
  setRelay(MIST2_RELAY_PIN, on);
  setRelay(MIST_FAN_RELAY_PIN, on);
}

void triggerEnvironmentalAlert() {
  // Do not restart the pattern if the same alert is already sounding.
  if (alertBuzzerOn || alertBeepsRemaining > 0) {
    return;
  }

  alertBeepsRemaining = 3;
  alertBuzzerOn = true;
  digitalWrite(BUZZER_PIN, HIGH);
  nextAlertBuzzerChange = millis() + 300;
}

void updateAlertBuzzer() {
  if (alertBeepsRemaining == 0 || millis() < nextAlertBuzzerChange) {
    return;
  }

  if (alertBuzzerOn) {
    digitalWrite(BUZZER_PIN, LOW);
    alertBuzzerOn = false;
    alertBeepsRemaining--;
    nextAlertBuzzerChange = millis() + 200;
  } else if (alertBeepsRemaining > 0) {
    digitalWrite(BUZZER_PIN, HIGH);
    alertBuzzerOn = true;
    nextAlertBuzzerChange = millis() + 300;
  }
}

// =============================================================================
// AUTOMATION DECISION POLLING
// =============================================================================
// This function sends current sensor readings to the backend and receives
// automation decisions for fan and misting.
//
// The backend decides based on:
// - AUTOMATIC MODE: Compare sensor values to thresholds
//   - Fan: ON when temp > threshold OR humidity > threshold OR air quality > threshold
//   - Mist: ON when humidity < low_threshold, OFF when humidity > high_threshold
// - MANUAL MODE: Use dashboard switch state (sensor data ignored)

void pollAutomationDecision() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️  WiFi not connected, skipping automation poll");
    return;
  }
  
  // Skip if we don't have a recent valid sensor reading
  if (!hasSensorData || millis() - lastGoodSensorRead > SENSOR_STALE_TIMEOUT) {
    static unsigned long lastNoDataWarn = 0;
    if (millis() - lastNoDataWarn > 30000) {
      lastNoDataWarn = millis();
      Serial.println("⚠️  No fresh sensor data, skipping automation poll");
    }
    return;
  }
  
  HTTPClient http;
  http.begin(secureClient, automationDecisionUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  // Build JSON payload with current sensor readings
  StaticJsonDocument<384> requestDoc;
  requestDoc["temperature"] = currentTemperature;
  requestDoc["humidity"] = currentHumidity;
  requestDoc["air_quality_ppm"] = (int)currentAirQualityPPM;
  requestDoc["light_lux"] = currentLightLux;
  requestDoc["device_id"] = deviceId;
  requestDoc["save_reading"] = false;  // Don't save again, we already sent via sendSensorData
  
  String requestBody;
  serializeJson(requestDoc, requestBody);
  
  // Send POST request with sensor data
  int httpCode = http.POST(requestBody);
  
  if (httpCode == 200) {
    String response = http.getString();
    
    // Parse JSON response
    StaticJsonDocument<1024> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      // ─────────────────────────────────────────────────────────────
      // PROCESS FAN CONTROL
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("fan")) {
        JsonObject fanControl = responseDoc["controls"]["fan"];
        
        bool shouldBeOn = fanControl["should_be_on"];
        const char* mode = fanControl["mode"];
        const char* reason = fanControl["reason"];
        
        // Update mode tracking
        fanAutoMode = (strcmp(mode, "automatic") == 0);
        
        // Only change relay if state differs
        if (fanOn != shouldBeOn) {
          fanOn = shouldBeOn;
          setRelay(FAN_RELAY_PIN, fanOn);
          
          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("🌀 FAN ");
          Serial.print(fanOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(fanAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.print("📝 Reason: ");
          Serial.println(reason);
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }
      
      // ─────────────────────────────────────────────────────────────
      // PROCESS MISTING/HUMIDIFIER CONTROL (NEW)
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("humidifier")) {
        JsonObject mistControl = responseDoc["controls"]["humidifier"];
        
        bool shouldBeOn = mistControl["should_be_on"];
        const char* mode = mistControl["mode"];
        const char* reason = mistControl["reason"];
        
        // Update mode tracking
        mistAutoMode = (strcmp(mode, "automatic") == 0);
        
        // Only change relay if state differs
        if (mistOn != shouldBeOn) {
          mistOn = shouldBeOn;
          setMistSystemState(mistOn);
          
          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("💧 MISTING ");
          Serial.print(mistOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(mistAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.print("📝 Reason: ");
          Serial.println(reason);
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }
      
      // Print thresholds for debugging (every 30 seconds)
      static unsigned long lastThresholdPrint = 0;
      if (millis() - lastThresholdPrint > 30000) {
        lastThresholdPrint = millis();
        if (responseDoc.containsKey("thresholds")) {
          JsonObject thresholds = responseDoc["thresholds"];
          Serial.println("\n📊 Current Automation Thresholds:");
          Serial.print("   Fan Temp Threshold: ");
          Serial.print((float)thresholds["fan_temp_threshold"]);
          Serial.println("°C");
          Serial.print("   Fan Humidity Threshold: ");
          Serial.print((float)thresholds["fan_humidity_threshold"]);
          Serial.println("%");
          Serial.print("   Mist Low Threshold: ");
          Serial.print((float)thresholds["humidifier_low_threshold"]);
          Serial.println("% (turns ON below this)");
          Serial.print("   Mist High Threshold: ");
          Serial.print((float)thresholds["humidifier_high_threshold"]);
          Serial.println("% (turns OFF above this)");
        }
      }
    } else {
      Serial.print("❌ JSON parse error: ");
      Serial.println(error.c_str());
    }
  } else if (httpCode > 0) {
    Serial.printf("⚠️  Automation poll returned: %d\n", httpCode);
  } else {
    Serial.printf("❌ Automation poll failed: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// =============================================================================
// RELAY COMMAND POLLING (MANUAL FALLBACK)
// =============================================================================
// Uses /api/relay-command/ to fetch the dashboard switch state directly.
// Devices whose automation toggle is OFF are applied here, so manual control
// keeps working even when sensor readings are unavailable and the
// automation-decision poll is skipped. Automatic devices are left alone so the
// two pollers can never fight over the same relay.
void pollRelayCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  http.begin(secureClient, relayCommandUrl);
  http.addHeader("X-API-Key", apiKey);

  int httpCode = http.GET();

  if (httpCode == 200) {
    String response = http.getString();

    StaticJsonDocument<512> relayDoc;
    DeserializationError error = deserializeJson(relayDoc, response);

    if (!error && relayDoc.containsKey("relays")) {
      JsonObject relays = relayDoc["relays"];
      JsonObject autoModes = relayDoc["auto_modes"];

      bool fanAuto = autoModes.containsKey("fan_auto") ? (bool)autoModes["fan_auto"] : true;
      bool humidifierAuto = autoModes.containsKey("humidifier_auto") ? (bool)autoModes["humidifier_auto"] : true;

      fanAutoMode = fanAuto;
      mistAutoMode = humidifierAuto;
      if (autoModes.containsKey("lights_auto")) {
        lightsAutoMode = autoModes["lights_auto"];
      }

      // ── FAN: manual fallback (works with no sensor data at all) ──
      if (!fanAuto && relays.containsKey("fan")) {
        bool shouldBeOn = relays["fan"];
        if (fanOn != shouldBeOn) {
          fanOn = shouldBeOn;
          setRelay(FAN_RELAY_PIN, fanOn);

          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("🌀 FAN ");
          Serial.print(fanOn ? "ON" : "OFF");
          Serial.println(" (MANUAL mode)");
          Serial.println("📝 Source: /api/relay-command/ (fallback)");
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }

      // ── MISTING: manual fallback ──
      if (!humidifierAuto && relays.containsKey("humidifier")) {
        bool shouldMistBeOn = relays["humidifier"];
        if (mistOn != shouldMistBeOn) {
          mistOn = shouldMistBeOn;
          setMistSystemState(mistOn);

          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("💧 MISTING ");
          Serial.print(mistOn ? "ON" : "OFF");
          Serial.println(" (MANUAL mode)");
          Serial.println("📝 Source: /api/relay-command/ (fallback)");
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }

      // ── GROW LIGHT: always driven by this endpoint ──
      if (relays.containsKey("lights")) {
        bool shouldBeOn = relays["lights"];
        if (lightsOn != shouldBeOn) {
          lightsOn = shouldBeOn;
          setRelay(LIGHT_RELAY_PIN, lightsOn);

          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("💡 GROW LIGHT ");
          Serial.print(lightsOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(lightsAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.println("📝 Source: /api/relay-command/");
          Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
      }
    }
  }

  http.end();
}

// =============================================================================
// DISPLAY FUNCTIONS
// =============================================================================

void printSensorReadings(float temperature, float humidity, int airQualityRaw, float airQualityPPM, float lightLux) {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("📊 Sensor Readings");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.print("🌡️  Temperature: ");
  Serial.print(temperature, 1);
  Serial.println(" °C");
  Serial.print("💧 Humidity: ");
  Serial.print(humidity, 1);
  Serial.println(" %");
  Serial.print("🌫️  Air Quality: ");
  Serial.print(airQualityRaw);
  Serial.print(" (raw) | ~");
  Serial.print(airQualityPPM, 0);
  Serial.println(" PPM");
  Serial.print("💡 Light Intensity: ");
  Serial.print(lightLux, 1);
  Serial.println(" lux");
  
  // Actuator status
  Serial.println("───────────────────────────────────");
  Serial.print("🌀 Fan: ");
  Serial.print(fanOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(fanAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
  
  Serial.print("💧 Misting: ");
  Serial.print(mistOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(mistAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
  
  Serial.print("💡 Grow Light: ");
  Serial.print(lightsOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(lightsAutoMode ? "AUTO" : "MANUAL");
  Serial.println(")");
}

// =============================================================================
// WIFI CONNECTION
// =============================================================================

void connectWiFi() {
  // Already connected - nothing to do
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  // Phase 1: Wait for the connection started in setup() (up to 30 seconds).
  // The long window handles slow routers, e.g. when power returns after an
  // outage and the ESP32 boots faster than the router.
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  // Phase 2: If still offline, force a fresh association and retry once more.
  // Calling disconnect() before begin() clears any half-open session so a
  // retry isn't blocked by the previous failed attempt.
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect();
    WiFi.begin(ssid, password);

    attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 60) {
      delay(500);
      Serial.print(".");
      attempts++;
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n❌ WiFi not connected yet - auto-reconnect will keep trying...");
  }
}

// =============================================================================
// SEND SENSOR DATA
// =============================================================================

void sendSensorData(float temperature, float humidity, float airQuality, float lightLux) {
  HTTPClient http;
  
  Serial.println("\n📡 Sending data to server...");
  
  http.begin(secureClient, serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  
  // Create JSON payload
  String jsonPayload = "{";
  jsonPayload += "\"temperature\":" + String(temperature, 1) + ",";
  jsonPayload += "\"humidity\":" + String(humidity, 1) + ",";
  jsonPayload += "\"air_quality_ppm\":" + String(airQuality, 0) + ",";
  jsonPayload += "\"light_lux\":" + String(lightLux, 1);
  jsonPayload += "}";
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    Serial.print("✓ Server Response: ");
    Serial.println(httpResponseCode);

    // The API sets this flag when it creates a new environmental alert/email.
    if (httpResponseCode == 201) {
      String response = http.getString();
      StaticJsonDocument<1536> responseDoc;
      DeserializationError error = deserializeJson(responseDoc, response);
      if (!error && responseDoc["data"]["environmental_alert"] == true) {
        Serial.println("⚠️  Environmental alert received - sounding buzzer");
        triggerEnvironmentalAlert();
      }
    }
  } else {
    Serial.print("❌ Error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  http.end();
}

// =============================================================================
// CONDITION ANALYSIS
// =============================================================================

void checkGrowingConditions(float temperature, float humidity, float airQuality) {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("🔍 Condition Analysis");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  
  // Temperature check
  if (temperature < 13) {
    Serial.println("🌡️  ⚠️  Temperature TOO LOW - below optimal range");
  } else if (temperature > 18) {
    Serial.println("🌡️  ⚠️  Temperature TOO HIGH - ventilation needed");
  } else {
    Serial.println("🌡️  ✓ Temperature is OPTIMAL (13-18°C)");
  }
  
  // Humidity check
  if (humidity < 80) {
    Serial.println("💧 ⚠️  Humidity TOO LOW - misting recommended");
  } else if (humidity > 95) {
    Serial.println("💧 ⚠️  Humidity TOO HIGH - risk of contamination");
  } else {
    Serial.println("💧 ✓ Humidity is OPTIMAL");
  }
  
  // Air Quality check
  if (airQuality < 400) {
    Serial.println("🌫️  ✓ Air Quality is GOOD");
  } else if (airQuality < 800) {
    Serial.println("🌫️  ⚠️  Air Quality is ACCEPTABLE - consider ventilation");
  } else { 
    Serial.println("🌫️  ⚠️  Air Quality is POOR - increase ventilation!");
  }
  
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
}
