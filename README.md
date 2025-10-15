# M307 Temperature Guard TCP Client

> **⚠️ WARNING:** This repository is 100% "vibe coded" and completely untested because I don't actually have one of these devices. Use at your own risk!

Python 2.7/3.4+ client library for communicating with M307 Temperature Guard devices via TCP/IP.

## Overview

The M307 is a temperature and humidity monitoring device with door sensors, battery backup, and data logging capabilities. This client library provides a clean, Pythonic interface to all M307 features:

- Reading current sensor status (temperature, humidity, door sensors)
- Configuring device settings and alarm limits
- Managing on-board data logging (up to 4000 records)
- Field calibration support

## Requirements

- Python 2.7 or Python 3.4+
- Network access to M307 device (default port: 10001)

## Installation

Simply copy `m307_client.py` to your project directory:

```python
from m307_client import M307Client
```

## Quick Start

```python
from m307_client import M307Client

# Read current status
with M307Client('192.168.1.100') as client:
    status = client.read_status()
    print "Temperature: {} {}".format(
        status['temperature_sensor_1']['reading'],
        status['temperature_unit']
    )
```

## API Documentation

- [Connection Management](#connection-management)
- [Reading Status](#reading-status)
- [Configuration](#configuration)
  - [Device Identification](#device-identification)
  - [Sensor Names](#sensor-names)
  - [Sensor Limits and Alarms](#sensor-limits-and-alarms)
  - [Field Calibration](#field-calibration)
  - [Device Settings](#device-settings)
- [Data Logging](#data-logging)
- [Low-Level User Record Access](#low-level-user-record-access)
- [Helper Methods](#helper-methods)

### Connection Management

#### Basic Usage

```python
# Manual connection management
client = M307Client('192.168.1.100')
client.connect()
try:
    status = client.read_status()
finally:
    client.disconnect()

# Context manager (recommended)
with M307Client('192.168.1.100') as client:
    status = client.read_status()
```

#### Constructor

```python
M307Client(host, port=10001, timeout=5.0)
```

**Parameters:**
- `host` (str): IP address or hostname of M307 device
- `port` (int, optional): TCP port (default: 10001)
- `timeout` (float, optional): Socket timeout in seconds (default: 5.0)

### Reading Status

#### read_status()

Read complete status from all sensors and inputs.

```python
status = client.read_status()
```

**Returns:** dict with the following structure:

```python
{
    'temperature_sensor_1': {
        'reading': 72.5,           # Temperature in configured unit
        'time_out_of_limits': 0,   # Minutes out of limits
        'in_alarm': False          # Alarm state
    },
    'temperature_sensor_2': { ... },
    'internal_temperature': { ... },
    'internal_humidity': {
        'reading': 45.2,           # Humidity in % RH
        'time_out_of_limits': 0,
        'in_alarm': False
    },
    'door_1': {
        'state': 'closed',         # 'open' or 'closed'
        'time_out_of_limits': 0,
        'in_alarm': False
    },
    'door_2': { ... },
    'main_power': True,            # Main power on/off
    'battery_voltage': 3.24,       # Battery voltage in volts
    'temperature_resolution': 0.1, # 0.1 or 1.0 degree resolution
    'temperature_unit': 'F'        # 'C' or 'F'
}
```

**Special temperature values:**
- `None`: No sensor connected
- `float('inf')`: Sensor open circuit
- `float('-inf')`: Sensor shorted

#### Convenience Methods

```python
# Get individual sensor readings
temp1 = client.get_temperature(1)          # Sensor 1
temp2 = client.get_temperature(2)          # Sensor 2
temp_int = client.get_temperature('internal')  # Internal sensor

humidity = client.get_humidity()

door1 = client.get_door_state(1)
door2 = client.get_door_state(2)

battery = client.get_battery_voltage()     # Returns float (volts)
power = client.get_power_status()          # Returns bool
```

### Configuration

#### Device Identification

```python
# Get device info
info = client.get_device_info()
# Returns: {'device_name': str, 'unit_of_measure': str,
#           'mac_address': str, 'serial_number': str}

# Set device info
client.set_device_info({
    'device_name': 'Lab Freezer #1',
    'unit_of_measure': 'F',  # 'C' or 'F'
})
```

#### Sensor Names

Sensors must be named to enable alarm functionality.

```python
# Temperature sensors
client.set_temperature_sensor_names('Probe 1', 'Probe 2')
names = client.get_temperature_sensor_names()

# Door sensors
client.set_door_sensor_names('Main Door', 'Access Door')
names = client.get_door_sensor_names()

# Internal sensors
client.set_internal_sensor_names('Internal Temp', 'Internal RH')
names = client.get_internal_sensor_names()
```

#### Sensor Limits and Alarms

```python
# Set alarm limits
limits = {
    'temp_sensor_1': {
        'lower_limit': -20,      # Lower temperature limit
        'upper_limit': 5,        # Upper temperature limit
        'time_delay': 15,        # Minutes before alarm
    },
    'temp_sensor_2': {
        'lower_limit': 60,
        'upper_limit': 80,
        'time_delay': 10,
    },
    'internal_humidity': {
        'lower_limit': 200,      # 20.0% RH (x10)
        'upper_limit': 800,      # 80.0% RH (x10)
        'time_delay': 30,
    },
    'door_1_time_delay': 5,      # Minutes before door alarm
    'door_2_time_delay': 10,
}

client.set_sensor_limits(limits)

# Get current limits
current_limits = client.get_sensor_limits()
```

#### Field Calibration

Apply correction factors to external temperature sensors.

```python
# Example: M307 reads 32.7°, calibrated thermometer reads 32.5°
# Correction Factor = (32.5 - 32.7) * 10 = -2

limits = {
    'temp_sensor_1_correction': -2,
    'temp_sensor_2_correction': 5,
}

client.set_sensor_limits(limits)
```

#### Device Settings

```python
# Configure device behavior
settings = {
    'relay_logic': 0,              # 0=normally off, 1=normally on
    'alarm_reminder_delay': 60,    # Re-alarm every N minutes (0=disable)
    'buzzer_enabled': True,        # Enable/disable buzzer
    'two_stage_door_alarm_delay': 30,  # Secondary alarm delay
}

client.set_device_settings(settings)

# Get current settings
current_settings = client.get_device_settings()
```

### Data Logging

The M307 maintains an on-board log of up to 4000 records with 15-byte entries containing temperature, humidity, door states, and timestamps.

#### Configure Logging

```python
from datetime import datetime

# Set device date/time and logging interval
now = datetime.now()
log_rate = 5  # Log every 5 minutes

client.set_log_datetime(now, log_rate)
```

#### Read Log Information

```python
log_info = client.get_log_info()
# Returns:
# {
#     'datetime': datetime object,
#     'log_rate_minutes': int,
#     'total_records': int
# }
```

#### Read Log File

```python
# Read entire log file
records = client.read_log_file(reset_pointer=True)

# Each record contains:
for record in records:
    print "{} - Temp1: {:.1f}, Humidity: {:.1f}%".format(
        record['datetime'].strftime("%Y-%m-%d %H:%M"),
        record['temp_1'],
        record['internal_humidity']
    )
```

**Record structure:**

```python
{
    'datetime': datetime,      # Timestamp
    'temp_1': float,           # Temperature sensor 1 (÷10)
    'temp_2': float,           # Temperature sensor 2 (÷10)
    'internal_temp': float,    # Internal temperature (÷10)
    'internal_humidity': float,# Internal humidity (÷10)
    'door_1_state': bool,      # Door 1 open/closed
    'door_2_state': bool,      # Door 2 open/closed
    'power_status': bool       # Main power on/off
}
```

#### Streaming Log Read

For large log files, use a callback to process records as they arrive:

```python
def process_record(record):
    if record['temp_1'] > 100:
        print "High temperature alert!"

records = client.read_log_file(
    reset_pointer=True,
    callback=process_record
)
```

### Low-Level User Record Access

For advanced use cases, you can read/write raw 60-byte user records directly:

```python
# Read raw record (0-5)
data = client.read_user_record(0)  # Returns 60-byte bytearray

# Modify and write back
data[8] = 0x42
client.write_user_record(0, data)
```

**User Records:**
- Record 0: Sensor limits and calibration
- Record 1: Device identification
- Record 2: Temperature sensor names
- Record 3: Door sensor names
- Record 4: Device settings
- Record 5: Internal sensor names

### Helper Methods

Static utility methods for data conversion:

```python
# Signed 16-bit integer conversion
value = M307Client.bytes_to_int16(msb, lsb)
msb, lsb = M307Client.int16_to_bytes(value)

# BCD conversion (0-99)
value = M307Client.bcd_to_int(bcd_byte)
bcd = M307Client.int_to_bcd(value)

# Temperature parsing
temp = M307Client.parse_temperature(msb, lsb, resolution=0.1, unit='F')

# Humidity parsing
humidity = M307Client.parse_humidity(msb, lsb)
```

## Error Handling

The client raises specific exceptions for different error types:

```python
from m307_client import (
    M307Error,           # Base exception
    M307ConnectionError, # Connection failures
    M307CommandError,    # Command execution errors
    M307ValidationError  # Invalid parameters
)

try:
    with M307Client('192.168.1.100') as client:
        status = client.read_status()
except M307ConnectionError as e:
    print "Failed to connect: {}".format(e)
except M307CommandError as e:
    print "Command failed: {}".format(e)
except M307ValidationError as e:
    print "Invalid parameter: {}".format(e)
except M307Error as e:
    print "General error: {}".format(e)
```

## Complete Example

```python
from datetime import datetime
from m307_client import M307Client

# Connect to device
with M307Client('192.168.1.100') as client:

    # Configure device
    client.set_device_info({
        'device_name': 'Lab Freezer',
        'unit_of_measure': 'F'
    })

    # Set sensor names (enables alarms)
    client.set_temperature_sensor_names('Freezer Probe', 'Ambient')
    client.set_door_sensor_names('Main Door', 'Access Door')

    # Configure alarm limits
    client.set_sensor_limits({
        'temp_sensor_1': {
            'lower_limit': -20,
            'upper_limit': 5,
            'time_delay': 15
        },
        'door_1_time_delay': 5
    })

    # Read current status
    status = client.read_status()

    temp = status['temperature_sensor_1']['reading']
    if status['temperature_sensor_1']['in_alarm']:
        print "ALARM: Temperature {} out of limits!".format(temp)
    else:
        print "Temperature: {} {}".format(temp, status['temperature_unit'])

    # Configure data logging
    client.set_log_datetime(datetime.now(), log_rate_minutes=5)

    # Read historical data
    records = client.read_log_file()
    print "Retrieved {} log records".format(len(records))
```

## Protocol Details

The M307 uses a simple binary protocol over TCP:

- **Port:** 10001
- **Packet Size:** 60 bytes (4 command + 56 data)
- **Byte Order:** Big-endian (MSB first)
- **Data Types:**
  - Signed 16-bit integers (temperature, time values)
  - BCD (date/time components)
  - ASCII strings (names, identification)

## Python Version Support

This library supports both Python 2.7 and Python 3.4+. It uses:
- `from __future__ import` statements for cross-version compatibility
- `bytearray` and `bytes()` for binary data (compatible with both versions)
- `.format()` strings instead of f-strings
- `argparse` for CLI (available in Python 2.7 and 3.2+)
- Standard library modules compatible with both versions

## Testing

Run the example file to test all functionality:

```bash
python m307_example.py
```

Make sure to update the IP address in the examples to match your M307 device.

## License

This code is provided as-is based on the M307 Integration Guide.

## Support

For M307 device documentation, refer to the official Integration Guide.

For API questions or issues with this client library, please refer to the examples and docstrings in the source code.
