"""
<plugin key="ZigbeeMQTT" name="Zigbee MQTT Bridge" author="Custom" version="3.3.0">
    <description>
        <h2>Zigbee MQTT Auto-Discovery Bridge</h2><br/>
        Multi-sensors are split into separate devices<br/>
        Handles partial updates (Temperature OR Humidity)<br/>
        Calibrated Lux conversion for Tuya TS0601 human sensor
    </description>
    <params>
        <param field="Address" label="MQTT Server" width="300px" required="true" default="192.168.88.115"/>
        <param field="Port" label="Port" width="300px" required="true" default="1883"/>
        <param field="Username" label="Username" width="300px"/>
        <param field="Password" label="Password" width="300px" password="true"/>
        <param field="Mode1" label="Tasmota Topic" width="300px" required="true" default="Zb_gateway_28F860"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import json
import time
from mqtt import MqttClientSH2 as MqttClient

class BasePlugin:
    mqttClient = None
    deviceMap = {}
    discoveryQueue = []
    discoveryInProgress = False
    lastValues = {}
    
    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(2)
        
        DumpConfigToLog()
        self.loadDeviceMap()
        
        mqtt_server = Parameters["Address"].strip()
        mqtt_port = Parameters["Port"].strip()
        
        self.mqttClient = MqttClient(
            mqtt_server, 
            mqtt_port,
            "DomoticzZigbee",
            self.onMQTTConnected, 
            self.onMQTTDisconnected, 
            self.onMQTTPublish, 
            self.onMQTTSubscribed
        )
    
    def onConnect(self, Connection, Status, Description):
        if self.mqttClient:
            self.mqttClient.onConnect(Connection, Status, Description)
    
    def onDisconnect(self, Connection):
        if self.mqttClient:
            self.mqttClient.onDisconnect(Connection)
    
    def onMessage(self, Connection, Data):
        if self.mqttClient:
            self.mqttClient.onMessage(Connection, Data)
    
    def onHeartbeat(self):
        if self.mqttClient:
            self.mqttClient.onHeartbeat()
    
    def onMQTTConnected(self):
        Domoticz.Log("MQTT connected")
        
        topic = Parameters["Mode1"]
        topics = [f"tele/{topic}/SENSOR", f"stat/{topic}/RESULT"]
        
        self.mqttClient.subscribe(topics)
        Domoticz.Log(f"Subscribed to: {topics}")
        
        time.sleep(3)
        self.startDiscovery()
    
    def onMQTTDisconnected(self):
        Domoticz.Log("MQTT disconnected")
    
    def onMQTTSubscribed(self):
        Domoticz.Debug("Subscribed")
    
    def onMQTTPublish(self, topic, message):
        try:
            if isinstance(message, str):
                payload = json.loads(message)
            else:
                payload = message
            
            if "ZbStatus1" in payload:
                self.handleZbStatus(payload["ZbStatus1"])
            elif "ZbInfo" in payload:
                self.handleZbInfo(payload["ZbInfo"])
            elif "ZbReceived" in payload:
                self.handleZbReceived(payload["ZbReceived"])
        except Exception as e:
            Domoticz.Error(f"Error: {e}")
    
    def startDiscovery(self):
        if self.discoveryInProgress:
            return
        
        Domoticz.Log("=== Starting Auto-Discovery ===")
        self.discoveryInProgress = True
        self.discoveryQueue = []
        
        self.mqttClient.publish(f"cmnd/{Parameters['Mode1']}/ZbStatus", "")
    
    def handleZbStatus(self, devices):
        Domoticz.Log(f"Found {len(devices)} devices")
        
        for dev in devices:
            addr = dev.get("Device")
            if addr and addr not in self.deviceMap:
                self.discoveryQueue.append(addr)
        
        if self.discoveryQueue:
            self.requestNext()
        else:
            self.discoveryInProgress = False
    
    def requestNext(self):
        if not self.discoveryQueue:
            Domoticz.Log("Discovery completed")
            self.discoveryInProgress = False
            self.saveDeviceMap()
            return
        
        addr = self.discoveryQueue.pop(0)
        Domoticz.Log(f"Getting info: {addr}")
        self.mqttClient.publish(f"cmnd/{Parameters['Mode1']}/ZbInfo", addr)
    
    def analyzeCapabilities(self, data):
        caps = []
        
        if "ZoneType" in data:
            zt = data["ZoneType"]
            if zt == 13:
                caps.append({"type": "motion", "desc": "Motion"})
            elif zt == 21:
                caps.append({"type": "door", "desc": "Door"})
            elif zt == 42:
                caps.append({"type": "water", "desc": "Water"})
        
        if "Temperature" in data and "Humidity" in data:
            caps.append({"type": "temp_hum", "desc": "Temp+Hum"})
        
        if "Illuminance" in data:
            caps.append({"type": "lux", "desc": "Lux"})
        
        if not caps:
            model = data.get("ModelId", "")
            if model.startswith("TS004"):
                num = model[-1]
                caps.append({"type": f"button_{num}", "desc": f"{num}-button"})
            elif "Dimmer" in data or "ZBT-" in model:
                caps.append({"type": "dimmer", "desc": "Dimmer"})
            elif "Power" in data:
                caps.append({"type": "switch", "desc": "Switch"})
            else:
                caps.append({"type": "unknown", "desc": "Unknown"})
        
        return caps
    
    def getFreeUnit(self):
        for i in range(1, 256):
            if i not in Devices:
                return i
        return None
    
    def handleZbInfo(self, info):
        if not isinstance(info, dict):
            return
        
        for addr, data in info.items():
            if addr in self.deviceMap:
                continue
            
            name = data.get("Name", addr)
            model = data.get("ModelId", "?")
            caps = self.analyzeCapabilities(data)
            
            Domoticz.Log(f"New: {name} ({addr}) - {model}")
            
            units = []
            types = []
            idxs = []
            
            for cap in caps:
                unit = self.getFreeUnit()
                if not unit:
                    continue
                
                dtype = cap["type"]
                desc = cap["desc"]
                
                if len(caps) > 1:
                    dname = f"{name} - {desc} ({addr})"
                else:
                    dname = f"{name} ({addr})"
                
                try:
                    if dtype == "temp_hum":
                        Domoticz.Device(Name=dname, Unit=unit, TypeName="Temp+Hum", Used=1).Create()
                    elif dtype == "lux":
                        Domoticz.Device(Name=dname, Unit=unit, Type=246, Subtype=1, Used=1).Create()
                    elif dtype == "motion":
                        Domoticz.Device(Name=dname, Unit=unit, Type=244, Subtype=73, Switchtype=8, Used=1).Create()
                    elif dtype == "water":
                        Domoticz.Device(Name=dname, Unit=unit, Type=244, Subtype=73, Switchtype=11, Used=1).Create()
                    elif dtype == "door":
                        Domoticz.Device(Name=dname, Unit=unit, Type=244, Subtype=73, Switchtype=2, Used=1).Create()
                    elif dtype == "dimmer":
                        Domoticz.Device(Name=dname, Unit=unit, Type=244, Subtype=73, Switchtype=7, Used=1).Create()
                    elif dtype.startswith("button_"):
                        Domoticz.Device(Name=dname, Unit=unit, Type=243, Subtype=19, Used=1).Create()
                    elif dtype == "switch":
                        Domoticz.Device(Name=dname, Unit=unit, TypeName="Switch", Used=1).Create()
                    else:
                        Domoticz.Device(Name=dname, Unit=unit, Type=243, Subtype=19, Used=1).Create()
                    
                    if unit in Devices:
                        units.append(unit)
                        types.append(dtype)
                        idxs.append(Devices[unit].ID)
                        Domoticz.Log(f"  Created {desc}: Unit={unit}, idx={Devices[unit].ID}")
                        
                        cache_key = f"{addr}_{unit}"
                        self.lastValues[cache_key] = {"temp": 20.0, "hum": 50.0}
                        
                except Exception as e:
                    Domoticz.Error(f"Create error: {e}")
            
            if units:
                self.deviceMap[addr] = {
                    "units": units,
                    "types": types,
                    "idxs": idxs,
                    "name": name
                }
        
        if self.discoveryInProgress:
            time.sleep(0.5)
            self.requestNext()
    
    def handleZbReceived(self, zb_data):
        for addr, data in zb_data.items():
            if addr not in self.deviceMap:
                continue
            
            info = self.deviceMap[addr]
            units = info.get("units", [])
            types = info.get("types", [])
            
            for i, unit in enumerate(units):
                if unit not in Devices:
                    continue
                
                dtype = types[i]
                cache_key = f"{addr}_{unit}"
                
                try:
                    if dtype == "temp_hum":
                        if cache_key not in self.lastValues:
                            current = Devices[unit].sValue
                            if current and ';' in current:
                                parts = current.split(';')
                                self.lastValues[cache_key] = {
                                    "temp": float(parts[0]) if parts[0] else 20.0,
                                    "hum": float(parts[1]) if len(parts) > 1 and parts[1] else 50.0
                                }
                            else:
                                self.lastValues[cache_key] = {"temp": 20.0, "hum": 50.0}
                        
                        if "Temperature" in data:
                            self.lastValues[cache_key]["temp"] = data["Temperature"]
                        if "Humidity" in data:
                            self.lastValues[cache_key]["hum"] = data["Humidity"]
                        
                        temp = self.lastValues[cache_key]["temp"]
                        hum = self.lastValues[cache_key]["hum"]
                        
                        Devices[unit].Update(nValue=0, sValue=f"{temp};{hum};1")
                        Domoticz.Debug(f"Updated {addr} T+H: {temp}°C, {hum}%")
                    
                    elif dtype == "lux" and "Illuminance" in data:
                        raw_lux = data['Illuminance']
                        
                        # Kalibračná tabuľka pre Tuya TS0601 human sensor (nočné merania)
                        calibration = [
                            (1, 0),
                            (23156, 87),
                            (25827, 145),
                            (29165, 210),
                            (31301, 600),
                            (33650, 1170),
                            (33941, 1750),
                            (34089, 2280),
                            (34715, 3000)
                        ]
                        
                        if raw_lux <= 1:
                            lux = 0
                        else:
                            lux = None
                            for j in range(len(calibration) - 1):
                                raw1, lux1 = calibration[j]
                                raw2, lux2 = calibration[j + 1]
                                
                                if raw1 <= raw_lux <= raw2:
                                    ratio = (raw_lux - raw1) / (raw2 - raw1)
                                    lux = round(lux1 + ratio * (lux2 - lux1), 1)
                                    break
                            
                            if lux is None:
                                if raw_lux < calibration[0][0]:
                                    lux = 0
                                else:
                                    raw1, lux1 = calibration[-2]
                                    raw2, lux2 = calibration[-1]
                                    ratio = (raw_lux - raw1) / (raw2 - raw1)
                                    lux = round(lux1 + ratio * (lux2 - lux1), 1)
                        
                        Devices[unit].Update(nValue=0, sValue=str(lux))
                        Domoticz.Debug(f"Updated {addr} Lux: {lux} (raw: {raw_lux})")
                    
                    elif dtype == "motion" and "Occupancy" in data:
                        Devices[unit].Update(nValue=1 if data["Occupancy"] else 0, sValue="")
                        Domoticz.Debug(f"Updated {addr} Motion: {'On' if data['Occupancy'] else 'Off'}")
                    
                    elif dtype == "water" and "Water" in data:
                        lvl = 4 if data["Water"] == 1 else 1
                        Devices[unit].Update(nValue=lvl, sValue="")
                    
                    elif dtype == "door" and "ZoneStatusChange" in data:
                        Devices[unit].Update(nValue=data["ZoneStatusChange"], sValue="")
                    
                    elif dtype.startswith("button_") and "LidlPower" in data:
                        val = f"{data.get('Endpoint',1)}-{data['LidlPower']}"
                        Devices[unit].Update(nValue=0, sValue=val)
                        Domoticz.Log(f"Button {addr}: {val}")
                    
                    elif dtype == "dimmer" and "Power" in data:
                        lvl = int((data.get("Dimmer", 254) / 254) * 100)
                        Devices[unit].Update(nValue=data["Power"], sValue=str(lvl))
                    
                    elif dtype == "switch" and "Power" in data:
                        Devices[unit].Update(nValue=data["Power"], sValue="")
                    
                    if "BatteryPercentage" in data:
                        Devices[unit].Update(
                            nValue=Devices[unit].nValue,
                            sValue=Devices[unit].sValue,
                            BatteryLevel=data["BatteryPercentage"]
                        )
                        
                except Exception as e:
                    Domoticz.Error(f"Update error {addr}: {e}")
                    import traceback
                    Domoticz.Error(traceback.format_exc())
    
    def saveDeviceMap(self):
        try:
            import os
            f = os.path.join(os.path.dirname(__file__), "device_map.json")
            with open(f, 'w') as fp:
                json.dump(self.deviceMap, fp, indent=2)
            Domoticz.Log(f"Saved {len(self.deviceMap)} devices")
        except Exception as e:
            Domoticz.Error(f"Save error: {e}")
    
    def loadDeviceMap(self):
        try:
            import os
            f = os.path.join(os.path.dirname(__file__), "device_map.json")
            if os.path.exists(f):
                with open(f) as fp:
                    self.deviceMap = json.load(fp)
                Domoticz.Log(f"Loaded {len(self.deviceMap)} devices")
        except:
            pass

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug(f"'{x}':'{Parameters[x]}'")
