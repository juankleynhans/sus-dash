import serial
import time
import math

# -------------------------
# CONFIG
# -------------------------
PORT = "COM10"       # Emulator side of virtual COM pair
BAUD = 115200
HEADER = bytes([83, 84, 65, 82, 84])  # START
PACKET_SIZE = 120
RATE = 1 / 25        # 25 samples/sec

# -------------------------
# CALIBRATION CONSTANTS
# -------------------------
RPM_OFFSET = 207.0
RPM_SCALE = 20.66

MAP_OFFSET = 0.767
MAP_SCALE = 0.00907
BOOST_CORRECTION = 0.10

CLT_OFFSET = 91.1
CLT_SCALE = 0.0958

IAT_OFFSET = 62.43
IAT_SCALE = 0.1268

# -------------------------
# CONNECT
# -------------------------
print("Starting Sustech ECU emulator...")
print(f"Opening {PORT} at {BAUD} baud")

ser = serial.Serial(PORT, BAUD, timeout=0)

print("Emulator running at 25 samples/sec")
print("Incoming Sustech software commands will be printed below.\n")

t = 0.0
frame_counter = 0
last_send = time.time()

while True:
    # -------------------------
    # Read incoming data from Sustech software
    # -------------------------
    incoming = ser.read(ser.in_waiting or 0)

    if incoming:
        ascii_view = "".join(chr(b) if 32 <= b <= 126 else "." for b in incoming)
        hex_view = " ".join(f"{b:02X}" for b in incoming)

        print("\nINCOMING FROM SOFTWARE")
        print("-" * 60)
        print("HEX  :", hex_view)
        print("ASCII:", ascii_view)
        print("-" * 60)

    # -------------------------
    # Send fake ECU packet at 25Hz
    # -------------------------
    now = time.time()

    if now - last_send >= RATE:
        last_send = now

        packet = bytearray(PACKET_SIZE)

        # Header
        packet[0:5] = HEADER

        # -------------------------
        # Simulated true RPM
        # -------------------------
        true_rpm = 930 + 2500 * abs(math.sin(t * 0.8))

        rpm_byte_simple = int((true_rpm - RPM_OFFSET) / RPM_SCALE)
        rpm_byte_simple = max(0, min(255, rpm_byte_simple))

        rpm_low_byte = int(true_rpm / 10) & 0xFF
        rpm_high_byte = int(true_rpm / 256) & 0xFF

        if frame_counter % 2 == 0:
            packet[6] = rpm_low_byte
            packet[7] = 0
            packet[8] = 0x01
        else:
            packet[6] = rpm_high_byte
            packet[7] = 0
            packet[8] = 0x02

        packet[9] = rpm_byte_simple

        # -------------------------
        # Boost / MAP
        # -------------------------
        boost = -0.65 + 0.55 * abs(math.sin(t * 0.6))

        map_byte = int((MAP_OFFSET + BOOST_CORRECTION - boost) / MAP_SCALE)
        map_byte = max(0, min(255, map_byte))
        packet[13] = map_byte

        # -------------------------
        # TPS
        # -------------------------
        tps = int(3 + 60 * abs(math.sin(t * 0.9)))
        packet[14] = max(0, min(100, tps))

        # -------------------------
        # Coolant
        # -------------------------
        coolant = 78 + 7 * math.sin(t * 0.08)
        clt_byte = int((CLT_OFFSET - coolant) / CLT_SCALE)
        packet[16] = max(0, min(255, clt_byte))
        packet[17] = 0

        # -------------------------
        # Intake Air Temp
        # -------------------------
        iat = 34 + 12 * math.sin(t * 0.12)
        iat_byte = int((IAT_OFFSET - iat) / IAT_SCALE)
        packet[18] = max(0, min(255, iat_byte))
        packet[19] = 0

        # -------------------------
        # Battery
        # -------------------------
        battery = 14.1 + 0.15 * math.sin(t * 0.4)
        batt_raw = int(battery * 64)
        packet[20] = batt_raw & 0xFF
        packet[21] = (batt_raw >> 8) & 0xFF

        # -------------------------
        # GPO1
        # -------------------------
        packet[28] = 255 if int(t) % 4 < 2 else 0

        # -------------------------
        # Send packet
        # -------------------------
        ser.write(packet)

        print(
            f"OUT Frame:{frame_counter:05d} "
            f"RPMMarker:{packet[8]} "
            f"TrueRPM:{true_rpm:6.0f} "
            f"RPM_B6:{packet[6]:3d} "
            f"MAP_B:{packet[13]:3d} "
            f"TPS:{packet[14]:3d} "
            f"CLT_B:{packet[16]:3d} "
            f"IAT_B:{packet[18]:3d} "
            f"BATT:{battery:4.2f} "
            f"GPO1:{packet[28]}"
        )

        frame_counter += 1
        t += RATE

    time.sleep(0.001)
