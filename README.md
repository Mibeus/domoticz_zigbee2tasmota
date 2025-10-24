# Zigbee MQTT Bridge for Domoticz

Auto-discovery plugin for Domoticz that automatically creates and manages Zigbee devices via MQTT from Tasmota Zigbee Gateway.

## ✨ Features

- **🔍 Auto-Discovery**: Automatically discovers all Zigbee devices from Tasmota gateway
- **📊 Multi-Sensor Support**: Splits multi-function sensors into separate Domoticz devices
  - Temperature + Humidity sensors
  - Motion sensors with Lux + Temp + Humidity
  - Multi-button switches (1-4 buttons)
  - Door/Window sensors
  - Water leak sensors
  - Dimmers and smart plugs
- **🔄 Partial Updates**: Handles temperature-only or humidity-only updates (battery saving)
- **💡 Calibrated Lux**: Accurate lux conversion for Tuya TS0601 human sensors
- **🔋 Battery Monitoring**: Automatic battery level updates
- **💾 Persistent Storage**: Remembers devices across restarts

## 📋 Requirements

- Domoticz (tested on 2023.2+)
- MQTT broker (Mosquitto recommended)
- Tasmota Zigbee Gateway
- Python 3.x

## 🚀 Installation

### Option 1: Docker (Recommended)
```bash
# Download plugin files
mkdir -p ~/domoticz/plugins/ZigbeeMQTT
cd ~/domoticz/plugins/ZigbeeMQTT
wget https://raw.githubusercontent.com/YOUR_USERNAME/zigbee-mqtt-domoticz/main/plugin.py
wget https://raw.githubusercontent.com/YOUR_USERNAME/zigbee-mqtt-domoticz/main/mqtt.py

# Copy to Docker container
docker cp ~/domoticz/plugins/ZigbeeMQTT domoticz:/config/plugins/

# Restart Domoticz
docker restart domoticz
```

### Option 2: Native Installation
```bash
# Navigate to Domoticz plugins directory
cd /path/to/domoticz/plugins

# Clone repository
git clone https://github.com/YOUR_USERNAME/zigbee-mqtt-domoticz.git ZigbeeMQTT

# Restart Domoticz
sudo systemctl restart domoticz
```

## ⚙️ Configuration

1. Open Domoticz web interface
2. Go to **Setup → Hardware**
3. Add new hardware:
   - **Type**: `Zigbee MQTT Bridge`
   - **Name**: Your choice (e.g., "Zigbee MQTT")
   - **MQTT Server**: IP address of your MQTT broker (e.g., `192.168.1.100`)
   - **Port**: `1883` (default MQTT port)
   - **Username**: Your MQTT username (optional)
   - **Password**: Your MQTT password (optional)
   - **Tasmota Topic**: Your Tasmota device topic (e.g., `Zb_gateway_28F860`)
   - **Debug**: `False` (set to `True` for troubleshooting)
4. Click **Add**

## 🎯 How It Works

### Discovery Process

1. Plugin connects to MQTT broker
2. Sends `ZbStatus` command to Tasmota gateway
3. Requests detailed info for each device with `ZbInfo`
4. Analyzes device capabilities (temperature, motion, buttons, etc.)
5. Creates appropriate Domoticz devices automatically
6. Saves device map for persistence

### Multi-Sensor Example

For a Tuya 10G 4 in 1 Human Motion Sensor Zigbee MmWave Radar Detector with Luminance Temperature Humidity Sensor (TS0601, https://www.aliexpress.com/item/1005009110210160.html) :
```
Physical Device → Creates 3 Domoticz Devices:
├─ "Human Sensor - Motion (0x2A1E)"
├─ "Human Sensor - Temp+Hum (0x2A1E)"
└─ "Human Sensor - Lux (0x2A1E)"
```

### Supported Devices

| Device Type | ZoneType | Features | Example Models |
|------------|----------|----------|----------------|
| Motion Sensor | 13 | Occupancy detection | SNZB-03, TS0601 |
| Door/Window | 21 | Contact sensor | TS0203 |
| Water Leak | 42 | Water detection | TS0207 |
| Temp+Hum | - | Temperature, Humidity | TH01, TS0201 |
| Buttons | - | 1-4 button switches | TS0041, TS0044 |
| Dimmer | - | Dimmable lights | ZBT-DIMLight |
| Smart Plug | - | On/Off control | - |

## 🔧 Advanced Configuration

### Lux Calibration for tuya Human presence sensor 4in1 

The plugin includes calibration for Tuya TS0601 human sensors. Raw illuminance values are converted to actual lux using interpolation:
```python
Raw Value → Lux
23156 → 87
25827 → 145
29165 → 210
31301 → 600
33650 → 1170
33941 → 1750
34089 → 2280
34715 → 3000
```

To add your own calibration points, edit the `calibration` array in `plugin.py`.

### Tasmota Configuration

Ensure your Tasmota Zigbee gateway has MQTT properly configured:
```
Backlog MqttHost YOUR_MQTT_IP; MqttUser YOUR_USER; MqttPassword YOUR_PASS; Topic Zb_gateway_XXXXXX
```

Check MQTT topics in Tasmota console:
```
ZbStatus
```

## 📝 Logs and Debugging

Enable debug mode in hardware settings to see detailed logs:
```bash
# Docker
docker logs -f domoticz | grep Zigbee

# Native
tail -f /var/log/domoticz.log | grep Zigbee
```

Common log messages:
- `MQTT connected` - Successfully connected to broker
- `Found X devices` - Discovery completed
- `Created Temp+Hum: Unit=X` - Device created
- `Updated 0xXXXX T+H: 22.5°C, 55%` - Value updated

## 🐛 Troubleshooting

### Plugin doesn't start
```bash
# Check if mqtt.py is present
ls -la /config/plugins/ZigbeeMQTT/

# View error logs
docker logs domoticz | grep -i error
```

### No devices discovered
1. Check MQTT broker is running: `mosquitto -h`
2. Verify Tasmota topic matches plugin configuration
3. Test MQTT subscription:
```bash
mosquitto_sub -h MQTT_IP -p 1883 -u USER -P PASS -t "tele/YOUR_TOPIC/SENSOR" -v
```

### Devices not updating
1. Enable Debug mode in hardware settings
2. Check if plugin receives MQTT messages
3. Verify device is in `device_map.json`

### Wrong Lux values
The calibration is specific to Tuya TS0601. For other sensors, you may need to adjust the calibration table in the code.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Adding New Device Support

To add support for new device types:

1. Add detection logic in `analyzeCapabilities()`
2. Add device creation in `handleZbInfo()`
3. Add update handling in `handleZbReceived()`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Domoticz team for the plugin framework
- Tasmota project for Zigbee gateway support
- MQTT protocol for reliable messaging
- Shelly MQTT plugin for MQTT client implementation

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/zigbee-mqtt-domoticz/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/zigbee-mqtt-domoticz/discussions)

## 📊 Tested Devices

| Brand | Model | Type | Status |
|-------|-------|------|--------|
| Sonoff | SNZB-03 | Motion | ✅ Working |
| Tuya | TS0601 | Multi-sensor | ✅ Working |
| Tuya | TS0201 | Temp+Hum | ✅ Working |
| Tuya | TS0041 | 1-button | ✅ Working |
| Tuya | TS0044 | 4-button | ✅ Working |
| Tuya | TS0203 | Door/Window | ✅ Working |
| Tuya | TS0207 | Water leak | ✅ Working |

Have you tested other devices? Please submit a PR to update this list!

## 🔄 Version History

### v3.3.0 (Current)
- ✅ Added calibrated Lux conversion for Tuya TS0601
- ✅ Fixed partial temperature/humidity updates
- ✅ Improved multi-sensor device splitting
- ✅ Enhanced error handling and logging

### v3.2.0
- ✅ Added support for partial sensor updates
- ✅ Implemented value caching

### v3.1.0
- ✅ Multi-sensor device splitting
- ✅ Auto-discovery improvements

### v3.0.0
- ✅ Initial public release
