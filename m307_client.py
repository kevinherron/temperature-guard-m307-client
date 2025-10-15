# -*- coding: utf-8 -*-
"""
M307 Temperature Guard TCP Client

Python 2.7/3.x compatible client for communicating with M307 Temperature Guard devices
via TCP/IP on port 10001.

Protocol: 60-byte records (4-byte command + 56-byte data)

Usage:
    from m307_client import M307Client

    with M307Client('192.168.1.100') as client:
        status = client.read_status()
        print("Temperature: {} {}".format(
            status['temperature_sensor_1']['reading'],
            status['temperature_unit']
        ))
"""

from __future__ import division, print_function, absolute_import

import socket
import struct
from datetime import datetime


class M307Error(Exception):
    """Base exception for M307 client errors"""
    pass


class M307ConnectionError(M307Error):
    """Connection-related errors"""
    pass


class M307CommandError(M307Error):
    """Command execution errors"""
    pass


class M307ValidationError(M307Error):
    """Data validation errors"""
    pass


class M307Client(object):
    """
    M307 Temperature Guard TCP Client

    Provides interface for:
    - Reading current status (sensors, doors, power, battery)
    - Reading/writing user configuration records (0-5)
    - Managing on-board data logging
    """

    # Protocol constants
    PACKET_SIZE = 60
    COMMAND_SIZE = 4
    DATA_SIZE = 56
    DEFAULT_PORT = 10001
    DEFAULT_TIMEOUT = 5.0

    # Command bytes
    CMD_READ_STATUS = (0x3f, 0xcd, 0xdc, 0x00)

    CMD_READ_USER_RECORD = {
        0: (0xaa, 0xbb, 0xcc, 0x00),
        1: (0xaa, 0xbb, 0xcc, 0x01),
        2: (0xaa, 0xbb, 0xcc, 0x02),
        3: (0xaa, 0xbb, 0xcc, 0x03),
        4: (0xaa, 0xbb, 0xcc, 0x04),
        5: (0xaa, 0xbb, 0xcc, 0x05),
    }

    CMD_WRITE_USER_RECORD = {
        0: (0xdd, 0xcc, 0xbb, 0x00),
        1: (0xdd, 0xcc, 0xbb, 0x01),
        2: (0xdd, 0xcc, 0xbb, 0x02),
        3: (0xdd, 0xcc, 0xbb, 0x03),
        4: (0xdd, 0xcc, 0xbb, 0x04),
        5: (0xdd, 0xcc, 0xbb, 0x05),
    }

    CMD_SET_LOG_DATETIME = (0xde, 0xca, 0xde, 0x00)
    CMD_READ_LOG_DATETIME = (0xde, 0xca, 0xde, 0x02)
    CMD_READ_LOG_FILE = (0xde, 0xca, 0xde, 0x04)

    LOG_FILE_END_MARKER = "THE-END"

    def __init__(self, host, port=None, timeout=None):
        """
        Initialize M307 TCP client

        Args:
            host: IP address or hostname of M307 device
            port: TCP port (default: 10001)
            timeout: Socket timeout in seconds (default: 5.0)
        """
        self.host = host
        self.port = port if port is not None else self.DEFAULT_PORT
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self._socket = None
        self._cached_resolution = None  # 0.1 or 1.0, populated from status read
        self._cached_unit = None        # 'C' or 'F', populated from status read

    def connect(self):
        """
        Establish TCP connection to M307 device

        Raises:
            M307ConnectionError: If connection fails
        """
        if self._socket is not None:
            return

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
        except socket.error as e:
            self._socket = None
            raise M307ConnectionError("Failed to connect to {}:{} - {}".format(
                self.host, self.port, str(e)
            ))

    def disconnect(self):
        """Close TCP connection"""
        if self._socket is not None:
            try:
                self._socket.close()
            except socket.error:
                pass
            finally:
                self._socket = None
                self._cached_resolution = None
                self._cached_unit = None

    def is_connected(self):
        """
        Check if connected to device

        Returns:
            bool: True if connected
        """
        return self._socket is not None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
        return False

    # =========================================================================
    # Status Record Operations
    # =========================================================================

    def read_status(self):
        """
        Read current status record

        Returns:
            dict: Parsed status containing all sensor readings, door states,
                  power status, and battery voltage

        Raises:
            M307CommandError: If command fails
        """
        response = self._send_command(self.CMD_READ_STATUS)
        return self._parse_status_record(response)

    def get_temperature(self, sensor_number):
        """
        Get temperature reading from specific sensor

        Args:
            sensor_number: 1, 2, or 'internal'

        Returns:
            dict: {'reading': float, 'time_out_of_limits': int, 'in_alarm': bool}
        """
        status = self.read_status()
        if sensor_number == 1:
            return status['temperature_sensor_1']
        elif sensor_number == 2:
            return status['temperature_sensor_2']
        elif sensor_number == 'internal':
            return status['internal_temperature']
        else:
            raise M307ValidationError("Invalid sensor_number: {}".format(sensor_number))

    def get_humidity(self):
        """
        Get internal humidity sensor reading

        Returns:
            dict: {'reading': float, 'time_out_of_limits': int, 'in_alarm': bool}
        """
        status = self.read_status()
        return status['internal_humidity']

    def get_door_state(self, door_number):
        """
        Get door sensor state

        Args:
            door_number: 1 or 2

        Returns:
            dict: {'state': str, 'time_out_of_limits': int, 'in_alarm': bool}
        """
        status = self.read_status()
        if door_number == 1:
            return status['door_1']
        elif door_number == 2:
            return status['door_2']
        else:
            raise M307ValidationError("Invalid door_number: {}".format(door_number))

    def get_battery_voltage(self):
        """
        Get battery voltage

        Returns:
            float: Battery voltage in volts
        """
        status = self.read_status()
        return status['battery_voltage']

    def get_power_status(self):
        """
        Get main power status

        Returns:
            bool: True if main power is on
        """
        status = self.read_status()
        return status['main_power']

    def get_resolution_info(self):
        """
        Get device temperature resolution and unit.

        Reads status if not already cached. This is useful before reading
        log files to ensure proper temperature parsing.

        Returns:
            dict: {'resolution': float, 'unit': str}
                  resolution: 0.1 or 1.0 degrees
                  unit: 'C' or 'F'
        """
        if self._cached_resolution is None:
            self.read_status()

        return {
            'resolution': self._cached_resolution,
            'unit': self._cached_unit
        }

    # =========================================================================
    # User Record Operations
    # =========================================================================

    def read_user_record(self, record_number):
        """
        Read raw user record

        Args:
            record_number: Record number (0-5)

        Returns:
            bytearray: 60-byte record data

        Raises:
            M307ValidationError: If record_number is invalid
            M307CommandError: If command fails
        """
        self._validate_record_number(record_number)
        command = self.CMD_READ_USER_RECORD[record_number]
        return self._send_command(command)

    def write_user_record(self, record_number, data):
        """
        Write user record

        Args:
            record_number: Record number (0-5)
            data: 60-byte bytearray or list of bytes

        Returns:
            bool: True if write verified successfully

        Raises:
            M307ValidationError: If record_number or data is invalid
            M307CommandError: If command fails or verification fails
        """
        self._validate_record_number(record_number)

        if len(data) != self.PACKET_SIZE:
            raise M307ValidationError(
                "Data must be {} bytes, got {}".format(self.PACKET_SIZE, len(data))
            )

        # Replace command bytes with write command
        write_data = bytearray(data)
        write_cmd = self.CMD_WRITE_USER_RECORD[record_number]
        write_data[0:4] = write_cmd

        # Send write command
        response = self._send_command(write_cmd, write_data[4:])

        # Verify response
        # Response should contain the READ command bytes, not WRITE
        read_cmd = self.CMD_READ_USER_RECORD[record_number]
        if tuple(response[0:4]) != read_cmd:
            raise M307CommandError("Write verification failed: unexpected command in response")

        # Compare data bytes (skip command bytes)
        if response[4:] != write_data[4:]:
            raise M307CommandError("Write verification failed: data mismatch")

        return True

    # -------------------------------------------------------------------------
    # Record 0: Sensor Limits
    # -------------------------------------------------------------------------

    def get_sensor_limits(self):
        """
        Get sensor limits configuration (User Record 0)

        Returns:
            dict: Sensor limits and configuration
        """
        data = self.read_user_record(0)
        return self._parse_sensor_limits(data)

    def set_sensor_limits(self, limits):
        """
        Set sensor limits configuration (User Record 0)

        Args:
            limits: dict with limit configuration

        Returns:
            bool: True if successful
        """
        # Read current record
        current_data = self.read_user_record(0)

        # Modify with new limits
        new_data = self._build_sensor_limits(current_data, limits)

        # Write back
        return self.write_user_record(0, new_data)

    # -------------------------------------------------------------------------
    # Record 1: Device Identification
    # -------------------------------------------------------------------------

    def get_device_info(self):
        """
        Get device identification (User Record 1)

        Returns:
            dict: {'device_name': str, 'unit_of_measure': str,
                   'mac_address': str, 'serial_number': str}
        """
        data = self.read_user_record(1)
        return {
            'device_name': self._extract_string(data, 8, 20).strip(),
            'unit_of_measure': chr(data[28]) if data[28] in (0x43, 0x46) else '?',
            'mac_address': self._extract_string(data, 29, 20).strip(),
            'serial_number': self._extract_string(data, 50, 10).strip(),
        }

    def set_device_info(self, info):
        """
        Set device identification (User Record 1)

        Args:
            info: dict with 'device_name', 'unit_of_measure', 'mac_address', 'serial_number'

        Returns:
            bool: True if successful
        """
        # Read current record
        data = self.read_user_record(1)

        # Update fields
        if 'device_name' in info:
            self._insert_string(data, 8, 20, info['device_name'])

        if 'unit_of_measure' in info:
            unit = info['unit_of_measure'].upper()
            if unit == 'C':
                data[28] = 0x43
            elif unit == 'F':
                data[28] = 0x46
            else:
                raise M307ValidationError("unit_of_measure must be 'C' or 'F'")

        if 'mac_address' in info:
            self._insert_string(data, 29, 20, info['mac_address'])

        if 'serial_number' in info:
            self._insert_string(data, 50, 10, info['serial_number'])

        return self.write_user_record(1, data)

    # -------------------------------------------------------------------------
    # Record 2: Temperature Sensor Names
    # -------------------------------------------------------------------------

    def get_temperature_sensor_names(self):
        """
        Get temperature sensor names (User Record 2)

        Returns:
            dict: {'sensor_1': str, 'sensor_2': str}
        """
        data = self.read_user_record(2)
        return {
            'sensor_1': self._extract_string(data, 8, 20).strip(),
            'sensor_2': self._extract_string(data, 28, 20).strip(),
        }

    def set_temperature_sensor_names(self, sensor_1_name, sensor_2_name):
        """
        Set temperature sensor names (User Record 2)

        Note: Sensors must be named to enable alarms

        Args:
            sensor_1_name: Name for temperature sensor 1 (max 20 chars)
            sensor_2_name: Name for temperature sensor 2 (max 20 chars)

        Returns:
            bool: True if successful
        """
        data = self.read_user_record(2)
        self._insert_string(data, 8, 20, sensor_1_name)
        self._insert_string(data, 28, 20, sensor_2_name)
        return self.write_user_record(2, data)

    # -------------------------------------------------------------------------
    # Record 3: Door Sensor Names
    # -------------------------------------------------------------------------

    def get_door_sensor_names(self):
        """
        Get door sensor names (User Record 3)

        Returns:
            dict: {'door_1': str, 'door_2': str}
        """
        data = self.read_user_record(3)
        return {
            'door_1': self._extract_string(data, 8, 20).strip(),
            'door_2': self._extract_string(data, 28, 20).strip(),
        }

    def set_door_sensor_names(self, door_1_name, door_2_name):
        """
        Set door sensor names (User Record 3)

        Note: Sensors must be named to enable alarms

        Args:
            door_1_name: Name for door sensor 1 (max 20 chars)
            door_2_name: Name for door sensor 2 (max 20 chars)

        Returns:
            bool: True if successful
        """
        data = self.read_user_record(3)
        self._insert_string(data, 8, 20, door_1_name)
        self._insert_string(data, 28, 20, door_2_name)
        return self.write_user_record(3, data)

    # -------------------------------------------------------------------------
    # Record 4: Device Settings
    # -------------------------------------------------------------------------

    def get_device_settings(self):
        """
        Get device settings (User Record 4)

        Returns:
            dict: {'relay_logic': int, 'alarm_reminder_delay': int,
                   'buzzer_enabled': bool, 'two_stage_door_alarm_delay': int}
        """
        data = self.read_user_record(4)
        return {
            'relay_logic': data[8],
            'alarm_reminder_delay': data[9],
            'buzzer_enabled': bool(data[10]),
            'two_stage_door_alarm_delay': data[11],
        }

    def set_device_settings(self, settings):
        """
        Set device settings (User Record 4)

        Args:
            settings: dict with 'relay_logic', 'alarm_reminder_delay',
                     'buzzer_enabled', 'two_stage_door_alarm_delay'

        Returns:
            bool: True if successful
        """
        data = self.read_user_record(4)

        if 'relay_logic' in settings:
            data[8] = int(settings['relay_logic']) & 0xFF

        if 'alarm_reminder_delay' in settings:
            data[9] = int(settings['alarm_reminder_delay']) & 0xFF

        if 'buzzer_enabled' in settings:
            data[10] = 1 if settings['buzzer_enabled'] else 0

        if 'two_stage_door_alarm_delay' in settings:
            data[11] = int(settings['two_stage_door_alarm_delay']) & 0xFF

        return self.write_user_record(4, data)

    # -------------------------------------------------------------------------
    # Record 5: Internal Sensor Names
    # -------------------------------------------------------------------------

    def get_internal_sensor_names(self):
        """
        Get internal sensor names (User Record 5)

        Returns:
            dict: {'temperature': str, 'humidity': str}
        """
        data = self.read_user_record(5)
        return {
            'temperature': self._extract_string(data, 8, 20).strip(),
            'humidity': self._extract_string(data, 28, 20).strip(),
        }

    def set_internal_sensor_names(self, temperature_name, humidity_name):
        """
        Set internal sensor names (User Record 5)

        Note: Sensors must be named to enable alarms

        Args:
            temperature_name: Name for internal temperature sensor (max 20 chars)
            humidity_name: Name for internal humidity sensor (max 20 chars)

        Returns:
            bool: True if successful
        """
        data = self.read_user_record(5)
        self._insert_string(data, 8, 20, temperature_name)
        self._insert_string(data, 28, 20, humidity_name)
        return self.write_user_record(5, data)

    # =========================================================================
    # Data Logging Operations
    # =========================================================================

    def set_log_datetime(self, dt, log_rate_minutes):
        """
        Set device date/time and logging interval

        Args:
            dt: datetime object
            log_rate_minutes: Logging interval (1-60 minutes)

        Returns:
            bool: True if successful

        Raises:
            M307ValidationError: If parameters are invalid
        """
        if not isinstance(dt, datetime):
            raise M307ValidationError("dt must be a datetime object")

        if not (1 <= log_rate_minutes <= 60):
            raise M307ValidationError("log_rate_minutes must be 1-60")

        # Build data packet
        data = bytearray(self.DATA_SIZE)
        data[0] = 0  # Seconds (not used)
        data[1] = self.int_to_bcd(dt.minute)
        data[2] = self.int_to_bcd(dt.hour)
        data[3] = 0  # Leave blank
        data[4] = self.int_to_bcd(dt.day)
        data[5] = self.int_to_bcd(dt.month)
        data[6] = self.int_to_bcd(dt.year - 2000)
        data[7] = log_rate_minutes & 0xFF

        self._send_command(self.CMD_SET_LOG_DATETIME, data)
        return True

    def get_log_info(self):
        """
        Get log information (date/time, rate, record count)

        Returns:
            dict: {'datetime': datetime, 'log_rate_minutes': int, 'total_records': int}
        """
        response = self._send_command(self.CMD_READ_LOG_DATETIME)

        # Parse response
        seconds = response[4]
        minutes = self.bcd_to_int(response[5])
        hours = self.bcd_to_int(response[6]) & 0x1F  # Mask off upper bits
        day_of_week = self.bcd_to_int(response[7])
        day = self.bcd_to_int(response[8])
        month = self.bcd_to_int(response[9])
        year = 2000 + self.bcd_to_int(response[10])
        log_rate = response[11]
        total_records = (response[12] << 8) | response[13]

        dt = datetime(year, month, day, hours, minutes, seconds)

        return {
            'datetime': dt,
            'log_rate_minutes': log_rate,
            'total_records': total_records,
        }

    def read_log_file(self, reset_pointer=True, callback=None):
        """
        Read entire log file (up to 4000 records, 15 bytes each)

        Device resolution is automatically detected before parsing if not
        already cached (0.1° for firmware v5+, 1.0° for older versions).

        Args:
            reset_pointer: If True, reset log pointer before reading
            callback: Optional function(record_dict) called for each record

        Returns:
            list: List of record dicts with the following structure:
                {
                    'datetime': datetime object,
                    'temp_1': float or None or inf or -inf,
                    'temp_2': float or None or inf or -inf,
                    'internal_temp': float or None or inf or -inf,
                    'internal_humidity': float or None,
                    'door_1_state': bool,
                    'door_2_state': bool,
                    'power_status': bool
                }

            Special temperature values:
                - None: No sensor connected
                - float('inf'): Sensor open circuit
                - float('-inf'): Sensor shorted

            Special humidity values:
                - None: Sensor failed

        Note:
            This may take significant time for large log files.
            Use callback for streaming processing.
        """
        # Ensure we know the device's resolution before parsing logs
        if self._cached_resolution is None:
            self.read_status()

        # Build command
        data = bytearray(self.DATA_SIZE)
        data[0] = 0x01 if reset_pointer else 0x00

        # Send command
        self._send_command(self.CMD_READ_LOG_FILE, data)

        # Read log records
        records = []
        record_buffer = bytearray()

        # Convert end marker to bytes for Python 2/3 compatibility
        end_marker_bytes = self.LOG_FILE_END_MARKER.encode('ascii')

        while True:
            # Read data from socket
            try:
                chunk = self._socket.recv(4096)
                if not chunk:
                    break

                record_buffer.extend(chunk)

                # Check for end marker (works in both Python 2 and 3)
                if end_marker_bytes in bytes(record_buffer):
                    # Remove end marker and any trailing data
                    marker_pos = bytes(record_buffer).find(end_marker_bytes)
                    record_buffer = record_buffer[:marker_pos]
                    break

                # Process complete records (15 bytes each)
                while len(record_buffer) >= 15:
                    record_data = record_buffer[:15]
                    record_buffer = record_buffer[15:]

                    record = self._parse_log_record(record_data, self._cached_resolution)
                    records.append(record)

                    if callback is not None:
                        callback(record)

            except socket.timeout:
                break

        return records

    # =========================================================================
    # Helper Methods - Data Conversion
    # =========================================================================

    @staticmethod
    def bytes_to_int16(msb, lsb):
        """
        Convert two bytes to signed 16-bit integer

        Args:
            msb: Most significant byte
            lsb: Least significant byte

        Returns:
            int: Signed 16-bit integer
        """
        value = (msb << 8) | lsb

        # Check if negative (bit 15 set)
        if value & 0x8000:
            value = -(0x10000 - value)

        return value

    @staticmethod
    def int16_to_bytes(value):
        """
        Convert signed 16-bit integer to two bytes

        Args:
            value: Signed integer (-32768 to 32767)

        Returns:
            tuple: (msb, lsb)
        """
        if value < -32768 or value > 32767:
            raise M307ValidationError("Value must be -32768 to 32767")

        if value < 0:
            value = 0x10000 + value

        msb = (value >> 8) & 0xFF
        lsb = value & 0xFF

        return (msb, lsb)

    @staticmethod
    def bcd_to_int(bcd_byte):
        """
        Convert BCD byte to integer (0-99)

        Args:
            bcd_byte: BCD encoded byte

        Returns:
            int: Integer value (0-99)
        """
        high_nibble = (bcd_byte >> 4) & 0x0F
        low_nibble = bcd_byte & 0x0F
        return high_nibble * 10 + low_nibble

    @staticmethod
    def int_to_bcd(value):
        """
        Convert integer (0-99) to BCD byte

        Args:
            value: Integer (0-99)

        Returns:
            int: BCD encoded byte
        """
        if value < 0 or value > 99:
            raise M307ValidationError("BCD value must be 0-99")

        high_nibble = (value // 10) & 0x0F
        low_nibble = value % 10
        return (high_nibble << 4) | low_nibble

    @staticmethod
    def parse_temperature(msb, lsb, resolution, unit):
        """
        Parse temperature bytes

        Args:
            msb: Most significant byte
            lsb: Least significant byte
            resolution: 0.1 or 1.0
            unit: 'C' or 'F'

        Returns:
            float: Temperature value with proper resolution
        """
        raw_value = M307Client.bytes_to_int16(msb, lsb)

        # Check for special values
        if raw_value == 1000:
            return None  # No sensor connected
        elif raw_value == 999:
            return float('inf')  # Sensor open circuit
        elif raw_value == -999:
            return float('-inf')  # Sensor shorted

        # Apply resolution
        return float(raw_value) / (10.0 if resolution == 0.1 else 1.0)

    @staticmethod
    def parse_humidity(msb, lsb):
        """
        Parse humidity bytes (always 0.1% RH resolution)

        Args:
            msb: Most significant byte
            lsb: Least significant byte

        Returns:
            float: Humidity percentage with 0.1% resolution
        """
        raw_value = M307Client.bytes_to_int16(msb, lsb)

        # Check for special values
        if raw_value == 999:
            return None  # Sensor failed

        return float(raw_value) / 10.0

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _send_command(self, command_bytes, data_bytes=None):
        """
        Send 60-byte command and receive 60-byte response

        Args:
            command_bytes: 4-byte command tuple
            data_bytes: Optional 56-byte data (will be padded with zeros)

        Returns:
            bytearray: 60-byte response

        Raises:
            M307ConnectionError: If not connected
            M307CommandError: If command fails
        """
        if not self.is_connected():
            raise M307ConnectionError("Not connected to device")

        # Build packet
        packet = self._build_command_packet(command_bytes, data_bytes)

        # Send command
        try:
            self._socket.sendall(bytes(packet))
        except socket.error as e:
            raise M307CommandError("Failed to send command: {}".format(str(e)))

        # Receive response
        try:
            response = bytearray()
            while len(response) < self.PACKET_SIZE:
                chunk = self._socket.recv(self.PACKET_SIZE - len(response))
                if not chunk:
                    raise M307CommandError("Connection closed by device")
                response.extend(chunk)

            return response
        except socket.timeout:
            raise M307CommandError("Timeout waiting for response")
        except socket.error as e:
            raise M307CommandError("Failed to receive response: {}".format(str(e)))

    def _build_command_packet(self, cmd_bytes, data_bytes=None):
        """
        Build 60-byte packet

        Args:
            cmd_bytes: 4-byte command tuple
            data_bytes: Optional data bytes

        Returns:
            bytearray: 60-byte packet
        """
        packet = bytearray(self.PACKET_SIZE)

        # Set command bytes
        packet[0:4] = cmd_bytes

        # Set data bytes if provided
        if data_bytes is not None:
            data_len = min(len(data_bytes), self.DATA_SIZE)
            packet[4:4+data_len] = data_bytes[:data_len]

        return packet

    def _validate_record_number(self, record_number):
        """
        Validate record number is 0-5

        Raises:
            M307ValidationError: If invalid
        """
        if record_number not in range(6):
            raise M307ValidationError(
                "Invalid record_number: {} (must be 0-5)".format(record_number)
            )

    def _parse_status_record(self, data):
        """
        Parse status record bytes into structured dict

        Args:
            data: 60-byte status record

        Returns:
            dict: Parsed status
        """
        # Get temperature resolution and unit
        resolution = 0.1 if data[58] == 10 else 1.0
        unit = chr(data[59]) if data[59] in (0x43, 0x46) else '?'

        # Cache for use in log parsing
        self._cached_resolution = resolution
        self._cached_unit = unit

        return {
            'temperature_sensor_1': {
                'reading': self.parse_temperature(data[4], data[5], resolution, unit),
                'time_out_of_limits': self.bytes_to_int16(data[6], data[7]),
                'in_alarm': bool(data[8]),
            },
            'temperature_sensor_2': {
                'reading': self.parse_temperature(data[9], data[10], resolution, unit),
                'time_out_of_limits': self.bytes_to_int16(data[11], data[12]),
                'in_alarm': bool(data[13]),
            },
            'internal_temperature': {
                'reading': self.parse_temperature(data[14], data[15], resolution, unit),
                'time_out_of_limits': self.bytes_to_int16(data[16], data[17]),
                'in_alarm': bool(data[18]),
            },
            'internal_humidity': {
                'reading': self.parse_humidity(data[19], data[20]),
                'time_out_of_limits': self.bytes_to_int16(data[21], data[22]),
                'in_alarm': bool(data[23]),
            },
            'door_1': {
                'state': 'closed' if data[25] == 1 else 'open',
                'time_out_of_limits': self.bytes_to_int16(data[26], data[27]),
                'in_alarm': bool(data[28]),
            },
            'door_2': {
                'state': 'closed' if data[30] == 1 else 'open',
                'time_out_of_limits': self.bytes_to_int16(data[31], data[32]),
                'in_alarm': bool(data[33]),
            },
            'main_power': data[34] == 4,
            'battery_voltage': float(self.bytes_to_int16(data[35], data[36])) / 100.0,
            'temperature_resolution': resolution,
            'temperature_unit': unit,
        }

    def _parse_sensor_limits(self, data):
        """
        Parse sensor limits from User Record 0

        Args:
            data: 60-byte record

        Returns:
            dict: Parsed sensor limits
        """
        return {
            'temp_sensor_1': {
                'lower_limit': self.bytes_to_int16(data[8], data[9]),
                'upper_limit': self.bytes_to_int16(data[10], data[11]),
                'time_delay': self.bytes_to_int16(data[12], data[13]),
            },
            'temp_sensor_2': {
                'lower_limit': self.bytes_to_int16(data[14], data[15]),
                'upper_limit': self.bytes_to_int16(data[16], data[17]),
                'time_delay': self.bytes_to_int16(data[18], data[19]),
            },
            'internal_temp': {
                'lower_limit': self.bytes_to_int16(data[20], data[21]),
                'upper_limit': self.bytes_to_int16(data[22], data[23]),
                'time_delay': self.bytes_to_int16(data[24], data[25]),
            },
            'internal_humidity': {
                'lower_limit': self.bytes_to_int16(data[26], data[27]),
                'upper_limit': self.bytes_to_int16(data[28], data[29]),
                'time_delay': self.bytes_to_int16(data[30], data[31]),
            },
            'door_1_time_delay': self.bytes_to_int16(data[32], data[33]),
            'door_2_time_delay': self.bytes_to_int16(data[34], data[35]),
            'temp_sensor_1_correction': self.bytes_to_int16(data[36], data[37]),
            'temp_sensor_2_correction': self.bytes_to_int16(data[38], data[39]),
            'internal_temp_correction': self.bytes_to_int16(data[40], data[41]),
            'internal_humidity_correction': self.bytes_to_int16(data[42], data[43]),
            'input_1_logic_level': data[45],
            'input_2_logic_level': data[46],
        }

    def _build_sensor_limits(self, current_data, limits):
        """
        Build sensor limits record from dict

        Args:
            current_data: Current 60-byte record
            limits: dict with new limits

        Returns:
            bytearray: Updated 60-byte record
        """
        data = bytearray(current_data)

        # Temperature Sensor 1
        if 'temp_sensor_1' in limits:
            sensor = limits['temp_sensor_1']
            if 'lower_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['lower_limit']))
                data[8], data[9] = msb, lsb
            if 'upper_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['upper_limit']))
                data[10], data[11] = msb, lsb
            if 'time_delay' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['time_delay']))
                data[12], data[13] = msb, lsb

        # Temperature Sensor 2
        if 'temp_sensor_2' in limits:
            sensor = limits['temp_sensor_2']
            if 'lower_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['lower_limit']))
                data[14], data[15] = msb, lsb
            if 'upper_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['upper_limit']))
                data[16], data[17] = msb, lsb
            if 'time_delay' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['time_delay']))
                data[18], data[19] = msb, lsb

        # Internal Temperature
        if 'internal_temp' in limits:
            sensor = limits['internal_temp']
            if 'lower_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['lower_limit']))
                data[20], data[21] = msb, lsb
            if 'upper_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['upper_limit']))
                data[22], data[23] = msb, lsb
            if 'time_delay' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['time_delay']))
                data[24], data[25] = msb, lsb

        # Internal Humidity
        if 'internal_humidity' in limits:
            sensor = limits['internal_humidity']
            if 'lower_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['lower_limit']))
                data[26], data[27] = msb, lsb
            if 'upper_limit' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['upper_limit']))
                data[28], data[29] = msb, lsb
            if 'time_delay' in sensor:
                msb, lsb = self.int16_to_bytes(int(sensor['time_delay']))
                data[30], data[31] = msb, lsb

        # Door delays
        if 'door_1_time_delay' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['door_1_time_delay']))
            data[32], data[33] = msb, lsb

        if 'door_2_time_delay' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['door_2_time_delay']))
            data[34], data[35] = msb, lsb

        # Correction factors
        if 'temp_sensor_1_correction' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['temp_sensor_1_correction']))
            data[36], data[37] = msb, lsb

        if 'temp_sensor_2_correction' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['temp_sensor_2_correction']))
            data[38], data[39] = msb, lsb

        if 'internal_temp_correction' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['internal_temp_correction']))
            data[40], data[41] = msb, lsb

        if 'internal_humidity_correction' in limits:
            msb, lsb = self.int16_to_bytes(int(limits['internal_humidity_correction']))
            data[42], data[43] = msb, lsb

        # Input logic levels
        if 'input_1_logic_level' in limits:
            data[45] = int(limits['input_1_logic_level']) & 0xFF

        if 'input_2_logic_level' in limits:
            data[46] = int(limits['input_2_logic_level']) & 0xFF

        return data

    def _parse_log_record(self, record_data, resolution=0.1):
        """
        Parse 15-byte log record

        Args:
            record_data: 15-byte log record
            resolution: Temperature resolution (0.1 or 1.0)

        Returns:
            dict: Parsed log record
        """
        # Parse timestamp
        minutes = self.bcd_to_int(record_data[0])
        hours = self.bcd_to_int(record_data[1]) & 0x1F  # Mask off upper bits
        day_of_week = self.bcd_to_int(record_data[2])
        day = self.bcd_to_int(record_data[3])
        month = self.bcd_to_int(record_data[4])
        year = 2000 + self.bcd_to_int(record_data[5])

        dt = datetime(year, month, day, hours, minutes, 0)

        # Parse sensor data (raw values)
        temp_1_raw = self.bytes_to_int16(record_data[6], record_data[7])
        temp_2_raw = self.bytes_to_int16(record_data[8], record_data[9])
        internal_temp_raw = self.bytes_to_int16(record_data[10], record_data[11])
        internal_humidity_raw = self.bytes_to_int16(record_data[12], record_data[13])

        # Apply special value handling and resolution
        divisor = 10.0 if resolution == 0.1 else 1.0

        # Temperature sensor 1
        if temp_1_raw == 1000:
            temp_1 = None  # No sensor connected
        elif temp_1_raw == 999:
            temp_1 = float('inf')  # Sensor open circuit
        elif temp_1_raw == -999:
            temp_1 = float('-inf')  # Sensor shorted
        else:
            temp_1 = float(temp_1_raw) / divisor

        # Temperature sensor 2
        if temp_2_raw == 1000:
            temp_2 = None  # No sensor connected
        elif temp_2_raw == 999:
            temp_2 = float('inf')  # Sensor open circuit
        elif temp_2_raw == -999:
            temp_2 = float('-inf')  # Sensor shorted
        else:
            temp_2 = float(temp_2_raw) / divisor

        # Internal temperature
        if internal_temp_raw == 1000:
            internal_temp = None  # No sensor connected
        elif internal_temp_raw == 999:
            internal_temp = float('inf')  # Sensor open circuit
        elif internal_temp_raw == -999:
            internal_temp = float('-inf')  # Sensor shorted
        else:
            internal_temp = float(internal_temp_raw) / divisor

        # Internal humidity (always 0.1% RH resolution)
        if internal_humidity_raw == 999:
            internal_humidity = None  # Sensor failed
        else:
            internal_humidity = float(internal_humidity_raw) / 10.0

        # Parse status byte
        status_byte = record_data[14]
        door_1_state = bool(status_byte & 0x01)
        door_2_state = bool(status_byte & 0x02)
        power_status = bool(status_byte & 0x04)

        return {
            'datetime': dt,
            'temp_1': temp_1,
            'temp_2': temp_2,
            'internal_temp': internal_temp,
            'internal_humidity': internal_humidity,
            'door_1_state': door_1_state,
            'door_2_state': door_2_state,
            'power_status': power_status,
        }

    @staticmethod
    def _extract_string(data, offset, length):
        """
        Extract ASCII string from byte array

        Args:
            data: Byte array
            offset: Starting offset
            length: Maximum length

        Returns:
            str: Extracted string
        """
        chars = []
        for i in range(length):
            if offset + i >= len(data):
                break
            byte_val = data[offset + i]
            if byte_val == 0:
                break
            if 32 <= byte_val <= 126:  # Printable ASCII
                chars.append(chr(byte_val))
        return ''.join(chars)

    @staticmethod
    def _insert_string(data, offset, max_length, string):
        """
        Insert ASCII string into byte array

        Args:
            data: Byte array (will be modified)
            offset: Starting offset
            max_length: Maximum field length
            string: String to insert
        """
        # Clear field
        for i in range(max_length):
            if offset + i < len(data):
                data[offset + i] = 0

        # Insert string (truncate if needed)
        for i, char in enumerate(string[:max_length]):
            if offset + i < len(data):
                data[offset + i] = ord(char)
