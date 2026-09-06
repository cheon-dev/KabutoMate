/*
 * ESP32 DHT22 + MQ-135 + BH1750 + Fan + Misting + HEATER + GROW LIGHT Control
 * for Mushroom Farming Dashboard
 * 
 * This sketch reads temperature/humidity from DHT22, air quality from MQ-135,
 * and light intensity (lux) from BH1750,
 * sends the data to your Django server, and controls fan, misting system, heater,
 * and grow lights
 * via relays based on dashboard settings with AUTOMATIC and MANUAL mode support.
 * 
 * =============================================================================
 * AUTOMATION MODES (applies to Fan, Misting, Heater, and Grow Lights):
 * =============================================================================
 * - AUTOMATIC MODE: Actuators turn ON/OFF based on sensor readings vs thresholds
 *   - Fan: ON when temperature > threshold OR humidity > threshold OR air quality > threshold
 *   - Misting: ON when humidity < low threshold, OFF when humidity > high threshold
 *   - Heater: ON when temperature < low threshold, OFF when temperature > high threshold
 * - MANUAL MODE: Actuators respond only to dashboard switch (user control)
 * 
 * =============================================================================
 * HARDWARE REQUIREMENTS:
 * =============================================================================
 * - ESP32 Development Board
 * - DHT22 Temperature & Humidity Sensor
 * - MQ-135 Air Quality Sensor
 * - BH1750 Light Sensor (I2C)
 * - 4-Channel Relay Module (or four 1-channel modules)
 * - 5V USB Fan (connected via Relay 1)
 * - 24V DC Misting Actuator (connected via Relay 2)
 * - Heater (connected via Relay 3) - See HEATER_INTEGRATION_GUIDE.md
 * - 24V DC 1A Power Supply for misting
 * - 5V Power Supply for fan
 * - Power supply for heater (AC or DC depending on heater type)
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
 * RELAY MODULE (4-Channel):
 * ┌─────────────┬────────────────┐
 * │ Relay Pin   │ ESP32 Pin      │
 * ├─────────────┼────────────────┤
 * │ VCC         │ 5V (VIN)       │
 * │ GND         │ GND            │
 * │ IN1 (Fan)   │ GPIO 26        │
 * │ IN2 (Mist)  │ GPIO 27        │
 * │ IN3 (Heat)  │ GPIO 25        │
 * │ IN4 (Light) │ GPIO 33        │
 * └─────────────┴────────────────┘
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

// =============================================================================
// CONFIGURATION
// =============================================================================

// WiFi credentials
const char* ssid = "Hi2";           // Replace with your WiFi network name
const char* password = "kir111104";          // Replace with your WiFi password

// Server settings
const char* serverUrl = "https://kabutomate-dan-f468.vercel.app/api/sensor-data/receive/";
const char* automationDecisionUrl = "https://kabutomate-dan-f468.vercel.app/api/automation-decision/";
const char* relayCommandUrl = "https://kabutomate-dan-f468.vercel.app/api/relay-command/";
const char* apiKey = "YOUR_API_KEY";  // Optional: Add API key for authentication
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
#define MIST_RELAY_PIN 27     // GPIO pin for Misting Relay (Relay 2)
#define HEATER_RELAY_PIN 25   // GPIO pin for Heater Relay (Relay 3)
#define LIGHT_RELAY_PIN 33    // GPIO pin for Grow Light Relay (Relay 4)

// Relay behavior: Most relay modules are ACTIVE LOW (LOW = relay ON, HIGH = relay OFF)
// Set to true if your relay module activates on LOW signal
#define RELAY_ACTIVE_LOW false

// =============================================================================
// HEATER SAFETY LIMITS
// =============================================================================
#define MAX_SAFE_TEMPERATURE 30.0       // Soft limit: Auto mode won't turn heater ON above this
#define ABSOLUTE_MAX_TEMPERATURE 50.0   // Hard limit: Even manual mode can't exceed this (fire safety)
#define MIN_HEATER_INTERVAL 30000       // Minimum 30 seconds between heater state changes
#define WATCHDOG_TIMEOUT 60000          // Turn off heater if no server response for 60 seconds
#define MANUAL_TEST_TIMEOUT 60000       // Auto-disable manual test mode after 60 seconds

// =============================================================================
// GLOBAL OBJECTS AND VARIABLES
// =============================================================================

DHT dht(DHTPIN, DHTTYPE);
BH1750 lightMeter;
WiFiClientSecure secureClient;

// Timing intervals (milliseconds)
const unsigned long sensorReadInterval = 5000;    // Read/send sensor data every 5 seconds
const unsigned long automationPollInterval = 3000; // Poll automation decision every 3 seconds
unsigned long lastSensorReadTime = 0;
unsigned long lastAutomationPollTime = 0;
unsigned long lastServerResponse = 0;        // Watchdog timer for heater safety
unsigned long lastHeaterStateChange = 0;      // Prevent rapid heater cycling

// Control states - Fan
bool fanOn = false;
bool fanAutoMode = true;

// Control states - Misting
bool mistOn = false;
bool mistAutoMode = true;

// Control states - Heater
bool heaterOn = false;
bool heaterAutoMode = true;
bool heaterManualTestMode = false;    // For hardware testing via Serial
unsigned long manualTestModeStart = 0; // When manual test mode was enabled

// Control states - Grow Light
bool lightsOn = false;
bool lightsAutoMode = true;

// Current sensor readings (stored for automation polling)
float currentTemperature = 0;
float currentHumidity = 0;
float currentAirQualityPPM = 0;
float currentLightLux = 0;
bool bh1750Initialized = false;

// =============================================================================
// SETUP
// =============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=============================================");
  Serial.println("ESP32 DHT22 + MQ-135 + Fan + Mist + HEATER + LIGHT");
  Serial.println("Mushroom Farming Dashboard v2.0");
  Serial.println("WITH HEATER AUTOMATION SUPPORT");
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
  pinMode(MIST_RELAY_PIN, OUTPUT);
  pinMode(HEATER_RELAY_PIN, OUTPUT);
  pinMode(LIGHT_RELAY_PIN, OUTPUT);
  Serial.println("✓ Fan relay pin (GPIO 26) initialized");
  Serial.println("✓ Misting relay pin (GPIO 27) initialized");
  Serial.println("✓ Heater relay pin (GPIO 25) initialized");
  Serial.println("✓ Grow light relay pin (GPIO 33) initialized");
  
  // ===== RELAY HARDWARE TEST =====
  Serial.println("\n>>> TESTING ALL RELAYS - Listen for clicks! <<<");
  
  Serial.println("Test: Fan Relay ON");
  setRelay(FAN_RELAY_PIN, true);
  delay(1000);
  
  Serial.println("Test: Fan Relay OFF");
  setRelay(FAN_RELAY_PIN, false);
  delay(500);
  
  Serial.println("Test: Misting Relay ON");
  setRelay(MIST_RELAY_PIN, true);
  delay(1000);
  
  Serial.println("Test: Misting Relay OFF");
  setRelay(MIST_RELAY_PIN, false);
  delay(500);
  
  Serial.println("Test: Heater Relay ON");
  setRelay(HEATER_RELAY_PIN, true);
  delay(1000);
  
  Serial.println("Test: Heater Relay OFF");
  setRelay(HEATER_RELAY_PIN, false);
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
  setRelay(MIST_RELAY_PIN, false);
  setRelay(HEATER_RELAY_PIN, false);
  setRelay(LIGHT_RELAY_PIN, false);
  Serial.println("✓ All relays set to OFF");
  
  // ===== WIFI AUTO-CONNECT AT POWER ON =====
  // Runs immediately on boot - no computer or Serial Monitor needed.
  WiFi.mode(WIFI_STA);          // Station mode: connect to the router
  WiFi.persistent(false);       // Don't rewrite credentials to flash
  WiFi.setAutoReconnect(true);  // Automatically reconnect after any drop
  WiFi.setSleep(false);         // Disable modem sleep for a stable radio link
  secureClient.setInsecure();   // Hosted API uses HTTPS; certificate validation is omitted
  
  // Connect to WiFi
  connectWiFi();
  
  // Initialize watchdog timer
  lastServerResponse = millis();
  
  // Print help for heater testing commands
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("💡 HEATER MANUAL TEST COMMANDS:");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("  Type 'HELP' in Serial Monitor");
  Serial.println("  for heater testing commands");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
}

// =============================================================================
// MAIN LOOP
// =============================================================================

void loop() {
  unsigned long currentTime = millis();
  
  // Task 0: Process Serial commands for manual heater testing
  processSerialCommands();
  
  // Task 0.5: Auto-disable manual test mode after timeout (safety feature)
  if (heaterManualTestMode && (currentTime - manualTestModeStart >= MANUAL_TEST_TIMEOUT)) {
    Serial.println("\n⏰ MANUAL TEST MODE TIMEOUT - Returning to automatic mode");
    heaterManualTestMode = false;
    setHeaterStateWithOverride(false, "Test mode timeout - auto safety shutoff", true);
  }
  
  // Task 1: Read and send sensor data every 5 seconds
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
      Serial.println("❌ Failed to read from DHT sensor!");
    } else {
      // Store current readings for automation polling
      currentTemperature = temperature;
      currentHumidity = humidity;
      currentAirQualityPPM = airQualityPPM;
      currentLightLux = lightLux;
      
      // Display readings
      printSensorReadings(temperature, humidity, airQualityRaw, airQualityPPM, lightLux);
      
      // Check mushroom growing conditions
      checkGrowingConditions(temperature, humidity, airQualityPPM);
      
      // HEATER SAFETY CHECK: Force heater OFF if temperature exceeds absolute limit
      // This cannot be bypassed even in manual test mode
      if (temperature >= ABSOLUTE_MAX_TEMPERATURE && heaterOn) {
        Serial.println("\n🚨🚨🚨 ABSOLUTE SAFETY CUTOFF 🚨🚨🚨");
        Serial.println("Temperature exceeds absolute maximum - FORCING HEATER OFF!");
        heaterManualTestMode = false; // Exit test mode for safety
        setHeaterStateWithOverride(false, "ABSOLUTE safety cutoff - max temperature exceeded", true);
      }
      // Soft safety check for automatic mode (not test mode)
      else if (temperature >= MAX_SAFE_TEMPERATURE && heaterOn && !heaterManualTestMode) {
        Serial.println("\n🚨 SAFETY CUTOFF: Temperature too high, forcing heater OFF!");
        setHeaterState(false, "Safety cutoff - max temperature reached");
      }
      
      // Send data to server
      if (WiFi.status() == WL_CONNECTED) {
        sendSensorData(temperature, humidity, airQualityPPM, lightLux);
      } else {
        Serial.println("❌ WiFi disconnected! Attempting to reconnect...");
        connectWiFi();
      }
    }
  }
  
  // Task 2: Poll automation decision every 3 seconds
  if (currentTime - lastAutomationPollTime >= automationPollInterval) {
    lastAutomationPollTime = currentTime;
    pollAutomationDecision();
    pollRelayCommandLights();
  }
  
  // Task 3: Watchdog - turn off heater if no server response (safety feature)
  // Does not apply in manual test mode (allows testing without server)
  if (!heaterManualTestMode && currentTime - lastServerResponse >= WATCHDOG_TIMEOUT && heaterOn) {
    Serial.println("\n🚨 WATCHDOG: No server response, turning heater OFF for safety!");
    setHeaterState(false, "Watchdog timeout - no server response");
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

// =============================================================================
// HEATER CONTROL WITH SAFETY FEATURES
// =============================================================================

void setHeaterState(bool newState, const char* reason) {
  setHeaterStateWithOverride(newState, reason, false);
}

// Overloaded function that allows bypassing soft safety limit (for manual testing)
void setHeaterStateWithOverride(bool newState, const char* reason, bool bypassSoftLimit) {
  unsigned long currentTime = millis();
  
  // ABSOLUTE SAFETY: Never exceed ABSOLUTE_MAX_TEMPERATURE (fire prevention)
  // This cannot be bypassed even in manual test mode
  if (newState && currentTemperature >= ABSOLUTE_MAX_TEMPERATURE) {
    Serial.println("\n🚨🚨🚨 ABSOLUTE SAFETY LIMIT 🚨🚨🚨");
    Serial.print("❌ Heater ON BLOCKED - Temperature ");
    Serial.print(currentTemperature);
    Serial.print("°C exceeds absolute max ");
    Serial.print(ABSOLUTE_MAX_TEMPERATURE);
    Serial.println("°C");
    Serial.println("This limit cannot be bypassed for fire safety!");
    return;
  }
  
  // Soft safety limit - only applies in automatic mode (can be bypassed in manual/test mode)
  if (!bypassSoftLimit && newState && currentTemperature >= MAX_SAFE_TEMPERATURE) {
    if (heaterAutoMode && !heaterManualTestMode) {
      Serial.println("⚠️  Heater ON blocked - temperature at or above safety limit (AUTO mode)");
      Serial.println("💡 Tip: Use 'HEATER TEST ON' in Serial Monitor to bypass for testing");
      return;
    }
  }
  
  // Prevent rapid cycling (minimum interval between state changes) - can be bypassed in test mode
  if (!heaterManualTestMode && currentTime - lastHeaterStateChange < MIN_HEATER_INTERVAL && lastHeaterStateChange != 0) {
    Serial.println("⚠️  Heater state change blocked - minimum interval not met");
    Serial.println("💡 Tip: Use 'HEATER TEST ON/OFF' to bypass timing restriction");
    return;
  }
  
  // Apply the state change
  if (heaterOn != newState) {
    heaterOn = newState;
    setRelay(HEATER_RELAY_PIN, heaterOn);
    lastHeaterStateChange = currentTime;
    
    Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.print("🔥 HEATER ");
    Serial.print(heaterOn ? "ON" : "OFF");
    Serial.print(" (");
    if (heaterManualTestMode) {
      Serial.print("TEST MODE");
    } else {
      Serial.print(heaterAutoMode ? "AUTO" : "MANUAL");
    }
    Serial.println(")");
    Serial.print("📝 Reason: ");
    Serial.println(reason);
    Serial.print("🌡️  Current Temp: ");
    Serial.print(currentTemperature);
    Serial.println("°C");
    if (heaterManualTestMode) {
      Serial.println("⚠️  TEST MODE ACTIVE - Will auto-disable in 60 seconds");
    }
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  }
}

// =============================================================================
// SERIAL COMMAND PROCESSING
// =============================================================================
// Commands for testing heater hardware via Serial Monitor:
//   HEATER TEST ON   - Force heater ON (bypasses soft safety limit)
//   HEATER TEST OFF  - Force heater OFF
//   HEATER AUTO      - Return to automatic mode
//   HEATER STATUS    - Show current heater status
//   HELP             - Show available commands

void processSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();
    
    if (command == "HEATER TEST ON") {
      Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      Serial.println("🔧 HEATER TEST MODE ACTIVATED");
      Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      heaterManualTestMode = true;
      manualTestModeStart = millis();
      setHeaterStateWithOverride(true, "Manual test via Serial", true);
      
    } else if (command == "HEATER TEST OFF") {
      Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      Serial.println("🔧 HEATER TEST - TURNING OFF");
      Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      heaterManualTestMode = true;
      manualTestModeStart = millis();
      setHeaterStateWithOverride(false, "Manual test via Serial", true);
      
    } else if (command == "HEATER AUTO") {
      Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      Serial.println("🔄 RETURNING TO AUTOMATIC MODE");
      Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      heaterManualTestMode = false;
      // Turn heater off when returning to auto mode for safety
      setHeaterStateWithOverride(false, "Returning to auto mode", true);
      
    } else if (command == "HEATER STATUS") {
      printHeaterStatus();
      
    } else if (command == "HELP" || command == "?") {
      printHelpCommands();
      
    } else if (command.length() > 0) {
      Serial.print("❓ Unknown command: ");
      Serial.println(command);
      Serial.println("Type 'HELP' for available commands");
    }
  }
}

void printHeaterStatus() {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("📊 HEATER STATUS");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.print("   State: ");
  Serial.println(heaterOn ? "ON 🔥" : "OFF");
  Serial.print("   Mode: ");
  if (heaterManualTestMode) {
    Serial.println("TEST MODE ⚠️");
  } else if (heaterAutoMode) {
    Serial.println("AUTOMATIC");
  } else {
    Serial.println("MANUAL (Dashboard)");
  }
  Serial.print("   Current Temperature: ");
  Serial.print(currentTemperature);
  Serial.println("°C");
  Serial.print("   Soft Safety Limit: ");
  Serial.print(MAX_SAFE_TEMPERATURE);
  Serial.println("°C");
  Serial.print("   Absolute Safety Limit: ");
  Serial.print(ABSOLUTE_MAX_TEMPERATURE);
  Serial.println("°C");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
}

void printHelpCommands() {
  Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("📋 AVAILABLE SERIAL COMMANDS");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println("  HEATER TEST ON  - Force heater ON (test mode)");
  Serial.println("  HEATER TEST OFF - Force heater OFF (test mode)");
  Serial.println("  HEATER AUTO     - Return to automatic mode");
  Serial.println("  HEATER STATUS   - Show heater status");
  Serial.println("  HELP            - Show this help");
  Serial.println("");
  Serial.println("⚠️  Test mode auto-disables after 60 seconds");
  Serial.println("⚠️  Absolute safety limit (50°C) cannot be bypassed");
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
}

// =============================================================================
// AUTOMATION DECISION POLLING
// =============================================================================
// This function sends current sensor readings to the backend and receives
// automation decisions for fan, misting, and heater.
//
// The backend decides based on:
// - AUTOMATIC MODE: Compare sensor values to thresholds
//   - Fan: ON when temp > threshold OR humidity > threshold OR air quality > threshold
//   - Mist: ON when humidity < low_threshold, OFF when humidity > high_threshold
//   - Heater: ON when temp < low_threshold, OFF when temp > high_threshold
// - MANUAL MODE: Use dashboard switch state (sensor data ignored)

void pollAutomationDecision() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️  WiFi not connected, skipping automation poll");
    return;
  }
  
  // Skip if we don't have valid sensor readings yet
  if (currentTemperature == 0 && currentHumidity == 0) {
    Serial.println("⚠️  No sensor data yet, skipping automation poll");
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
          setRelay(MIST_RELAY_PIN, mistOn);
          
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
      
      // ─────────────────────────────────────────────────────────────
      // PROCESS HEATER CONTROL
      // ─────────────────────────────────────────────────────────────
      if (responseDoc.containsKey("controls") && responseDoc["controls"].containsKey("heater")) {
        JsonObject heaterControl = responseDoc["controls"]["heater"];
        
        bool shouldBeOn = heaterControl["should_be_on"];
        const char* mode = heaterControl["mode"];
        const char* reason = heaterControl["reason"];
        
        // Update mode tracking
        heaterAutoMode = (strcmp(mode, "automatic") == 0);
        bool isManualMode = (strcmp(mode, "manual") == 0);
        
        // Use safety-checked heater control function
        // In manual mode from dashboard, bypass soft limit (but absolute limit still applies)
        if (heaterOn != shouldBeOn) {
          if (isManualMode) {
            // Manual dashboard control - bypass soft safety limit
            setHeaterStateWithOverride(shouldBeOn, reason, true);
          } else {
            // Automatic mode - enforce all safety limits
            setHeaterState(shouldBeOn, reason);
          }
        }
      }
      
      // Update server response time for watchdog
      lastServerResponse = millis();
      
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
          Serial.print("   Heater Low Threshold: ");
          Serial.print((float)thresholds["heater_low_threshold"]);
          Serial.println("°C (turns ON below this)");
          Serial.print("   Heater High Threshold: ");
          Serial.print((float)thresholds["heater_high_threshold"]);
          Serial.println("°C (turns OFF above this)");
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
// RELAY COMMAND POLLING (GROW LIGHT + HUMIDIFIER FALLBACK)
// =============================================================================
// Uses /api/relay-command/ to fetch relay states that should always be honored.
// This keeps manual dashboard control working even when sensor readings are
// unavailable and automation-decision polling is skipped.
void pollRelayCommandLights() {
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

      // Keep grow light behavior driven by relay-command payload.
      if (relays.containsKey("lights")) {
        bool shouldBeOn = relays["lights"];

        if (relayDoc.containsKey("auto_modes") && relayDoc["auto_modes"].containsKey("lights_auto")) {
          lightsAutoMode = relayDoc["auto_modes"]["lights_auto"];
        }

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

      // Fallback path for humidifier so manual mode still works without DHT22 updates.
      if (relays.containsKey("humidifier")) {
        bool shouldMistBeOn = relays["humidifier"];

        if (relayDoc.containsKey("auto_modes") && relayDoc["auto_modes"].containsKey("humidifier_auto")) {
          mistAutoMode = relayDoc["auto_modes"]["humidifier_auto"];
        }

        if (mistOn != shouldMistBeOn) {
          mistOn = shouldMistBeOn;
          setRelay(MIST_RELAY_PIN, mistOn);

          Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
          Serial.print("💧 MISTING ");
          Serial.print(mistOn ? "ON" : "OFF");
          Serial.print(" (");
          Serial.print(mistAutoMode ? "AUTO" : "MANUAL");
          Serial.println(" mode)");
          Serial.println("📝 Source: /api/relay-command/ (fallback)");
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
  
  Serial.print("🔥 Heater: ");
  Serial.print(heaterOn ? "ON" : "OFF");
  Serial.print(" (");
  Serial.print(heaterAutoMode ? "AUTO" : "MANUAL");
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
    Serial.println("🌡️  ⚠️  Temperature TOO LOW - heater needed");
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
