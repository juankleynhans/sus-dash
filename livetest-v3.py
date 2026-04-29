import serial
import time

# -------------------------
# CONFIG
# -------------------------
PORT = "COM5"
BAUD = 115200
HEADER = bytes([83, 84, 65, 82, 84])  # "START"
PACKET_SIZE = 120

ADC_SCALE = 64.0      # try 64 first, then 32 or 128 if temps are off
PULLUP = 2490.0       # common ECU pull-up value

# MAP config
MAP_SPAN_BAR = 3.25   # -1.00 to +2.25 bar = 3.25 span
MAP_OFFSET_BAR = -1.0

# -------------------------
# SENSOR TABLES
# resistance in ohms, temp in °C
# -------------------------
CLT_TABLE = [
    (15369, -20),
    (5956, 0),
    (2774, 20),
    (1431, 40),
    (805, 60),
    (309, 80),
    (171, 100),
    (89, 120),
]

IAT_TABLE = [
    (15369, -20),
    (5956, 0),
    (2557, 20),
    (1167, 40),
    (596, 60),
    (325, 80),
    (187, 100),
    (113, 120),
]


# -------------------------
# HELPERS
# -------------------------
def adc_to_resistance(adc: float):
    if adc <= 0 or adc >= 1023:
        return None

    # For NTC sensor to ground with ECU pull-up to 5V
    return PULLUP * adc / (1023.0 - adc)


def lookup_temp_from_resistance(resistance, table):
    if resistance is None:
        return None

    for i in range(len(table) - 1):
        r1, t1 = table[i]
        r2, t2 = table[i + 1]

        # Table resistance decreases as temp increases
        if r1 >= resistance >= r2:
            ratio = (resistance - r2) / (r1 - r2)
            return t2 + ratio * (t1 - t2)

    return None


def decode_temp(raw_value: int, table):
    adc = raw_value / ADC_SCALE
    resistance = adc_to_resistance(adc)
    temp = lookup_temp_from_resistance(resistance, table)
    return temp, adc, resistance


def fmt_temp(value):
    return f"{value:5.1f}" if value is not None else "  ---"


def find_packet(buffer: bytearray):
    start = buffer.find(HEADER)
    if start == -1:
        # keep only a small tail in case the header is split across reads
        if len(buffer) > len(HEADER):
            del buffer[:-len(HEADER)]
        return None

    if len(buffer) < start + PACKET_SIZE:
        return None

    packet = buffer[start:start + PACKET_SIZE]
    del buffer[:start + PACKET_SIZE]
    return packet


# -------------------------
# CONNECT
# -------------------------
print("Connecting to ECU...")
ser = serial.Serial(PORT, BAUD, timeout=1)
print("Connected\n")

buffer = bytearray()

# -------------------------
# MAIN LOOP
# -------------------------
while True:
    data = ser.read(ser.in_waiting or 1)
    if data:
        buffer.extend(data)

    packet = find_packet(buffer)

    if packet is not None:
        # -------------------------
        # RPM
        # -------------------------
        # Current known working method:
        rpm = packet[6] * 10.0

        # Optional 16-bit test, uncomment to compare:
        # rpm16_le = (packet[7] << 8) | packet[6]
        # rpm16_be = (packet[6] << 8) | packet[7]

        # -------------------------
        # Boost / MAP
        # -------------------------
        map_byte = packet[13]
        boost_bar = (map_byte * MAP_SPAN_BAR / 255.0) + MAP_OFFSET_BAR

        # -------------------------
        # TPS
        # -------------------------
        tps = packet[14]

        # -------------------------
        # Coolant temp - 2 bytes
        # -------------------------
        raw_clt = (packet[17] << 8) | packet[16]
        coolant, adc_clt, res_clt = decode_temp(raw_clt, CLT_TABLE)

        # -------------------------
        # Intake air temp - 2 bytes
        # -------------------------
        raw_iat = (packet[19] << 8) | packet[18]
        iat, adc_iat, res_iat = decode_temp(raw_iat, IAT_TABLE)

        # -------------------------
        # Battery
        # -------------------------
        raw_batt = (packet[21] << 8) | packet[20]
        battery = raw_batt / 64.0

# -------------------------
# MAIN DISPLAY
# -------------------------
print(
    f"RPM:{rpm:5.0f}  "
    f"Boost:{boost_bar:6.3f}bar  "
    f"TPS:{tps:3d}%  "
    f"CLT:{fmt_temp(coolant)}°C  "
    f"IAT:{fmt_temp(iat)}°C  "
    f"BATT:{battery:4.2f}V"
)

# -------------------------
# RAW DEBUG DISPLAY
# -------------------------
print(
    f"RAW -> "
    f"RPM_B:{packet[6]:3d} "
    f"MAP_B:{map_byte:3d} "
    f"TPS_B:{tps:3d} "
    f"CLT_RAW:{raw_clt:5d} "
    f"CLT_ADC:{adc_clt:6.1f} "
    f"IAT_RAW:{raw_iat:5d} "
    f"IAT_ADC:{adc_iat:6.1f} "
    f"BATT_RAW:{raw_batt:5d}"
)

print("-" * 110)
