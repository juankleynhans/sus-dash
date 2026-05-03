import serial
import time
import os

# -------------------------
# CONFIG
# -------------------------
PORT = "COM5"
BAUD = 115200
HEADER = bytes([83, 84, 65, 82, 84])  # START
PACKET_SIZE = 120

UPDATE_RATE = 0.04  # 25 samples/sec

# RPM calibration:
# raw 35  = 930 RPM
# raw 111 = 2500 RPM
RPM_OFFSET = 207.0
RPM_SCALE = 20.66

# Boost calibration
MAP_OFFSET = 0.767
MAP_SCALE = 0.00907
BOOST_CORRECTION = 0.0001

# Temp calibration
CLT_OFFSET = 91.1
CLT_SCALE = 0.0958

IAT_OFFSET = 62.43
IAT_SCALE = 0.1268


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def find_packet(buffer):
    start = buffer.find(HEADER)

    if start == -1:
        if len(buffer) > len(HEADER):
            del buffer[:-len(HEADER)]
        return None

    if len(buffer) < start + PACKET_SIZE:
        return None

    packet = buffer[start:start + PACKET_SIZE]
    del buffer[:start + PACKET_SIZE]
    return packet


print("Connecting to ECU...")
ser = serial.Serial(PORT, BAUD, timeout=1)
print("Connected\n")

buffer = bytearray()
last_display_update = 0

frame_count = 0
fps_timer = time.time()
fps = 0

latest_packet = None

while True:
    data = ser.read(ser.in_waiting or 1)

    if data:
        buffer.extend(data)

    packet = find_packet(buffer)

    if packet is not None:
        latest_packet = packet
        frame_count += 1

    now = time.time()

    if now - fps_timer >= 1.0:
        fps = frame_count
        frame_count = 0
        fps_timer = now

    if latest_packet is not None and now - last_display_update >= UPDATE_RATE:
        last_display_update = now
        packet = latest_packet

        # RPM - Still need to figure out if thise run between 2 Frames ( Looks like it) - Possible frame split between low and high RPM
        rpm_byte = packet[6]
        rpm = RPM_OFFSET + (rpm_byte * RPM_SCALE)

        # Boost / MAP
        map_byte = packet[12]
        boost_bar = (MAP_OFFSET - (map_byte * MAP_SCALE)) + BOOST_CORRECTION

        # TPS - Still work in progress 
        tps = packet[14]

        # Coolant temp
        clt_byte = packet[16]
        clt_status = packet[17]
        coolant = CLT_OFFSET - (clt_byte * CLT_SCALE)

        # Intake air temp
        iat_byte = packet[18]
        iat_status = packet[19]
        iat = IAT_OFFSET - (iat_byte * IAT_SCALE)

        # Battery - Completed 100% Working
        raw_batt = (packet[21] << 8) | packet[20]
        battery = raw_batt / 64.0

        # GPO-01 - Completed 100% Working
        gpo1_raw = packet[27]
        gpo1 = "ON" if gpo1_raw >= 128 else "OFF"

        # GPO-02 - Completed 100% Working
        gpo2_raw = packet[28]
        gpo2 = "ON" if gpo2_raw >= 128 else "OFF"
        clear_screen()

        print("SUSTECH ECU LIVE DECODER")
        print("=" * 60)
        print(f"ECU/Decoder Rate: {fps} samples/sec")

        print("\nDECODED VALUES")
        print("-" * 60)
        print(f"{'RPM':<15}{rpm:>10.0f}")
        print(f"{'BOOST':<15}{boost_bar:>10.3f} bar")
        print(f"{'TPS':<15}{tps:>10d} %")
        print(f"{'CLT':<15}{coolant:>10.1f} °C")
        print(f"{'IAT':<15}{iat:>10.1f} °C")
        print(f"{'BATT':<15}{battery:>10.2f} V")
        print(f"{'GPO1':<15}{gpo1:>10}")
        print(f"{'GPO2':<15}{gpo2:>10}")

        print("\nRAW VALUES")
        print("-" * 60)
        print(f"{'RPM_B':<15}{rpm_byte:>10}")
        print(f"{'RPM_OFFSET':<15}{RPM_OFFSET:>10.1f}")
        print(f"{'RPM_SCALE':<15}{RPM_SCALE:>10.2f}")
        print(f"{'MAP_B':<15}{map_byte:>10}")
        print(f"{'TPS_B':<15}{tps:>10}")
        print(f"{'CLT_BYTE':<15}{clt_byte:>10}")
        print(f"{'CLT_STATUS':<15}{clt_status:>10}")
        print(f"{'IAT_BYTE':<15}{iat_byte:>10}")
        print(f"{'IAT_STATUS':<15}{iat_status:>10}")
        print(f"{'BATT_RAW':<15}{raw_batt:>10}")
        print(f"{'GPO1_RAW':<15}{gpo1_raw:>10}")
        print(f"{'GPO2_RAW':<15}{gpo2_raw:>10}")

    time.sleep(0.001)
