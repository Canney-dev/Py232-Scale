import time

import serial
from serial.tools import list_ports


BAUDRATE = 9600
TIMEOUT = 1
PROBE_SECONDS = 2


def open_scale(port):
    return serial.Serial(
        port=port,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=TIMEOUT,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def read_line(scale):
    raw = scale.readline()

    if not raw:
        return ""

    return raw.decode("ascii", errors="ignore").strip()


def detect_com_port():
    ports = list(list_ports.comports())

    if not ports:
        print("No COM ports found.")
        return None

    print("Available COM ports:")
    for port in ports:
        print(f"{port.device} - {port.description}")

    print("\nProbing COM ports for scale data...\n")

    first_open_port = None

    for port in ports:
        print(f"Trying {port.device}...")

        try:
            with open_scale(port.device) as scale:
                if first_open_port is None:
                    first_open_port = port.device

                scale.reset_input_buffer()
                deadline = time.time() + PROBE_SECONDS

                while time.time() < deadline:
                    line = read_line(scale)
                    if line:
                        print(f"Detected data on {port.device}: {line}")
                        return port.device

        except serial.SerialException as exc:
            print(f"Could not open {port.device}: {exc}")

    if first_open_port:
        print(f"No data detected. Using first open port: {first_open_port}")
        return first_open_port

    print("No usable COM port found.")
    return None


def main():
    scale = None
    port = detect_com_port()

    if not port:
        return

    try:
        scale = open_scale(port)
        scale.reset_input_buffer()

        print(f"\nConnected to {port}")
        print("Reading scale data. Press Ctrl+C to stop.\n")

        while True:
            line = read_line(scale)

            if line:
                print(f"Raw: {line}")

    except serial.SerialException as exc:
        print(f"Serial error: {exc}")

    except KeyboardInterrupt:
        print("\nStopped by user.")

    finally:
        if scale and scale.is_open:
            scale.close()
            print("Serial port closed.")


if __name__ == "__main__":
    main()
