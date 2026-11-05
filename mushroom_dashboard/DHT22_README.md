# 🍄 DHT22 Sensor Integration - Complete Package
## Mushroom Farming Dashboard - Real-Time Environmental Monitoring

---

## 📦 What's Included

This integration package provides everything you need to connect a DHT22 temperature and humidity sensor to your Django mushroom farming dashboard using an ESP32 microcontroller.

### Files Created:

1. **arduino_esp32_dht22.ino**
   - Complete Arduino sketch for ESP32
   - Reads DHT22 sensor data
   - Sends data to Django via HTTP POST
   - Includes condition checking and alerts
   - Serial debug output

2. **core/sensor_api.py**
   - Django API views for receiving sensor data
   - Three endpoints: POST data, GET latest, GET statistics
   - Automatic alert creation for critical conditions
   - API key authentication support

3. **core/models.py** (Enhanced)
   - Updated SensorReading model
   - Added device_id field
   - Made co2_ppm optional
   - Added helper properties for condition checking

4. **core/urls.py** (Updated)
   - Added routes for sensor API endpoints
   - Imported sensor_api module

5. **core/migrations/0016_dht22_sensor_integration.py**
   - Django migration file
   - Updates database schema for enhanced sensor model

6. **database_schema_dht22.sql**
   - MySQL schema for sensor readings table
   - Includes indexes, views, and useful queries
   - Optional sensor device registry table

7. **DHT22_INTEGRATION_GUIDE.md**
   - Comprehensive setup guide
   - Hardware wiring instructions
   - Arduino IDE setup steps
   - Django configuration
   - Testing procedures
   - Troubleshooting guide
   - API documentation

8. **QUICK_REFERENCE.txt**
   - Quick reference card
   - Wiring diagram
   - Configuration checklist
   - Common commands
   - Troubleshooting tips

9. **test_dht22_integration.py**
   - Python test script
   - Validates entire integration
   - Tests all API endpoints
   - Checks database connectivity

10. **ARDUINO_LIBRARIES.txt**
    - List of required Arduino libraries
    - Installation instructions

---

## 🚀 Quick Start Guide

### Hardware Setup (5 minutes)
1. Connect DHT22 to ESP32:
   - VCC → 3.3V
   - GND → GND
   - DATA → GPIO 4

### Arduino Setup (10 minutes)
1. Install ESP32 board support in Arduino IDE
2. Install DHT libraries (Adafruit DHT + Unified Sensor)
3. Open `arduino_esp32_dht22.ino`
4. Update WiFi credentials and server URL
5. Upload to ESP32

### Django Setup (5 minutes)
1. Run migration: `python manage.py migrate`
2. Update API key in `core/sensor_api.py`
3. Add your IP to ALLOWED_HOSTS in settings.py
4. Start server: `python manage.py runserver 0.0.0.0:8000`

### Sensor Simulation
The admin dashboard automatically generates simulated sensor readings when
there has been no physical sensor reading for five minutes. It refreshes the
simulated values gradually while the dashboard is open, and labels the sensor
status `Simulated`. Real sensor readings take precedence as soon as they resume.

On the Environmental Control page, tap the page title five times within two
seconds to open the simulated sensor range settings. Configure temperature,
humidity, and air-quality minimums and maximums there; simulated readings stay
inside those ranges. Run `python manage.py migrate` once after updating the
application to create the settings table.

The optional `python manage.py run_simulator` command is still available for
continuous simulated data independent of dashboard visits.

### Testing (2 minutes)
1. Open Serial Monitor in Arduino IDE
2. Watch for successful data transmission
3. Run: `python test_dht22_integration.py`
4. Check Django admin for new sensor readings

**Total setup time: ~25 minutes**

---

## 🌟 Key Features

### Hardware
- ✅ ESP32 WiFi connectivity
- ✅ DHT22 temperature & humidity sensor
- ✅ Automatic reconnection on WiFi drop
- ✅ Configurable reading intervals (default: 60 seconds)
- ✅ Serial debug output

### Backend API
- ✅ RESTful API endpoints
- ✅ JSON request/response format
- ✅ API key authentication
- ✅ Automatic condition checking
- ✅ Critical alert notifications
- ✅ Multiple device support (via device_id)

### Data Management
- ✅ Timestamped readings
- ✅ Decimal precision for accuracy
- ✅ Database indexes for performance
- ✅ Historical data storage
- ✅ Statistics calculations (min, max, avg)

### Mushroom Growing Intelligence
- ✅ Optimal range detection (13-18°C, 80-95% humidity)
- ✅ Three-level status system (OPTIMAL/ACCEPTABLE/CRITICAL)
- ✅ Automatic notifications for critical conditions
- ✅ Real-time condition analysis

---

## 📊 API Endpoints

| Method | Endpoint                    | Purpose                    |
|--------|----------------------------|----------------------------|
| POST   | /api/sensor-data/          | Receive sensor data        |
| GET    | /api/sensor-data/latest/   | Get recent readings        |
| GET    | /api/sensor-data/stats/    | Get statistics             |

---

## 🎯 Sensor Data Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  DHT22   │ ─────→  │  ESP32   │ ─────→  │  Django  │
│  Sensor  │ Digital  │ WiFi MCU │  HTTP   │  Server  │
└──────────┘         └──────────┘         └──────────┘
     │                     │                     │
     │                     │                     ↓
Temperature &         Sends JSON           ┌──────────┐
Humidity Data         every 60s            │ Database │
                                           └──────────┘
                                                 │
                                                 ↓
                                           ┌──────────┐
                                           │Dashboard │
                                           └──────────┘
```

---

## 🌡️ Growing Conditions

The system monitors and classifies conditions:

### OPTIMAL ✅
- Temperature: 13-18°C (55-64°F)
- Humidity: 80-95%

### ACCEPTABLE ⚠️
- Temperature: 10-21°C (50-70°F)
- Humidity: 70-98%

### CRITICAL 🚨
- Temperature: <10°C or >21°C
- Humidity: <70% or >98%

Notifications are automatically created for CRITICAL conditions.

---

## 🔧 Customization Options

### Change Reading Interval
In Arduino sketch:
```cpp
const unsigned long readingInterval = 30000;  // 30 seconds
```

### Change GPIO Pin
In Arduino sketch:
```cpp
#define DHTPIN 5  // Use GPIO 5 instead
```

### Change Optimal Ranges
In `core/models.py`, modify properties:
```python
@property
def is_temperature_optimal(self):
    return 15 <= self.temperature <= 20  # Custom range
```

### Add More Sensors
Just use different device_id values:
```json
{
  "temperature": 16.5,
  "humidity": 85.2,
  "device_id": "ESP32_ROOM_2"
}
```

---

## 📈 Data Retention

By default, all sensor data is kept indefinitely. To manage database size:

### Automatic Cleanup (Recommended)
Add a Django management command to delete old data:
```python
# Delete readings older than 30 days
SensorReading.objects.filter(
    timestamp__lt=timezone.now() - timedelta(days=30)
).delete()
```

Run via cron job or task scheduler.

---

## 🔐 Security Considerations

### Development
- API key is optional
- HTTP is acceptable
- Server can be local network only

### Production
1. **Enable API key authentication**
   - Set strong API key in `sensor_api.py`
   - Use same key in ESP32 sketch

2. **Use HTTPS**
   - Get SSL certificate (Let's Encrypt is free)
   - Configure web server (nginx/Apache)

3. **Firewall rules**
   - Only open necessary ports
   - Restrict to known IP addresses if possible

4. **Rate limiting**
   - Add middleware to prevent abuse
   - Limit requests per device per hour

---

## 🆘 Troubleshooting Quick Reference

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "Failed to read sensor" | Wiring issue | Check connections |
| "WiFi failed" | Wrong credentials | Verify SSID/password |
| "HTTP 401" | API key mismatch | Sync keys |
| "HTTP 500" | Database issue | Run migrations |
| No data in DB | Endpoint wrong | Check server URL |
| Sensor always shows same value | Sensor failure | Replace DHT22 |

---

## 📚 Additional Resources

### Official Documentation
- [ESP32 Datasheet](https://www.espressif.com/en/products/socs/esp32)
- [DHT22 Datasheet](https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf)
- [Django Documentation](https://docs.djangoproject.com/)

### Arduino Libraries
- [Adafruit DHT Library](https://github.com/adafruit/DHT-sensor-library)
- [ESP32 Arduino Core](https://github.com/espressif/arduino-esp32)

### Mushroom Growing
- Optimal conditions vary by species
- Research specific requirements for your variety
- Monitor trends, not just individual readings

---

## ✅ Verification Checklist

Before going live, verify:

- [ ] ESP32 connects to WiFi successfully
- [ ] DHT22 readings are realistic (not NaN or 0)
- [ ] Serial Monitor shows successful HTTP POST (201)
- [ ] Django logs show incoming requests
- [ ] Database contains new SensorReading entries
- [ ] API key authentication works (if enabled)
- [ ] Notifications created for critical conditions
- [ ] All test script tests pass

---

## 🎓 Learning Path

If you're new to this:

1. **Week 1:** Get basic ESP32 WiFi working
2. **Week 2:** Add DHT22 sensor, test locally
3. **Week 3:** Set up Django API endpoint
4. **Week 4:** Integrate and test together
5. **Week 5:** Add notifications and alerts
6. **Week 6:** Build dashboard visualizations

Don't rush - building incrementally ensures success!

---

## 🔄 Future Enhancements

Consider adding:

1. **Real-time dashboard** - WebSocket updates
2. **Charts** - Temperature/humidity graphs over time
3. **Automation** - Control heaters/fans based on readings
4. **Mobile app** - Monitor from anywhere
5. **Multiple sensors** - Different growing rooms
6. **Machine learning** - Predict yield based on conditions
7. **Email/SMS alerts** - Critical condition notifications
8. **Data export** - CSV download for analysis

---

## 📞 Support

### Before Asking for Help
1. Check Serial Monitor output
2. Review Django server logs
3. Run test_dht22_integration.py
4. Verify wiring with multimeter
5. Test API with curl/Postman

### Include in Support Request
- Serial Monitor output
- Django error messages
- Your configuration (WiFi, URL, etc.)
- Hardware details (ESP32 model, DHT22 version)
- What you've already tried

---

## 📝 License & Credits

**Created for:** Mushroom Farming Dashboard
**Date:** January 30, 2026
**Author:** AI Assistant (GitHub Copilot)
**Framework:** Django 4.x + Arduino (ESP32)
**Hardware:** ESP32 + DHT22 (AM2302)

**Libraries Used:**
- Adafruit DHT Sensor Library
- Adafruit Unified Sensor
- ESP32 Arduino Core

**Special Thanks:**
- Adafruit for excellent sensor libraries
- Espressif for ESP32 platform
- Django community for robust framework

---

## 🎉 You're All Set!

You now have a complete, production-ready sensor integration system. The DHT22 sensor will continuously monitor your mushroom growing environment and send data to your Django dashboard.

**Happy Mushroom Farming! 🍄**

---

*For detailed technical documentation, see DHT22_INTEGRATION_GUIDE.md*
*For quick reference, see QUICK_REFERENCE.txt*
*For testing, run test_dht22_integration.py*
