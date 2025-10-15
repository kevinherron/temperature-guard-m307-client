#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M307 Client CLI - Command-line interface for M307 Temperature Guard devices

Usage:
    m307_client_cli.py --host HOST COMMAND [OPTIONS]

Examples:
    # Read status
    m307_client_cli.py --host 192.168.1.100 status

    # Get temperature
    m307_client_cli.py --host 192.168.1.100 temperature --sensor 1

    # Set device name
    m307_client_cli.py --host 192.168.1.100 device-info set --name "Lab Freezer"

    # Export log to CSV
    m307_client_cli.py --host 192.168.1.100 log export --output data.csv
"""

from __future__ import division, print_function, absolute_import

import sys
import json
import argparse
from datetime import datetime
from m307_client import M307Client, M307Error


# =============================================================================
# Output Formatters
# =============================================================================

def format_output(data, output_format='text'):
    """
    Format data for output

    Args:
        data: Data to format (dict, list, or primitive)
        output_format: 'text' or 'json'
    """
    if output_format == 'json':
        return json.dumps(data, indent=2, default=str)
    else:
        return format_text(data)


def format_text(data, indent=0):
    """Format data as human-readable text"""
    if isinstance(data, dict):
        lines = []
        for key, value in sorted(data.items()):
            prefix = "  " * indent
            if isinstance(value, dict):
                lines.append("{}{}:".format(prefix, key))
                lines.append(format_text(value, indent + 1))
            elif isinstance(value, list):
                lines.append("{}{}:".format(prefix, key))
                for item in value:
                    lines.append(format_text(item, indent + 1))
            else:
                lines.append("{}{}: {}".format(prefix, key, value))
        return "\n".join(lines)
    elif isinstance(data, list):
        lines = []
        for item in data:
            lines.append(format_text(item, indent))
        return "\n".join(lines)
    else:
        prefix = "  " * indent
        return "{}{}".format(prefix, data)


def print_output(data, output_format='text'):
    """Print formatted output"""
    print(format_output(data, output_format))


def print_error(message):
    """Print error message to stderr"""
    sys.stderr.write("Error: {}\n".format(message))


def print_success(message):
    """Print success message"""
    print(message)


# =============================================================================
# Progress Indicator
# =============================================================================

class ProgressIndicator(object):
    """Simple progress indicator for long operations"""

    def __init__(self, total=None, description=""):
        self.total = total
        self.description = description
        self.current = 0

    def update(self, count=1):
        """Update progress"""
        self.current += count
        if self.total:
            percent = int(100.0 * self.current / self.total)
            sys.stderr.write("\r{}: {} / {} ({}%)".format(
                self.description, self.current, self.total, percent
            ))
        else:
            sys.stderr.write("\r{}: {}".format(self.description, self.current))
        sys.stderr.flush()

    def finish(self):
        """Finish progress indicator"""
        sys.stderr.write("\n")
        sys.stderr.flush()


# =============================================================================
# Command Handlers - Status & Monitoring
# =============================================================================

def cmd_status(args, client):
    """Read complete status"""
    status = client.read_status()
    print_output(status, args.format)
    return 0


def cmd_temperature(args, client):
    """Get temperature reading"""
    temp = client.get_temperature(args.sensor)

    if args.format == 'json':
        print_output(temp, args.format)
    else:
        reading = temp['reading']
        status_str = "ALARM" if temp['in_alarm'] else "OK"

        if reading is None:
            print("Sensor {}: No sensor connected".format(args.sensor))
        elif reading == float('inf'):
            print("Sensor {}: Open circuit".format(args.sensor))
        elif reading == float('-inf'):
            print("Sensor {}: Shorted".format(args.sensor))
        else:
            print("Sensor {}: {} ({})".format(args.sensor, reading, status_str))
            if temp['in_alarm']:
                print("  Out of limits for {} minutes".format(temp['time_out_of_limits']))

    return 0


def cmd_humidity(args, client):
    """Get humidity reading"""
    humidity = client.get_humidity()

    if args.format == 'json':
        print_output(humidity, args.format)
    else:
        reading = humidity['reading']
        status_str = "ALARM" if humidity['in_alarm'] else "OK"

        if reading is None:
            print("Humidity: Sensor failed")
        else:
            print("Humidity: {}% RH ({})".format(reading, status_str))
            if humidity['in_alarm']:
                print("  Out of limits for {} minutes".format(humidity['time_out_of_limits']))

    return 0


def cmd_door(args, client):
    """Get door state"""
    door = client.get_door_state(args.door)

    if args.format == 'json':
        print_output(door, args.format)
    else:
        state = door['state']
        status_str = "ALARM" if door['in_alarm'] else "OK"

        print("Door {}: {} ({})".format(args.door, state.upper(), status_str))
        if door['in_alarm']:
            print("  Open for {} minutes".format(door['time_out_of_limits']))

    return 0


def cmd_battery(args, client):
    """Get battery voltage"""
    voltage = client.get_battery_voltage()

    if args.format == 'json':
        print_output({'battery_voltage': voltage}, args.format)
    else:
        print("Battery: {:.2f}V".format(voltage))

    return 0


def cmd_power(args, client):
    """Get power status"""
    power = client.get_power_status()

    if args.format == 'json':
        print_output({'main_power': power}, args.format)
    else:
        print("Main Power: {}".format("ON" if power else "OFF"))

    return 0


# =============================================================================
# Command Handlers - Device Configuration
# =============================================================================

def cmd_device_info_get(args, client):
    """Get device information"""
    info = client.get_device_info()
    print_output(info, args.format)
    return 0


def cmd_device_info_set(args, client):
    """Set device information"""
    info = {}

    if args.name is not None:
        info['device_name'] = args.name
    if args.unit is not None:
        info['unit_of_measure'] = args.unit
    if args.mac is not None:
        info['mac_address'] = args.mac
    if args.serial is not None:
        info['serial_number'] = args.serial

    if not info:
        print_error("No parameters specified. Use --name, --unit, --mac, or --serial")
        return 1

    client.set_device_info(info)
    print_success("Device information updated")
    return 0


# =============================================================================
# Command Handlers - Sensor Names
# =============================================================================

def cmd_sensor_names_get(args, client):
    """Get all sensor names"""
    names = {
        'temperature_sensors': client.get_temperature_sensor_names(),
        'door_sensors': client.get_door_sensor_names(),
        'internal_sensors': client.get_internal_sensor_names(),
    }
    print_output(names, args.format)
    return 0


def cmd_sensor_names_set_temp(args, client):
    """Set temperature sensor names"""
    client.set_temperature_sensor_names(args.sensor1, args.sensor2)
    print_success("Temperature sensor names updated")
    return 0


def cmd_sensor_names_set_door(args, client):
    """Set door sensor names"""
    client.set_door_sensor_names(args.door1, args.door2)
    print_success("Door sensor names updated")
    return 0


def cmd_sensor_names_set_internal(args, client):
    """Set internal sensor names"""
    client.set_internal_sensor_names(args.temperature, args.humidity)
    print_success("Internal sensor names updated")
    return 0


# =============================================================================
# Command Handlers - Sensor Limits
# =============================================================================

def cmd_limits_get(args, client):
    """Get sensor limits"""
    limits = client.get_sensor_limits()
    print_output(limits, args.format)
    return 0


def cmd_limits_set(args, client):
    """Set sensor limits"""
    limits = {}

    if args.file:
        # Load from JSON file
        try:
            with open(args.file, 'r') as f:
                limits = json.load(f)
        except (IOError, ValueError) as e:
            print_error("Failed to load limits file: {}".format(e))
            return 1
    else:
        # Build from command line arguments
        if args.sensor:
            sensor_key = None
            if args.sensor == 1:
                sensor_key = 'temp_sensor_1'
            elif args.sensor == 2:
                sensor_key = 'temp_sensor_2'
            elif args.sensor == 'internal':
                sensor_key = 'internal_temp'

            if sensor_key:
                limits[sensor_key] = {}
                if args.lower is not None:
                    limits[sensor_key]['lower_limit'] = args.lower
                if args.upper is not None:
                    limits[sensor_key]['upper_limit'] = args.upper
                if args.delay is not None:
                    limits[sensor_key]['time_delay'] = args.delay

        if args.humidity:
            limits['internal_humidity'] = {}
            if args.humidity_lower is not None:
                limits['internal_humidity']['lower_limit'] = int(args.humidity_lower * 10)
            if args.humidity_upper is not None:
                limits['internal_humidity']['upper_limit'] = int(args.humidity_upper * 10)
            if args.humidity_delay is not None:
                limits['internal_humidity']['time_delay'] = args.humidity_delay

        if args.door1_delay is not None:
            limits['door_1_time_delay'] = args.door1_delay
        if args.door2_delay is not None:
            limits['door_2_time_delay'] = args.door2_delay

    if not limits:
        print_error("No limits specified. Use --sensor, --humidity, or --file")
        return 1

    client.set_sensor_limits(limits)
    print_success("Sensor limits updated")
    return 0


def cmd_calibrate(args, client):
    """Set calibration correction factors"""
    limits = {}

    if args.sensor1 is not None:
        limits['temp_sensor_1_correction'] = int(args.sensor1 * 10)
    if args.sensor2 is not None:
        limits['temp_sensor_2_correction'] = int(args.sensor2 * 10)
    if args.internal is not None:
        limits['internal_temp_correction'] = int(args.internal * 10)

    if not limits:
        print_error("No correction factors specified")
        return 1

    client.set_sensor_limits(limits)
    print_success("Calibration corrections applied")
    return 0


# =============================================================================
# Command Handlers - Device Settings
# =============================================================================

def cmd_settings_get(args, client):
    """Get device settings"""
    settings = client.get_device_settings()
    print_output(settings, args.format)
    return 0


def cmd_settings_set(args, client):
    """Set device settings"""
    settings = {}

    if args.relay_logic is not None:
        settings['relay_logic'] = args.relay_logic
    if args.alarm_reminder is not None:
        settings['alarm_reminder_delay'] = args.alarm_reminder
    if args.buzzer is not None:
        settings['buzzer_enabled'] = args.buzzer
    if args.door_alarm is not None:
        settings['two_stage_door_alarm_delay'] = args.door_alarm

    if not settings:
        print_error("No settings specified")
        return 1

    client.set_device_settings(settings)
    print_success("Device settings updated")
    return 0


# =============================================================================
# Command Handlers - Data Logging
# =============================================================================

def cmd_log_set_time(args, client):
    """Set logging date/time and rate"""
    if args.datetime:
        try:
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print_error("Invalid datetime format. Use: YYYY-MM-DD HH:MM:SS")
            return 1
    else:
        dt = datetime.now()

    client.set_log_datetime(dt, args.rate)

    if args.format == 'json':
        print_output({
            'datetime': dt.strftime("%Y-%m-%d %H:%M:%S"),
            'log_rate_minutes': args.rate
        }, args.format)
    else:
        print("Date/Time set to: {}".format(dt.strftime("%Y-%m-%d %H:%M:%S")))
        print("Log rate: {} minutes".format(args.rate))

    return 0


def cmd_log_info(args, client):
    """Get log information"""
    info = client.get_log_info()

    if args.format == 'json':
        print_output(info, args.format)
    else:
        print("Device Date/Time: {}".format(info['datetime'].strftime("%Y-%m-%d %H:%M:%S")))
        print("Log Rate: {} minutes".format(info['log_rate_minutes']))
        print("Total Records: {}".format(info['total_records']))

    return 0


def cmd_log_read(args, client):
    """Read log file"""
    progress = None

    if not args.quiet:
        log_info = client.get_log_info()
        progress = ProgressIndicator(log_info['total_records'], "Reading log")

    def callback(record):
        if progress:
            progress.update()

    records = client.read_log_file(
        reset_pointer=args.reset,
        callback=callback if progress else None
    )

    if progress:
        progress.finish()

    # Output records
    if args.output:
        try:
            with open(args.output, 'w') as f:
                if args.format == 'json':
                    json.dump(records, f, indent=2, default=str)
                else:
                    for record in records:
                        f.write("{}\n".format(format_output(record, 'text')))
            print_success("Log saved to: {}".format(args.output))
        except IOError as e:
            print_error("Failed to write output file: {}".format(e))
            return 1
    else:
        print_output(records, args.format)

    return 0


def cmd_log_export(args, client):
    """Export log to CSV"""
    import csv

    progress = None

    if not args.quiet:
        log_info = client.get_log_info()
        progress = ProgressIndicator(log_info['total_records'], "Reading log")

    def callback(record):
        if progress:
            progress.update()

    records = client.read_log_file(
        reset_pointer=args.reset,
        callback=callback if progress else None
    )

    if progress:
        progress.finish()

    if not records:
        print_error("No log records to export")
        return 1

    # Write CSV
    try:
        with open(args.output, 'w') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Timestamp',
                'Temperature_1',
                'Temperature_2',
                'Internal_Temperature',
                'Internal_Humidity',
                'Door_1_State',
                'Door_2_State',
                'Power_Status'
            ])

            # Data rows
            for record in records:
                writer.writerow([
                    record['datetime'].strftime("%Y-%m-%d %H:%M:%S"),
                    record['temp_1'],
                    record['temp_2'],
                    record['internal_temp'],
                    record['internal_humidity'],
                    1 if record['door_1_state'] else 0,
                    1 if record['door_2_state'] else 0,
                    1 if record['power_status'] else 0
                ])

        print_success("Log exported to: {}".format(args.output))
        print("Total records: {}".format(len(records)))

    except IOError as e:
        print_error("Failed to write CSV file: {}".format(e))
        return 1

    return 0


# =============================================================================
# Command Handlers - Low-Level Record Access
# =============================================================================

def cmd_record_read(args, client):
    """Read raw user record"""
    data = client.read_user_record(args.record)

    if args.output:
        try:
            with open(args.output, 'wb') as f:
                f.write(bytes(data))
            print_success("Record {} saved to: {}".format(args.record, args.output))
        except IOError as e:
            print_error("Failed to write file: {}".format(e))
            return 1
    else:
        # Print hex dump
        if args.format == 'json':
            print_output({'record': [int(b) for b in data]}, args.format)
        else:
            print("Record {} (60 bytes):".format(args.record))
            for i in range(0, len(data), 16):
                hex_str = ' '.join("{:02x}".format(b) for b in data[i:i+16])
                ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[i:i+16])
                print("{:04x}  {}  {}".format(i, hex_str.ljust(48), ascii_str))

    return 0


def cmd_record_write(args, client):
    """Write raw user record"""
    try:
        with open(args.file, 'rb') as f:
            data = bytearray(f.read())
    except IOError as e:
        print_error("Failed to read file: {}".format(e))
        return 1

    if len(data) != 60:
        print_error("File must be exactly 60 bytes (got {})".format(len(data)))
        return 1

    client.write_user_record(args.record, data)
    print_success("Record {} written successfully".format(args.record))
    return 0


# =============================================================================
# Argument Parser Setup
# =============================================================================

def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='M307 Temperature Guard CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read status
  %(prog)s --host 192.168.1.100 status

  # Get temperature from sensor 1
  %(prog)s --host 192.168.1.100 temperature --sensor 1

  # Set device name
  %(prog)s --host 192.168.1.100 device-info set --name "Lab Freezer"

  # Set temperature sensor limits
  %(prog)s --host 192.168.1.100 limits set --sensor 1 --lower -20 --upper 5 --delay 15

  # Export log to CSV
  %(prog)s --host 192.168.1.100 log export --output data.csv

  # Get status as JSON
  %(prog)s --host 192.168.1.100 --format json status
"""
    )

    # Global options
    parser.add_argument('--host', required=True,
                        help='M307 device IP address')
    parser.add_argument('--port', type=int, default=10001,
                        help='TCP port (default: 10001)')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='Socket timeout in seconds (default: 5.0)')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                        help='Output format (default: text)')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # -------------------------------------------------------------------------
    # Status & Monitoring Commands
    # -------------------------------------------------------------------------

    # status
    subparsers.add_parser('status',
                          help='Read complete status from all sensors')

    # temperature
    temp_parser = subparsers.add_parser('temperature',
                                        help='Get temperature reading')
    temp_parser.add_argument('--sensor', required=True,
                             help='Sensor number: 1, 2, or internal')

    # humidity
    subparsers.add_parser('humidity',
                          help='Get humidity reading')

    # door
    door_parser = subparsers.add_parser('door',
                                        help='Get door state')
    door_parser.add_argument('--door', type=int, required=True, choices=[1, 2],
                             help='Door number: 1 or 2')

    # battery
    subparsers.add_parser('battery',
                          help='Get battery voltage')

    # power
    subparsers.add_parser('power',
                          help='Get main power status')

    # -------------------------------------------------------------------------
    # Device Configuration Commands
    # -------------------------------------------------------------------------

    # device-info
    device_info_parser = subparsers.add_parser('device-info',
                                               help='Get/set device information')
    device_info_subparsers = device_info_parser.add_subparsers(dest='subcommand')

    device_info_subparsers.add_parser('get', help='Get device information')

    device_info_set_parser = device_info_subparsers.add_parser('set',
                                                                help='Set device information')
    device_info_set_parser.add_argument('--name', help='Device name')
    device_info_set_parser.add_argument('--unit', choices=['C', 'F'],
                                        help='Temperature unit')
    device_info_set_parser.add_argument('--mac', help='MAC address')
    device_info_set_parser.add_argument('--serial', help='Serial number')

    # -------------------------------------------------------------------------
    # Sensor Names Commands
    # -------------------------------------------------------------------------

    # sensor-names
    names_parser = subparsers.add_parser('sensor-names',
                                         help='Get/set sensor names')
    names_subparsers = names_parser.add_subparsers(dest='subcommand')

    names_subparsers.add_parser('get', help='Get all sensor names')

    temp_names_parser = names_subparsers.add_parser('set-temp',
                                                     help='Set temperature sensor names')
    temp_names_parser.add_argument('sensor1', help='Name for sensor 1')
    temp_names_parser.add_argument('sensor2', help='Name for sensor 2')

    door_names_parser = names_subparsers.add_parser('set-door',
                                                     help='Set door sensor names')
    door_names_parser.add_argument('door1', help='Name for door 1')
    door_names_parser.add_argument('door2', help='Name for door 2')

    internal_names_parser = names_subparsers.add_parser('set-internal',
                                                         help='Set internal sensor names')
    internal_names_parser.add_argument('temperature', help='Name for temperature')
    internal_names_parser.add_argument('humidity', help='Name for humidity')

    # -------------------------------------------------------------------------
    # Sensor Limits Commands
    # -------------------------------------------------------------------------

    # limits
    limits_parser = subparsers.add_parser('limits',
                                          help='Get/set sensor limits')
    limits_subparsers = limits_parser.add_subparsers(dest='subcommand')

    limits_subparsers.add_parser('get', help='Get sensor limits')

    limits_set_parser = limits_subparsers.add_parser('set',
                                                      help='Set sensor limits')
    limits_set_parser.add_argument('--file', help='Load limits from JSON file')
    limits_set_parser.add_argument('--sensor', type=int, choices=[1, 2],
                                   help='Temperature sensor number')
    limits_set_parser.add_argument('--lower', type=float,
                                   help='Lower temperature limit')
    limits_set_parser.add_argument('--upper', type=float,
                                   help='Upper temperature limit')
    limits_set_parser.add_argument('--delay', type=int,
                                   help='Time delay in minutes')
    limits_set_parser.add_argument('--humidity', action='store_true',
                                   help='Set humidity limits')
    limits_set_parser.add_argument('--humidity-lower', type=float,
                                   help='Lower humidity limit (%%RH)')
    limits_set_parser.add_argument('--humidity-upper', type=float,
                                   help='Upper humidity limit (%%RH)')
    limits_set_parser.add_argument('--humidity-delay', type=int,
                                   help='Humidity time delay (minutes)')
    limits_set_parser.add_argument('--door1-delay', type=int,
                                   help='Door 1 time delay (minutes)')
    limits_set_parser.add_argument('--door2-delay', type=int,
                                   help='Door 2 time delay (minutes)')

    # calibrate
    calibrate_parser = subparsers.add_parser('calibrate',
                                             help='Set calibration correction factors')
    calibrate_parser.add_argument('--sensor1', type=float,
                                  help='Correction for sensor 1 (degrees)')
    calibrate_parser.add_argument('--sensor2', type=float,
                                  help='Correction for sensor 2 (degrees)')
    calibrate_parser.add_argument('--internal', type=float,
                                  help='Correction for internal sensor (degrees)')

    # -------------------------------------------------------------------------
    # Device Settings Commands
    # -------------------------------------------------------------------------

    # settings
    settings_parser = subparsers.add_parser('settings',
                                            help='Get/set device settings')
    settings_subparsers = settings_parser.add_subparsers(dest='subcommand')

    settings_subparsers.add_parser('get', help='Get device settings')

    settings_set_parser = settings_subparsers.add_parser('set',
                                                          help='Set device settings')
    settings_set_parser.add_argument('--relay-logic', type=int, choices=[0, 1],
                                     help='Relay logic: 0=normally off, 1=normally on')
    settings_set_parser.add_argument('--alarm-reminder', type=int,
                                     help='Alarm reminder delay (minutes, 0=disable)')
    settings_set_parser.add_argument('--buzzer', type=lambda x: x.lower() in ('true', 'yes', '1'),
                                     help='Enable buzzer: true/false')
    settings_set_parser.add_argument('--door-alarm', type=int,
                                     help='Two-stage door alarm delay (minutes)')

    # -------------------------------------------------------------------------
    # Data Logging Commands
    # -------------------------------------------------------------------------

    # log
    log_parser = subparsers.add_parser('log',
                                       help='Data logging operations')
    log_subparsers = log_parser.add_subparsers(dest='subcommand')

    log_time_parser = log_subparsers.add_parser('set-time',
                                                 help='Set logging date/time and rate')
    log_time_parser.add_argument('--datetime',
                                 help='Date/time (YYYY-MM-DD HH:MM:SS, default: now)')
    log_time_parser.add_argument('--rate', type=int, required=True,
                                 help='Log rate in minutes (1-60)')

    log_subparsers.add_parser('info', help='Get log information')

    log_read_parser = log_subparsers.add_parser('read',
                                                 help='Read log file')
    log_read_parser.add_argument('--output', help='Output file')
    log_read_parser.add_argument('--reset', action='store_true', default=True,
                                 help='Reset log pointer (default: true)')
    log_read_parser.add_argument('--no-reset', dest='reset', action='store_false',
                                 help='Do not reset log pointer')
    log_read_parser.add_argument('--quiet', action='store_true',
                                 help='Suppress progress indicator')

    log_export_parser = log_subparsers.add_parser('export',
                                                   help='Export log to CSV')
    log_export_parser.add_argument('--output', required=True,
                                   help='Output CSV file')
    log_export_parser.add_argument('--reset', action='store_true', default=True,
                                   help='Reset log pointer (default: true)')
    log_export_parser.add_argument('--no-reset', dest='reset', action='store_false',
                                   help='Do not reset log pointer')
    log_export_parser.add_argument('--quiet', action='store_true',
                                   help='Suppress progress indicator')

    # -------------------------------------------------------------------------
    # Low-Level Record Commands
    # -------------------------------------------------------------------------

    # record
    record_parser = subparsers.add_parser('record',
                                          help='Low-level record access')
    record_subparsers = record_parser.add_subparsers(dest='subcommand')

    record_read_parser = record_subparsers.add_parser('read',
                                                       help='Read raw user record')
    record_read_parser.add_argument('--record', type=int, required=True,
                                    choices=range(6),
                                    help='Record number (0-5)')
    record_read_parser.add_argument('--output', help='Save to file')

    record_write_parser = record_subparsers.add_parser('write',
                                                        help='Write raw user record')
    record_write_parser.add_argument('--record', type=int, required=True,
                                     choices=range(6),
                                     help='Record number (0-5)')
    record_write_parser.add_argument('--file', required=True,
                                     help='File with 60-byte record data')

    return parser


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Map commands to handlers
    command_map = {
        'status': cmd_status,
        'temperature': cmd_temperature,
        'humidity': cmd_humidity,
        'door': cmd_door,
        'battery': cmd_battery,
        'power': cmd_power,
    }

    device_info_map = {
        'get': cmd_device_info_get,
        'set': cmd_device_info_set,
    }

    sensor_names_map = {
        'get': cmd_sensor_names_get,
        'set-temp': cmd_sensor_names_set_temp,
        'set-door': cmd_sensor_names_set_door,
        'set-internal': cmd_sensor_names_set_internal,
    }

    limits_map = {
        'get': cmd_limits_get,
        'set': cmd_limits_set,
    }

    settings_map = {
        'get': cmd_settings_get,
        'set': cmd_settings_set,
    }

    log_map = {
        'set-time': cmd_log_set_time,
        'info': cmd_log_info,
        'read': cmd_log_read,
        'export': cmd_log_export,
    }

    record_map = {
        'read': cmd_record_read,
        'write': cmd_record_write,
    }

    # Handle special temperature sensor argument
    if args.command == 'temperature':
        if args.sensor not in ('1', '2', 'internal'):
            try:
                args.sensor = int(args.sensor)
            except ValueError:
                if args.sensor == 'internal':
                    pass
                else:
                    print_error("Invalid sensor: {}".format(args.sensor))
                    return 1

    # Execute command
    try:
        with M307Client(args.host, args.port, args.timeout) as client:
            # Route to handler
            if args.command in command_map:
                return command_map[args.command](args, client)
            elif args.command == 'device-info':
                if args.subcommand in device_info_map:
                    return device_info_map[args.subcommand](args, client)
            elif args.command == 'sensor-names':
                if args.subcommand in sensor_names_map:
                    return sensor_names_map[args.subcommand](args, client)
            elif args.command == 'limits':
                if args.subcommand in limits_map:
                    return limits_map[args.subcommand](args, client)
            elif args.command == 'calibrate':
                return cmd_calibrate(args, client)
            elif args.command == 'settings':
                if args.subcommand in settings_map:
                    return settings_map[args.subcommand](args, client)
            elif args.command == 'log':
                if args.subcommand in log_map:
                    return log_map[args.subcommand](args, client)
            elif args.command == 'record':
                if args.subcommand in record_map:
                    return record_map[args.subcommand](args, client)

            print_error("Unknown command or subcommand")
            return 1

    except M307Error as e:
        print_error(str(e))
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted\n")
        return 130
    except Exception as e:
        print_error("Unexpected error: {}".format(e))
        if '--debug' in sys.argv:
            raise
        return 1


if __name__ == '__main__':
    sys.exit(main())
