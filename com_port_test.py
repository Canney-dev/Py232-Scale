import serial.tools.list_ports

ports = serial.tools.list_ports.comports()

print("Available COM ports:")
for port in ports:
    print(f"{port.device} - {port.description}")
