# M307 Client CLI - Quick Reference Guide

Command-line interface for M307 Temperature Guard devices.

## Installation

Make the script executable:
```bash
chmod +x m307_client_cli.py
```

Or run with Python:
```bash
python m307_client_cli.py --help
```

## Global Options

All commands require these global options:

```bash
--host HOST          # M307 device IP address (required)
--port PORT          # TCP port (default: 10001)
--timeout SECONDS    # Socket timeout (default: 5.0)
--format {text,json} # Output format (default: text)
```

## Command Reference

### Status & Monitoring

#### Read Complete Status
```bash
./m307_client_cli.py --host 192.168.1.100 status
```

Returns all sensor readings, door states, power, and battery voltage.

#### Get Temperature
```bash
# Sensor 1
./m307_client_cli.py --host 192.168.1.100 temperature --sensor 1

# Sensor 2
./m307_client_cli.py --host 192.168.1.100 temperature --sensor 2

# Internal sensor
./m307_client_cli.py --host 192.168.1.100 temperature --sensor internal
```

#### Get Humidity
```bash
./m307_client_cli.py --host 192.168.1.100 humidity
```

#### Get Door State
```bash
# Door 1
./m307_client_cli.py --host 192.168.1.100 door --door 1

# Door 2
./m307_client_cli.py --host 192.168.1.100 door --door 2
```

#### Get Battery Voltage
```bash
./m307_client_cli.py --host 192.168.1.100 battery
```

#### Get Power Status
```bash
./m307_client_cli.py --host 192.168.1.100 power
```

### Device Configuration

#### Get Device Information
```bash
./m307_client_cli.py --host 192.168.1.100 device-info get
```

Returns device name, temperature unit, MAC address, and serial number.

#### Set Device Information
```bash
# Set device name
./m307_client_cli.py --host 192.168.1.100 device-info set --name "Lab Freezer"

# Set temperature unit
./m307_client_cli.py --host 192.168.1.100 device-info set --unit F

# Set multiple fields
./m307_client_cli.py --host 192.168.1.100 device-info set \
  --name "Lab Freezer" \
  --unit F \
  --serial "SN12345"
```

### Sensor Names

Sensors must be named to enable alarm functionality.

#### Get All Sensor Names
```bash
./m307_client_cli.py --host 192.168.1.100 sensor-names get
```

#### Set Temperature Sensor Names
```bash
./m307_client_cli.py --host 192.168.1.100 sensor-names set-temp "Probe 1" "Probe 2"
```

#### Set Door Sensor Names
```bash
./m307_client_cli.py --host 192.168.1.100 sensor-names set-door "Main Door" "Access Door"
```

#### Set Internal Sensor Names
```bash
./m307_client_cli.py --host 192.168.1.100 sensor-names set-internal "Internal Temp" "Internal RH"
```

### Sensor Limits & Alarms

#### Get Sensor Limits
```bash
./m307_client_cli.py --host 192.168.1.100 limits get
```

#### Set Temperature Sensor Limits
```bash
# Sensor 1
./m307_client_cli.py --host 192.168.1.100 limits set \
  --sensor 1 \
  --lower -20 \
  --upper 5 \
  --delay 15

# Sensor 2
./m307_client_cli.py --host 192.168.1.100 limits set \
  --sensor 2 \
  --lower 60 \
  --upper 80 \
  --delay 10
```

#### Set Humidity Limits
```bash
./m307_client_cli.py --host 192.168.1.100 limits set \
  --humidity \
  --humidity-lower 20.0 \
  --humidity-upper 80.0 \
  --humidity-delay 30
```

#### Set Door Alarm Delays
```bash
./m307_client_cli.py --host 192.168.1.100 limits set \
  --door1-delay 5 \
  --door2-delay 10
```

#### Set Limits from JSON File
```bash
./m307_client_cli.py --host 192.168.1.100 limits set --file limits.json
```

Example `limits.json`:
```json
{
  "temp_sensor_1": {
    "lower_limit": -20,
    "upper_limit": 5,
    "time_delay": 15
  },
  "temp_sensor_2": {
    "lower_limit": 60,
    "upper_limit": 80,
    "time_delay": 10
  },
  "internal_humidity": {
    "lower_limit": 200,
    "upper_limit": 800,
    "time_delay": 30
  },
  "door_1_time_delay": 5,
  "door_2_time_delay": 10
}
```

### Field Calibration

Apply correction factors to external temperature sensors.

```bash
# Calibrate sensor 1
./m307_client_cli.py --host 192.168.1.100 calibrate --sensor1 -0.2

# Calibrate multiple sensors
./m307_client_cli.py --host 192.168.1.100 calibrate \
  --sensor1 -0.2 \
  --sensor2 0.5 \
  --internal -0.1
```

**Note:** Correction factors are in degrees. They will be multiplied by 10 internally.

### Device Settings

#### Get Device Settings
```bash
./m307_client_cli.py --host 192.168.1.100 settings get
```

#### Set Device Settings
```bash
./m307_client_cli.py --host 192.168.1.100 settings set \
  --relay-logic 0 \
  --alarm-reminder 60 \
  --buzzer true \
  --door-alarm 30
```

**Settings:**
- `--relay-logic`: 0 = normally off, 1 = normally on
- `--alarm-reminder`: Re-alarm every N minutes (0 = disable)
- `--buzzer`: Enable/disable buzzer (true/false)
- `--door-alarm`: Two-stage door alarm delay (minutes)

### Data Logging

#### Set Logging Date/Time and Rate
```bash
# Set current time
./m307_client_cli.py --host 192.168.1.100 log set-time --rate 5

# Set specific date/time
./m307_client_cli.py --host 192.168.1.100 log set-time \
  --datetime "2025-01-15 10:30:00" \
  --rate 10
```

**Rate:** Logging interval in minutes (1-60)

#### Get Log Information
```bash
./m307_client_cli.py --host 192.168.1.100 log info
```

Shows device date/time, log rate, and total records.

#### Read Log File
```bash
# Print to console
./m307_client_cli.py --host 192.168.1.100 log read

# Save to file (text)
./m307_client_cli.py --host 192.168.1.100 log read --output log.txt

# Save to file (JSON)
./m307_client_cli.py --host 192.168.1.100 --format json log read --output log.json

# Read without resetting pointer
./m307_client_cli.py --host 192.168.1.100 log read --no-reset

# Suppress progress indicator
./m307_client_cli.py --host 192.168.1.100 log read --quiet
```

#### Export Log to CSV
```bash
./m307_client_cli.py --host 192.168.1.100 log export --output data.csv
```

Creates CSV with columns:
- Timestamp
- Temperature_1, Temperature_2, Internal_Temperature
- Internal_Humidity
- Door_1_State, Door_2_State
- Power_Status

### Low-Level Record Access

#### Read Raw User Record
```bash
# Print hex dump
./m307_client_cli.py --host 192.168.1.100 record read --record 0

# Save to file
./m307_client_cli.py --host 192.168.1.100 record read --record 0 --output record0.bin

# JSON format
./m307_client_cli.py --host 192.168.1.100 --format json record read --record 0
```

**Records:**
- 0: Sensor limits and calibration
- 1: Device identification
- 2: Temperature sensor names
- 3: Door sensor names
- 4: Device settings
- 5: Internal sensor names

#### Write Raw User Record
```bash
./m307_client_cli.py --host 192.168.1.100 record write --record 0 --file record0.bin
```

**Warning:** Writing raw records can corrupt device configuration. Use high-level commands when possible.

## Output Formats

### Text Format (Default)
Human-readable output:
```bash
./m307_client_cli.py --host 192.168.1.100 status
```

### JSON Format
Machine-readable output for scripting:
```bash
./m307_client_cli.py --host 192.168.1.100 --format json status
```

Example with jq:
```bash
./m307_client_cli.py --host 192.168.1.100 --format json status | \
  jq '.temperature_sensor_1.reading'
```

## Common Workflows

### Complete Device Setup
```bash
HOST="192.168.1.100"

# 1. Set device info
./m307_client_cli.py --host $HOST device-info set --name "Lab Freezer" --unit F

# 2. Name sensors (enables alarms)
./m307_client_cli.py --host $HOST sensor-names set-temp "Freezer Probe" "Ambient"
./m307_client_cli.py --host $HOST sensor-names set-door "Main Door" "Access"
./m307_client_cli.py --host $HOST sensor-names set-internal "Internal Temp" "Internal RH"

# 3. Set temperature limits
./m307_client_cli.py --host $HOST limits set --sensor 1 --lower -20 --upper 5 --delay 15
./m307_client_cli.py --host $HOST limits set --sensor 2 --lower 60 --upper 80 --delay 10

# 4. Set door alarm
./m307_client_cli.py --host $HOST limits set --door1-delay 5

# 5. Configure settings
./m307_client_cli.py --host $HOST settings set --buzzer true --alarm-reminder 60

# 6. Set up logging
./m307_client_cli.py --host $HOST log set-time --rate 5
```

### Monitoring Script
```bash
#!/bin/bash
HOST="192.168.1.100"

while true; do
  clear
  echo "M307 Status - $(date)"
  echo "================================"
  ./m307_client_cli.py --host $HOST status
  sleep 60
done
```

### Export Historical Data
```bash
HOST="192.168.1.100"
DATE=$(date +%Y%m%d)

# Export to CSV
./m307_client_cli.py --host $HOST log export --output "m307_log_${DATE}.csv"

# Export to JSON
./m307_client_cli.py --host $HOST --format json log read --output "m307_log_${DATE}.json"
```

### Alert on High Temperature
```bash
#!/bin/bash
HOST="192.168.1.100"
THRESHOLD=100

TEMP=$(./m307_client_cli.py --host $HOST --format json temperature --sensor 1 | \
  jq -r '.reading')

if (( $(echo "$TEMP > $THRESHOLD" | bc -l) )); then
  echo "ALERT: Temperature $TEMP exceeds threshold $THRESHOLD"
  # Send email, SMS, etc.
fi
```

### Bulk Configuration from JSON
```bash
# Create configuration file
cat > config.json <<EOF
{
  "device_name": "Lab Freezer",
  "temp_unit": "F",
  "sensors": {
    "temp1": "Freezer Probe",
    "temp2": "Ambient Probe"
  },
  "limits": {
    "temp_sensor_1": {
      "lower_limit": -20,
      "upper_limit": 5,
      "time_delay": 15
    }
  }
}
EOF

# Apply configuration
HOST="192.168.1.100"

# Parse and apply (requires jq)
./m307_client_cli.py --host $HOST device-info set \
  --name "$(jq -r '.device_name' config.json)" \
  --unit "$(jq -r '.temp_unit' config.json)"

./m307_client_cli.py --host $HOST limits set --file <(jq '.limits' config.json)
```

## Error Handling

### Exit Codes
- `0`: Success
- `1`: Error (connection, validation, command failure)
- `130`: Interrupted (Ctrl+C)

### Example Error Handling in Scripts
```bash
#!/bin/bash

if ! ./m307_client_cli.py --host 192.168.1.100 status; then
  echo "Failed to read status" >&2
  exit 1
fi
```

## Tips

1. **Use JSON format for scripting:**
   ```bash
   ./m307_client_cli.py --host 192.168.1.100 --format json status | jq '.'
   ```

2. **Store host in environment variable:**
   ```bash
   export M307_HOST="192.168.1.100"
   ./m307_client_cli.py --host $M307_HOST status
   ```

3. **Create shell alias:**
   ```bash
   alias m307='./m307_client_cli.py --host 192.168.1.100'
   m307 status
   ```

4. **Progress indicators can be suppressed:**
   ```bash
   ./m307_client_cli.py --host 192.168.1.100 log read --quiet
   ```

5. **Increase timeout for slow networks:**
   ```bash
   ./m307_client_cli.py --host 192.168.1.100 --timeout 10.0 log read
   ```

## Troubleshooting

### Connection Failed
```bash
Error: Failed to connect to 192.168.1.100:10001
```
- Verify IP address
- Check network connectivity
- Ensure M307 is powered on
- Verify port 10001 is accessible

### Timeout
```bash
Error: Timeout waiting for response
```
- Increase timeout: `--timeout 10.0`
- Check network stability
- Verify device is responding

### Invalid Parameters
```bash
Error: Invalid sensor_number: 99
```
- Check command syntax
- Use `--help` for usage information

### Permission Denied
```bash
bash: ./m307_client_cli.py: Permission denied
```
- Make script executable: `chmod +x m307_client_cli.py`
- Or use: `python m307_client_cli.py`

## Getting Help

### Command Help
```bash
# General help
./m307_client_cli.py --help

# Command-specific help
./m307_client_cli.py limits --help
./m307_client_cli.py log --help

# Subcommand help
./m307_client_cli.py limits set --help
```

### Examples in Help
All commands include usage examples in their help text.
